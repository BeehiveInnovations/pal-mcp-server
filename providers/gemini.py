"""Gemini model provider implementation."""

import base64
import datetime
import json
import logging
import os
import time
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from google import genai
from google.genai import types

from utils.env import get_env, get_tool_context
from utils.image_utils import validate_image

from .base import ModelProvider
from .registries.gemini import GeminiModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ModelResponse, ProviderType

logger = logging.getLogger(__name__)


class _RateLimit429(Exception):
    """Internal signal for a 429 response from Code Assist.

    Attributes:
        reason: 'RATE_LIMIT_EXCEEDED' (RPM) or 'daily' (quota exhausted).
        reset_after_ms: Milliseconds until rate-limit resets (0 if unknown).
        raw_message: Full error message from the API response.
    """

    def __init__(self, reason: str, reset_after_ms: int = 0, raw_message: str = "") -> None:
        self.reason = reason
        self.reset_after_ms = reset_after_ms
        self.raw_message = raw_message
        super().__init__(f"429 {reason}: reset_after_ms={reset_after_ms}")


def _parse_429_reason(error_body: dict) -> tuple[str, int]:
    """Parse a 429 error response body to classify reason + reset window.

    Mirrors gemini-chain.js RC1 (SHA e22f73bb, TASK-20260718-GEMINIQUOTA-
    DEEPDIVE-BRAINSTORM): a 429 is classified as terminal 'daily' (RPD) ONLY
    when the body carries an explicit per-day quota marker AND no per-minute
    marker AND the status is not the explicit transient RATE_LIMIT_EXCEEDED.
    Every other 429 — including an unparseable/ambiguous one — is transient
    'RATE_LIMIT_EXCEEDED' so the 26b→31b→26b→31b cascade actually advances
    instead of terminating on attempt 1. The prior logic defaulted to 'daily'
    on any body without a 'reset after Ns' hint, which short-circuited the
    cascade and sent 100% of traffic to 26b / 0% to 31b. retryDelay / reset
    hints seed backoff timing only — never the day-vs-minute decision.

    Returns:
        (reason_str, reset_after_ms): reason is 'RATE_LIMIT_EXCEEDED' for RPM
        throttles / ambiguous 429s, 'daily' for confirmed daily-quota
        exhaustion. reset_after_ms from a 'reset after Ns' hint or a RetryInfo
        retryDelay in the body (0 if absent).
    """
    err = error_body.get("error", {}) or {}
    msg = (err.get("message", "") or "").lower()
    status = (err.get("status", "") or "").upper()

    import re
    # Backoff-timing hint only (does NOT influence the day/minute decision).
    m = re.search(r"reset\s+after\s+(\d+(?:\.\d+)?)\s*s", msg)
    reset_ms = int(float(m.group(1)) * 1000) if m else 0
    if not reset_ms:
        rd = re.search(r'"retrydelay"\s*:\s*"(\d+(?:\.\d+)?)s"', msg)
        if rd:
            reset_ms = int(float(rd.group(1)) * 1000)

    # DAILY (RPD) only on an explicit per-day quota marker with no per-minute
    # marker and not the explicit transient status. quotaId strings look like
    # '...RequestsPerDayPerProjectPerModel' / '...PerMinutePerProjectPerModel'.
    has_daily_marker = bool(re.search(r"per[\s_-]?day|requests?_per_day|perdayper", msg))
    has_minute_marker = bool(re.search(r"per[\s_-]?minute|requests?_per_minute|perminuteper", msg))
    is_daily = has_daily_marker and not has_minute_marker and status != "RATE_LIMIT_EXCEEDED"

    if is_daily:
        return "daily", reset_ms
    return "RATE_LIMIT_EXCEEDED", reset_ms


# ---------------------------------------------------------------------------
# TASK-20260529-298 — Gemma 4-26B API key adapter
#
# Replaces OAuth/Code Assist before June 18 2026 deadline.
# Endpoint: generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent
# Auth: x-goog-api-key header (NOT Bearer).
# Activation: PAL_USE_API_KEYS=1 in PAL MCP env.
# Per-tool key routing: reads the per-call PAL tool-context ContextVar set by
# server.py at dispatch time (utils.env.get_tool_context; TASK-20260619-397-P2).
# Thought-part handling: Gemma returns reasoning in parts with thought:true; strip for clean
#   verdicts EXCEPT for tools that benefit from full reasoning (challenge, debug, codereview).
# ---------------------------------------------------------------------------

_GEMMA_MODEL = "gemma-4-26b-a4b-it"
# TASK-20260611-097: HTTP-500 fallback sibling model. Retained as the 31b name used
# in the cascade rotation (default attempts 2 and 4).
_GEMMA_FALLBACK_MODEL = "gemma-4-31b-it"
_GEMMA_ENDPOINT_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# ---------------------------------------------------------------------------
# TASK-20260614-291 — 26b→31b→26b→31b retry cascade with exponential backoff.
#
# Replaces the prior one-shot 5xx→31b fallback. On a RECOVERABLE Gemma failure
# (HTTP 5xx, connection timeout, transient RPM RATE_LIMIT_EXCEEDED) the adapter
# alternates models across attempts with exponential backoff between each:
#   attempt 1: gemma-4-26b-a4b-it
#   attempt 2: gemma-4-31b-it        (after base ms)
#   attempt 3: gemma-4-26b-a4b-it    (after base*factor ms)
#   attempt 4: gemma-4-31b-it        (after base*factor^2 ms)
# PERMANENT failures (4xx except 429, daily quota exhaustion, auth) do NOT enter
# the cascade — they raise immediately (preserves loud misconfiguration + quota
# semantics). No key rotation: alternation is MODEL-only on the same dedicated key
# (cross-endpoint key fallback BANNED, Hamad msg-34515).
#
# ENV-tunable (ENV-001). Identical constant names + defaults are mirrored by the JS
# cascade in .claude/hooks/lib/gemini-chain.js for dual-runtime parity.
# ---------------------------------------------------------------------------
_GEMMA_CASCADE_MODELS_DEFAULT = (
    "gemma-4-26b-a4b-it,gemma-4-31b-it,gemma-4-26b-a4b-it,gemma-4-31b-it"
)


def _cascade_models() -> list[str]:
    """Return the ordered model rotation for the cascade (ENV-tunable)."""
    raw = os.environ.get("GEMMA_CASCADE_MODELS", _GEMMA_CASCADE_MODELS_DEFAULT)
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or [_GEMMA_MODEL]


def _cascade_backoff_ms(attempt_index: int) -> int:
    """Backoff in ms BEFORE the given (1-based) attempt.

    attempt_index 1 → 0 (no wait before the first attempt). For attempt n>=2 the
    wait is base * factor^(n-2), capped, with ±jitter to de-sync concurrent agents.
    Mirrors GEMMA_CASCADE_BACKOFF_* constants used by the JS cascade.
    """
    if attempt_index <= 1:
        return 0
    try:
        base = float(os.environ.get("GEMMA_CASCADE_BACKOFF_BASE_MS", "1000"))
        factor = float(os.environ.get("GEMMA_CASCADE_BACKOFF_FACTOR", "2.0"))
        cap = float(os.environ.get("GEMMA_CASCADE_BACKOFF_CAP_MS", "8000"))
        jitter = float(os.environ.get("GEMMA_CASCADE_BACKOFF_JITTER", "0.3"))
    except (TypeError, ValueError):
        base, factor, cap, jitter = 1000.0, 2.0, 8000.0, 0.3
    wait = base * (factor ** (attempt_index - 2))
    wait = min(wait, cap)
    if jitter > 0:
        import random as _random
        wait *= 1.0 + _random.uniform(-jitter, jitter)
    return max(0, int(wait))

# Tools where full reasoning (thought parts) is KEPT in the response text.
# For all other tools, thought parts are stripped so only the answer remains.
_GEMMA_KEEP_THOUGHTS_TOOLS = frozenset({"challenge", "debug", "codereview", "secaudit", "thinkdeep"})

# Mapping from PAL_TOOL_CONTEXT → env var name holding the dedicated API key.
# Falls back to GEMINI_API_KEY_GENERAL when tool is not in the map.
_GEMMA_TOOL_KEY_MAP = {
    "challenge": "GEMINI_API_KEY_CHALLENGE",
    "precommit": "GEMINI_API_KEY_PRECOMMIT",
    "codereview": "GEMINI_API_KEY_CODEREVIEW",
    "secaudit": "GEMINI_API_KEY_SECAUDIT",
    "debug": "GEMINI_API_KEY_DEBUG",
    "analyze": "GEMINI_API_KEY_ANALYZE",
    "thinkdeep": "GEMINI_API_KEY_THINKDEEP",
}


class _GemmaApiKeyAdapter:
    """Calls generativelanguage.googleapis.com with x-goog-api-key + gemma-4-26b-a4b-it.

    STRICTLY DEDICATED per-tool key routing (Hamad msg-34515): each PAL endpoint is
    HARD-BOUND to exactly its own key — NO cross-key fallback between PAL endpoints.
    1,500 req/day per key is ample; cross-endpoint rotation is BANNED.
    Only permitted fallback: OAuth (when PAL_USE_API_KEYS=0) until June 18 2026.
    Thought-part handling: strips thought:true parts EXCEPT for reasoning-heavy tools.
    """

    def _get_api_key(self) -> str:
        """Return the DEDICATED API key for the current PAL_TOOL_CONTEXT.

        Strictly bound: each tool reads ONLY its own dedicated key env var.
        No cross-key fallback between PAL endpoints (Hamad msg-34515).
        Raises RuntimeError if the dedicated key is missing — this is intentional
        (misconfiguration should be loud, not silently routed to another key).
        """
        # TASK-20260619-397-P2 (RC-5): read the per-call ContextVar, not a
        # process-global env var, so concurrent tool calls cannot cross-route.
        tool_ctx = get_tool_context().lower().strip()
        env_var = _GEMMA_TOOL_KEY_MAP.get(tool_ctx, "GEMINI_API_KEY_GENERAL")
        key = os.environ.get(env_var, "")
        if not key:
            raise RuntimeError(
                f"_GemmaApiKeyAdapter: dedicated key {env_var} is missing for "
                f"tool context '{tool_ctx}'. Set {env_var} in PAL MCP env. "
                f"Cross-endpoint key fallback is BANNED (Hamad msg-34515)."
            )
        return key

    def _log_gemma_call(self, tool_name: str, model: str, tokens_in: int, tokens_out: int,
                         latency_ms: float, success: bool, error: str = None) -> None:
        """Fail-open structured log of every Gemma API call to pal-gemma-log.jsonl."""
        try:
            from datetime import datetime, timedelta
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "pal-gemma-log.jsonl")
            entry = {
                "ts": datetime.utcnow().isoformat() + "Z",
                "tool": tool_name,
                "consumer": "pal-" + (tool_name or "unknown"),
                "model": model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "total_tokens": (tokens_in + tokens_out) if (tokens_in is not None and tokens_out is not None) else None,
                "latency_ms": round(latency_ms, 1),
                "success": success,
                "error": error,
                "runtime": "python-pal",
            }
            # Read + prune existing entries (14-day TTL, mirrors writeGemmaResponseLog)
            try:
                ttl_days = float(os.environ.get("GEMMA_LOG_TTL_DAYS", "14") or "14")
                if ttl_days <= 0:
                    ttl_days = 14.0
            except (TypeError, ValueError):
                ttl_days = 14.0
            cutoff = datetime.utcnow() - timedelta(days=ttl_days)
            lines = []
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                            rec_ts = datetime.fromisoformat(rec["ts"].rstrip("Z"))
                            if rec_ts >= cutoff:
                                lines.append(line)
                        except Exception:
                            pass
            lines.append(json.dumps(entry))
            # Atomic write: write to .tmp then os.replace (single-writer safe)
            tmp_path = log_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            os.replace(tmp_path, log_path)
        except Exception:
            pass  # fail-open: never block the caller

    def generate_content(
        self,
        model_name: str,
        contents: list,
        generation_config,
    ) -> dict:
        """POST to Gemma endpoint with x-goog-api-key; return inner response dict."""
        import urllib.request as _url_req
        import urllib.error as _url_err

        api_key = self._get_api_key()
        # TASK-20260619-397-P2 (RC-5): per-call ContextVar (see _get_api_key).
        tool_ctx = get_tool_context().lower().strip()
        keep_thoughts = tool_ctx in _GEMMA_KEEP_THOUGHTS_TOOLS

        # Build request body (generativelanguage.googleapis.com schema — no "request" wrapper).
        gen_cfg: dict = {}
        if generation_config:
            try:
                gen_cfg["temperature"] = generation_config.temperature
            except AttributeError:
                pass
            try:
                if generation_config.max_output_tokens:
                    gen_cfg["maxOutputTokens"] = generation_config.max_output_tokens
            except AttributeError:
                pass

        # TASK-20260628-683: Gemma-4 runs server-side reasoning ON by default on v1beta.
        # thinkingLevel:"MINIMAL" suppresses it at the API (probe-proven HTTP 200, ~8x fewer
        # tokens, clean output). DICT form — NOT types.ThinkingConfig (SDK path gated off for
        # Gemma) and NOT thinkingBudget:0 (probe-proven HTTP 400 "not supported").
        gen_cfg["thinkingConfig"] = {"thinkingLevel": "MINIMAL"}

        body_dict: dict = {"contents": contents}
        if gen_cfg:
            body_dict["generationConfig"] = gen_cfg

        body = json.dumps(body_dict).encode()
        # TASK-20260624-602: default 240->45. The cascade makes up to 4 attempts; a 240s
        # per-attempt timeout meant a single stalled 26b attempt could exceed the outer
        # asyncio deadline before the healthy-31b fallback was ever tried. 45s is ample for
        # a real gemma response (~3-8s typical, transient 500s return in ~1s) while letting
        # the FULL cascade fail-fast inside the 240s outer deadline (tools/simple/base.py).
        timeout_s = float(os.environ.get("PAL_HTTP_ATTEMPT_TIMEOUT_S", "45"))

        def _post_once(model: str) -> dict:
            """Single POST to the Gemma endpoint for one model. Raises on failure.

            Classifies failures: HTTPError with a transient code (5xx) is re-raised
            as-is for the cascade to catch; 429 is parsed — transient RPM raises
            _RateLimit429(reason='RATE_LIMIT_EXCEEDED'), daily exhaustion raises
            _RateLimit429(reason='daily'); any other 4xx raises RuntimeError
            (permanent). URLError (timeout/connection) propagates for the cascade.
            """
            url = _GEMMA_ENDPOINT_TMPL.format(model=model)
            req = _url_req.Request(
                url,
                data=body,
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with _url_req.urlopen(req, timeout=timeout_s) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except _url_err.HTTPError as exc:
                if exc.code == 429:
                    try:
                        error_body = json.loads(exc.read().decode("utf-8"))
                    except Exception:
                        error_body = {}
                    reason, reset_ms = _parse_429_reason(error_body)
                    raise _RateLimit429(reason, reset_ms, str(error_body)) from exc
                if exc.code >= 500:
                    # Transient server fault — let the cascade alternate models.
                    raise
                # 4xx (other than 429) = permanent; do NOT enter the cascade.
                raise RuntimeError(
                    f"Gemma API key generateContent HTTP {exc.code} for tool={tool_ctx}. "
                    "Check key validity or quota."
                ) from exc

        # ---- TASK-20260614-291: 26b→31b→26b→31b cascade with exponential backoff ----
        # Recoverable classes (HTTP 5xx, connection timeout/URLError, transient RPM
        # RATE_LIMIT_EXCEEDED) advance to the next model after a growing backoff.
        # PERMANENT classes (4xx≠429, daily quota, auth) raise immediately.
        cascade = _cascade_models()
        last_exc: Optional[Exception] = None
        data = None
        _t0 = time.monotonic()  # TASK-20260624-561: wall-clock start for latency logging
        _winning_model = cascade[0] if cascade else model_name  # track which model succeeded
        for idx, model in enumerate(cascade, start=1):
            wait_ms = _cascade_backoff_ms(idx)
            if wait_ms > 0:
                logger.info(
                    "_GemmaApiKeyAdapter: cascade backoff %dms before attempt %d (%s) tool=%s",
                    wait_ms, idx, model, tool_ctx,
                )
                time.sleep(wait_ms / 1000.0)
            logger.info(
                "paif_model_rotation_event: tool=%s attempt=%d/%d model=%s",
                tool_ctx, idx, len(cascade), model,
            )
            try:
                data = _post_once(model)
                _winning_model = model  # TASK-20260624-561: record the successful model
                break
            except _RateLimit429 as exc:
                # Transient RPM throttle → retriable; daily exhaustion → terminal.
                if exc.reason == "RATE_LIMIT_EXCEEDED":
                    last_exc = exc
                    logger.warning(
                        "_GemmaApiKeyAdapter: transient RPM-429 on attempt %d (%s) tool=%s; "
                        "advancing cascade", idx, model, tool_ctx,
                    )
                    continue
                # daily exhaustion is terminal — log then surface to daily-quota handler.
                self._log_gemma_call(
                    tool_name=tool_ctx,
                    model=model,
                    tokens_in=0,
                    tokens_out=0,
                    latency_ms=(time.monotonic() - _t0) * 1000.0,
                    success=False,
                    error=f"daily_quota_exhausted:{exc}",
                )
                raise
            except _url_err.HTTPError as exc:
                # Only 5xx reaches here (4xx≠429 raised RuntimeError inside _post_once).
                last_exc = exc
                logger.warning(
                    "_GemmaApiKeyAdapter: HTTP %d on attempt %d (%s) tool=%s; advancing cascade",
                    exc.code, idx, model, tool_ctx,
                )
                continue
            except _url_err.URLError as exc:
                # Connection/timeout — transient; advance to the next model.
                last_exc = exc
                logger.warning(
                    "_GemmaApiKeyAdapter: network error on attempt %d (%s) tool=%s: %s; "
                    "advancing cascade", idx, model, tool_ctx, exc,
                )
                continue

        if data is None:
            # All cascade attempts exhausted on recoverable failures — surface final.
            # TASK-20260624-561: log the failure before raising.
            self._log_gemma_call(
                tool_name=tool_ctx,
                model=_winning_model,
                tokens_in=0,
                tokens_out=0,
                latency_ms=(time.monotonic() - _t0) * 1000.0,
                success=False,
                error=f"cascade_exhausted:{last_exc}",
            )
            raise RuntimeError(
                f"Gemma API key generateContent cascade exhausted "
                f"({len(cascade)} attempts) for tool={tool_ctx}: {last_exc}"
            ) from last_exc

        # generativelanguage.googleapis.com returns the response directly (no "response" wrapper).
        candidates = data.get("candidates", [])
        if not candidates:
            logger.warning("_GemmaApiKeyAdapter: empty candidates in response for tool=%s", tool_ctx)

        # Handle thought-part filtering (Gemma returns reasoning in parts with thought:true).
        # For most tools: keep only non-thought parts (clean answer).
        # For reasoning-heavy tools (challenge, debug, codereview, etc.): keep all parts.
        if not keep_thoughts and candidates:
            for cand in candidates:
                parts_list = cand.get("content", {}).get("parts", [])
                non_thought = [p for p in parts_list if not p.get("thought")]
                if non_thought:
                    cand["content"]["parts"] = non_thought
                # If ALL parts are thought parts (shouldn't happen), keep them all
                # to avoid returning empty content.

        logger.debug(
            "_GemmaApiKeyAdapter: tool=%s keep_thoughts=%s candidates=%d",
            tool_ctx, keep_thoughts, len(candidates),
        )
        # TASK-20260624-561: structured success log — parse usageMetadata for token counts.
        try:
            _usage_meta = data.get("usageMetadata", {})
            _tokens_in = int(_usage_meta.get("promptTokenCount") or 0)
            _tokens_out = int(_usage_meta.get("candidatesTokenCount") or 0)
        except Exception:
            _tokens_in, _tokens_out = 0, 0
        self._log_gemma_call(
            tool_name=tool_ctx,
            model=_winning_model,
            tokens_in=_tokens_in,
            tokens_out=_tokens_out,
            latency_ms=(time.monotonic() - _t0) * 1000.0,
            success=True,
        )
        return data


def _build_model_adapter():
    """Factory: return the Gemma 4-26B API-key adapter.

    TASK-20260530-006 — OAuth/Code-Assist (cloudcode-pa.googleapis.com) purge.
    The legacy OAuth adapters (_OAuthCodeAssistAdapterLegacy / ...Shared) and the
    PAL_USE_SHARED_SWITCHER / PAL_USE_API_KEYS=0 / GEMINI_OAUTH_PREFER branches were
    removed; Gemma is now the SOLE auth path (x-goog-api-key, per-tool dedicated keys).
    """
    logger.info("PAL: using Gemma API key adapter (generativelanguage.googleapis.com)")
    return _GemmaApiKeyAdapter()


class GeminiModelProvider(RegistryBackedProviderMixin, ModelProvider):
    """First-party Gemini integration built on the official Google SDK.

    The provider advertises detailed thinking-mode budgets, handles optional
    custom endpoints, and performs image pre-processing before forwarding a
    request to the Gemini APIs.
    """

    REGISTRY_CLASS = GeminiModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    # Thinking mode configurations - percentages of model's max_thinking_tokens
    # These percentages work across all models that support thinking
    THINKING_BUDGETS = {
        "minimal": 0.005,  # 0.5% of max - minimal thinking for fast responses
        "low": 0.08,  # 8% of max - light reasoning tasks
        "medium": 0.33,  # 33% of max - balanced reasoning (default)
        "high": 0.67,  # 67% of max - complex analysis
        "max": 1.0,  # 100% of max - full thinking budget
    }

    def __init__(self, api_key: str, **kwargs):
        """Initialize Gemini provider.

        TASK-20260530-006: OAuth/Code-Assist purged. The model adapter is always
        the Gemma 4-26B API-key adapter (x-goog-api-key, per-tool dedicated keys).
        The dedicated key is read at request time, so a missing key surfaces loudly
        on the first call rather than silently at startup.
        """
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._client = None
        self._token_counters = {}  # Cache for token counting
        self._base_url = kwargs.get("base_url", None)  # Optional custom endpoint
        self._timeout_override = self._resolve_http_timeout()
        self._invalidate_capability_cache()
        # Gemma API-key adapter is the sole auth path. Errors that can be detected
        # at construction surface here; per-tool key lookup happens at call time.
        self._model_adapter = None
        try:
            self._model_adapter = _build_model_adapter()
        except (RuntimeError, ValueError) as exc:
            logger.warning("Gemini Gemma adapter unavailable: %s", exc)

    # ------------------------------------------------------------------
    # Capability surface
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Client access
    # ------------------------------------------------------------------

    @property
    def client(self):
        """Lazy initialization of the official Gemini SDK client (API-key path).

        Only used when a GEMINI_API_KEY is configured. The active PAL path is the
        Gemma API-key adapter (self._model_adapter); the SDK client is the legacy
        Developer-API path and is unused when no API key is set.
        """
        if self._client is None:
            http_options_kwargs: dict[str, object] = {}
            if self._base_url:
                http_options_kwargs["base_url"] = self._base_url
            if self._timeout_override is not None:
                http_options_kwargs["timeout"] = self._timeout_override

            http_options = types.HttpOptions(**http_options_kwargs) if http_options_kwargs else None

            if self.api_key:
                if http_options:
                    logger.debug(
                        "Initializing Gemini client with API key + options: base_url=%s timeout=%s",
                        http_options_kwargs.get("base_url"),
                        http_options_kwargs.get("timeout"),
                    )
                    self._client = genai.Client(api_key=self.api_key, http_options=http_options)
                else:
                    self._client = genai.Client(api_key=self.api_key)
            else:
                raise RuntimeError(
                    "Gemini SDK client requires GEMINI_API_KEY. The active PAL path "
                    "is the Gemma API-key adapter (per-tool dedicated keys)."
                )

        return self._client

    def _resolve_http_timeout(self) -> Optional[float]:
        """Compute timeout override from shared custom timeout environment variables."""

        timeouts: list[float] = []
        for env_var in [
            "CUSTOM_CONNECT_TIMEOUT",
            "CUSTOM_READ_TIMEOUT",
            "CUSTOM_WRITE_TIMEOUT",
            "CUSTOM_POOL_TIMEOUT",
        ]:
            raw_value = get_env(env_var)
            if raw_value:
                try:
                    timeouts.append(float(raw_value))
                except (TypeError, ValueError):
                    logger.warning("Invalid %s value '%s'; ignoring.", env_var, raw_value)

        if timeouts:
            # Use the largest timeout to best approximate long-running requests
            resolved = max(timeouts)
            logger.debug("Using custom Gemini HTTP timeout: %ss", resolved)
            return resolved

        return None

    # ------------------------------------------------------------------
    # Request execution
    # ------------------------------------------------------------------

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_output_tokens: Optional[int] = None,
        thinking_mode: str = "medium",
        images: Optional[list[str]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Generate content using Gemini model.

        Args:
            prompt: The main user prompt/query to send to the model
            model_name: Canonical model name or its alias (e.g., "gemini-2.5-pro", "flash", "pro")
            system_prompt: Optional system instructions to prepend to the prompt for context/behavior
            temperature: Controls randomness in generation (0.0=deterministic, 1.0=creative), default 0.3
            max_output_tokens: Optional maximum number of tokens to generate in the response
            thinking_mode: Thinking budget level for models that support it ("minimal", "low", "medium", "high", "max"), default "medium"
            images: Optional list of image paths or data URLs to include with the prompt (for vision models)
            **kwargs: Additional keyword arguments (reserved for future use)

        Returns:
            ModelResponse: Contains the generated content, token usage stats, model metadata, and safety information
        """
        # Validate parameters and fetch capabilities
        self.validate_parameters(model_name, temperature)
        capabilities = self.get_capabilities(model_name)
        capability_map = self.get_all_model_capabilities()

        resolved_model_name = self._resolve_model_name(model_name)

        # Prepare content parts (text and potentially images)
        parts = []

        # Add system and user prompts as text
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        parts.append({"text": full_prompt})

        # Add images if provided and model supports vision
        if images and capabilities.supports_images:
            for image_path in images:
                try:
                    image_part = self._process_image(image_path)
                    if image_part:
                        parts.append(image_part)
                except Exception as e:
                    logger.warning(f"Failed to process image {image_path}: {e}")
                    # Continue with other images and text
                    continue
        elif images and not capabilities.supports_images:
            logger.warning(f"Model {resolved_model_name} does not support images, ignoring {len(images)} image(s)")

        # Create contents structure
        contents = [{"parts": parts}]

        # Gemini 3 Pro Preview currently rejects medium thinking budgets; bump to high.
        effective_thinking_mode = thinking_mode
        if resolved_model_name == "gemini-3-pro-preview" and thinking_mode == "medium":
            logger.debug(
                "Overriding thinking mode 'medium' with 'high' for %s due to launch limitation",
                resolved_model_name,
            )
            effective_thinking_mode = "high"

        # Prepare generation config
        generation_config = types.GenerateContentConfig(
            temperature=temperature,
            candidate_count=1,
        )

        # Add max output tokens if specified
        if max_output_tokens:
            generation_config.max_output_tokens = max_output_tokens

        # Add thinking configuration for models that support it
        if capabilities.supports_extended_thinking and effective_thinking_mode in self.THINKING_BUDGETS:
            # Get model's max thinking tokens and calculate actual budget
            model_config = capability_map.get(resolved_model_name)
            if model_config and model_config.max_thinking_tokens > 0:
                max_thinking_tokens = model_config.max_thinking_tokens
                actual_thinking_budget = int(max_thinking_tokens * self.THINKING_BUDGETS[effective_thinking_mode])
                generation_config.thinking_config = types.ThinkingConfig(thinking_budget=actual_thinking_budget)

        # Retry logic with progressive delays.
        # TASK-20260614-291: when the Gemma API-key adapter is active it owns the FULL
        # 26b→31b→26b→31b cascade + exponential backoff internally. The outer retry loop
        # must NOT re-cascade (that would multiply to 16 HTTP calls). So with the adapter
        # the outer loop is a single pass (cascade is the sole retry authority); the SDK
        # client path (no adapter) keeps the original 4-attempt progressive backoff.
        if self._model_adapter is not None:
            max_retries = 1
            retry_delays = []
        else:
            max_retries = 4  # Total of 4 attempts
            retry_delays = [1, 3, 5, 8]  # Progressive delays: 1s, 3s, 5s, 8s
        attempt_counter = {"value": 0}

        def _attempt() -> ModelResponse:
            attempt_counter["value"] += 1
            if self._model_adapter is not None:
                # --- Gemma API-key adapter path (no SDK client) ---
                inner = self._model_adapter.generate_content(
                    resolved_model_name, contents, generation_config
                )
                # Guard: deadline/degraded path returns a graceful string; wrap it.
                if isinstance(inner, str):
                    return ModelResponse(
                        content=inner,
                        usage={},
                        model_name=resolved_model_name,
                        friendly_name="Gemini",
                        provider=ProviderType.GOOGLE,
                        metadata={"finish_reason": "STOP", "is_blocked_by_safety": False},
    
                    )
                candidates = inner.get("candidates", [])
                usage_meta = inner.get("usageMetadata", {})
                usage: dict[str, int] = {}
                if usage_meta.get("promptTokenCount") is not None:
                    usage["input_tokens"] = usage_meta["promptTokenCount"]
                if usage_meta.get("candidatesTokenCount") is not None:
                    usage["output_tokens"] = usage_meta["candidatesTokenCount"]
                if "input_tokens" in usage and "output_tokens" in usage:
                    usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
                text = None
                finish_reason_str = "STOP"
                if candidates:
                    cand = candidates[0]
                    parts_list = cand.get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts_list) or None
                    finish_reason_str = cand.get("finishReason", "STOP")
                return ModelResponse(
                    content=text,
                    usage=usage,
                    model_name=resolved_model_name,
                    friendly_name="Gemini",
                    provider=ProviderType.GOOGLE,
                    metadata={
                        "thinking_mode": effective_thinking_mode if capabilities.supports_extended_thinking else None,
                        "finish_reason": finish_reason_str,
                        "is_blocked_by_safety": False,
                        "safety_feedback": None,
                    },
                )
            response = self.client.models.generate_content(
                model=resolved_model_name,
                contents=contents,
                config=generation_config,
            )

            usage = self._extract_usage(response)

            finish_reason_str = "UNKNOWN"
            is_blocked_by_safety = False
            safety_feedback_details = None

            if response.candidates:
                candidate = response.candidates[0]

                try:
                    finish_reason_enum = candidate.finish_reason
                    if finish_reason_enum:
                        try:
                            finish_reason_str = finish_reason_enum.name
                        except AttributeError:
                            finish_reason_str = str(finish_reason_enum)
                    else:
                        finish_reason_str = "STOP"
                except AttributeError:
                    finish_reason_str = "STOP"

                if not response.text:
                    try:
                        safety_ratings = candidate.safety_ratings
                        if safety_ratings:
                            for rating in safety_ratings:
                                try:
                                    if rating.blocked:
                                        is_blocked_by_safety = True
                                        category_name = "UNKNOWN"
                                        probability_name = "UNKNOWN"

                                        try:
                                            category_name = rating.category.name
                                        except (AttributeError, TypeError):
                                            pass

                                        try:
                                            probability_name = rating.probability.name
                                        except (AttributeError, TypeError):
                                            pass

                                        safety_feedback_details = (
                                            f"Category: {category_name}, Probability: {probability_name}"
                                        )
                                        break
                                except (AttributeError, TypeError):
                                    continue
                    except (AttributeError, TypeError):
                        pass

            elif response.candidates is not None and len(response.candidates) == 0:
                is_blocked_by_safety = True
                finish_reason_str = "SAFETY"
                safety_feedback_details = "Prompt blocked, reason unavailable"

                try:
                    prompt_feedback = response.prompt_feedback
                    if prompt_feedback and prompt_feedback.block_reason:
                        try:
                            block_reason_name = prompt_feedback.block_reason.name
                        except AttributeError:
                            block_reason_name = str(prompt_feedback.block_reason)
                        safety_feedback_details = f"Prompt blocked, reason: {block_reason_name}"
                except (AttributeError, TypeError):
                    pass

            return ModelResponse(
                content=response.text,
                usage=usage,
                model_name=resolved_model_name,
                friendly_name="Gemini",
                provider=ProviderType.GOOGLE,
                metadata={
                    "thinking_mode": effective_thinking_mode if capabilities.supports_extended_thinking else None,
                    "finish_reason": finish_reason_str,
                    "is_blocked_by_safety": is_blocked_by_safety,
                    "safety_feedback": safety_feedback_details,
                },
            )

        try:
            _retries_result = self._run_with_retries(
                operation=_attempt,
                max_attempts=max_retries,
                delays=retry_delays,
                log_prefix=f"Gemini API ({resolved_model_name})",
            )
            # Guard: base.py deadline also returns a graceful string; wrap it.
            if isinstance(_retries_result, str):
                return ModelResponse(
                    content=_retries_result,
                    usage={},
                    model_name=resolved_model_name,
                    friendly_name="Gemini",
                    provider=ProviderType.GOOGLE,
                    metadata={"finish_reason": "STOP", "is_blocked_by_safety": False},

                )
            return _retries_result
        except Exception as exc:
            # TASK-20260530-006: OAuth/Code-Assist 429 fallback removed. Gemma is the
            # sole path; on exhaustion we surface the error (no OAuth re-route).
            attempts = max(attempt_counter["value"], 1)
            error_msg = (
                f"Gemini API error for model {resolved_model_name} after {attempts} attempt"
                f"{'s' if attempts > 1 else ''}: {exc}"
            )
            raise RuntimeError(error_msg) from exc

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.GOOGLE

    def _extract_usage(self, response) -> dict[str, int]:
        """Extract token usage from Gemini response."""
        usage = {}

        # Try to extract usage metadata from response
        # Note: The actual structure depends on the SDK version and response format
        try:
            metadata = response.usage_metadata
            if metadata:
                # Extract token counts with explicit None checks
                input_tokens = None
                output_tokens = None

                try:
                    value = metadata.prompt_token_count
                    if value is not None:
                        input_tokens = value
                        usage["input_tokens"] = value
                except (AttributeError, TypeError):
                    pass

                try:
                    value = metadata.candidates_token_count
                    if value is not None:
                        output_tokens = value
                        usage["output_tokens"] = value
                except (AttributeError, TypeError):
                    pass

                # Calculate total only if both values are available and valid
                if input_tokens is not None and output_tokens is not None:
                    usage["total_tokens"] = input_tokens + output_tokens
        except (AttributeError, TypeError):
            # response doesn't have usage_metadata
            pass

        return usage

    def _is_error_retryable(self, error: Exception) -> bool:
        """Determine if an error should be retried based on structured error codes.

        Uses Gemini API error structure instead of text pattern matching for reliability.

        Args:
            error: Exception from Gemini API call

        Returns:
            True if error should be retried, False otherwise
        """
        error_str = str(error).lower()

        # Check for 429 errors first - these need special handling
        if "429" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
            # For Gemini, check for specific non-retryable error indicators
            # These typically indicate permanent failures or quota/size limits
            non_retryable_indicators = [
                "quota exceeded",
                "resource exhausted",
                "context length",
                "token limit",
                "request too large",
                "invalid request",
                "quota_exceeded",
                "resource_exhausted",
            ]

            # Also check if this is a structured error from Gemini SDK
            try:
                # Try to access error details if available
                error_details = None
                try:
                    error_details = error.details
                except AttributeError:
                    try:
                        error_details = error.reason
                    except AttributeError:
                        pass

                if error_details:
                    error_details_str = str(error_details).lower()
                    # Check for non-retryable error codes/reasons
                    if any(indicator in error_details_str for indicator in non_retryable_indicators):
                        logger.debug(f"Non-retryable Gemini error: {error_details}")
                        return False
            except Exception:
                pass

            # Check main error string for non-retryable patterns
            if any(indicator in error_str for indicator in non_retryable_indicators):
                logger.debug(f"Non-retryable Gemini error based on message: {error_str[:200]}...")
                return False

            # If it's a 429/quota error but doesn't match non-retryable patterns, it might be retryable rate limiting
            logger.debug(f"Retryable Gemini rate limiting error: {error_str[:100]}...")
            return True

        # For non-429 errors, check if they're retryable
        retryable_indicators = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "unavailable",
            "retry",
            "internal error",
            "408",  # Request timeout
            "500",  # Internal server error
            "502",  # Bad gateway
            "503",  # Service unavailable
            "504",  # Gateway timeout
            "ssl",  # SSL errors
            "handshake",  # Handshake failures
        ]

        return any(indicator in error_str for indicator in retryable_indicators)

    def _process_image(self, image_path: str) -> Optional[dict]:
        """Process an image for Gemini API."""
        try:
            # Use base class validation
            image_bytes, mime_type = validate_image(image_path)

            # For data URLs, extract the base64 data directly
            if image_path.startswith("data:"):
                # Extract base64 data from data URL
                _, data = image_path.split(",", 1)
                return {"inline_data": {"mime_type": mime_type, "data": data}}
            else:
                # For file paths, encode the bytes
                image_data = base64.b64encode(image_bytes).decode()
                return {"inline_data": {"mime_type": mime_type, "data": image_data}}

        except ValueError as e:
            logger.warning(str(e))
            return None
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            return None

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get Gemini's preferred model for a given category from allowed models.

        Args:
            category: The tool category requiring a model
            allowed_models: Pre-filtered list of models allowed by restrictions

        Returns:
            Preferred model name or None
        """
        from tools.models import ToolModelCategory

        if not allowed_models:
            return None

        # TASK-20260613-204 (Hamad NO-FLASH HARD RULE, msg-46143; spec §7.4):
        # get_preferred_model() must NEVER return a Gemini Flash / Flash-Lite model.
        # The live _GemmaApiKeyAdapter ignores model_name and always POSTs _GEMMA_MODEL
        # ('gemma-4-26b-a4b-it'); the 31b sibling is reached ONLY via the adapter's
        # one-shot HTTP-500 fallback, never through this selection helper. Returning the
        # canonical Gemma model here makes the advertised name match what is actually
        # called. All "flash" preference branches are removed; any Flash member of
        # allowed_models is filtered out so no caller-restriction can resurrect Flash.
        flash_free = [m for m in allowed_models if "flash" not in m.lower()]

        # Canonical Gemma primary is the preferred answer when permitted by restrictions.
        if _GEMMA_MODEL in flash_free:
            return _GEMMA_MODEL

        if not flash_free:
            # allowed_models contained only Flash variants → none are permissible.
            # NO-FLASH is absolute: surface "no model" rather than a banned Flash.
            return None

        capability_map = self.get_all_model_capabilities()

        # Helper to find best model from candidates
        def find_best(candidates: list[str]) -> Optional[str]:
            """Return best model from candidates (sorted for consistency)."""
            return sorted(candidates, reverse=True)[0] if candidates else None

        if category == ToolModelCategory.EXTENDED_REASONING:
            # For extended reasoning, prefer models with thinking support
            # First try Pro models that support thinking
            pro_thinking = [
                m
                for m in flash_free
                if "pro" in m and m in capability_map and capability_map[m].supports_extended_thinking
            ]
            if pro_thinking:
                return find_best(pro_thinking)

            # Then any model that supports thinking
            any_thinking = [
                m for m in flash_free if m in capability_map and capability_map[m].supports_extended_thinking
            ]
            if any_thinking:
                return find_best(any_thinking)

            # Finally, just prefer Pro models even without thinking
            pro_models = [m for m in flash_free if "pro" in m]
            if pro_models:
                return find_best(pro_models)

        # Default for BALANCED / FAST_RESPONSE / fallback: NO Flash. Prefer Pro, then
        # any non-Flash model. Flash is never a candidate.
        pro_models = [m for m in flash_free if "pro" in m]
        if pro_models:
            return find_best(pro_models)

        # Ultimate fallback to best available non-Flash model.
        return find_best(flash_free)


# Load registry data at import time for registry consumers
GeminiModelProvider._ensure_registry()
