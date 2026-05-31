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

from utils.env import get_env
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

    Returns:
        (reason_str, reset_after_ms): reason is 'RATE_LIMIT_EXCEEDED' for RPM
        throttles, 'daily' for daily quota exhaustion. reset_after_ms from
        'reset after Ns' hint in the message (0 if absent).
    """
    msg = (error_body.get("error", {}).get("message", "") or "").lower()
    # Look for "reset after Ns" hint (gemini-chain.js TASK-179 pattern)
    import re
    m = re.search(r"reset\s+after\s+(\d+(?:\.\d+)?)\s*s", msg)
    reset_ms = int(float(m.group(1)) * 1000) if m else 0

    # RATE_LIMIT_EXCEEDED = RPM throttle (short cooldown)
    # "quota exceeded" / "resource exhausted" without reset hint = daily
    if "rate_limit_exceeded" in msg or (reset_ms > 0 and reset_ms < 300_000):
        return "RATE_LIMIT_EXCEEDED", reset_ms
    return "daily", reset_ms


# ---------------------------------------------------------------------------
# TASK-20260529-298 — Gemma 4-26B API key adapter
#
# Replaces OAuth/Code Assist before June 18 2026 deadline.
# Endpoint: generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent
# Auth: x-goog-api-key header (NOT Bearer).
# Activation: PAL_USE_API_KEYS=1 in PAL MCP env.
# Per-tool key routing: reads PAL_TOOL_CONTEXT env var set by server.py at dispatch time.
# Thought-part handling: Gemma returns reasoning in parts with thought:true; strip for clean
#   verdicts EXCEPT for tools that benefit from full reasoning (challenge, debug, codereview).
# ---------------------------------------------------------------------------

_GEMMA_MODEL = "gemma-4-26b-a4b-it"
_GEMMA_ENDPOINT_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

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
        tool_ctx = os.environ.get("PAL_TOOL_CONTEXT", "").lower().strip()
        env_var = _GEMMA_TOOL_KEY_MAP.get(tool_ctx, "GEMINI_API_KEY_GENERAL")
        key = os.environ.get(env_var, "")
        if not key:
            raise RuntimeError(
                f"_GemmaApiKeyAdapter: dedicated key {env_var} is missing for "
                f"tool context '{tool_ctx}'. Set {env_var} in PAL MCP env. "
                f"Cross-endpoint key fallback is BANNED (Hamad msg-34515)."
            )
        return key

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
        tool_ctx = os.environ.get("PAL_TOOL_CONTEXT", "").lower().strip()
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

        body_dict: dict = {"contents": contents}
        if gen_cfg:
            body_dict["generationConfig"] = gen_cfg

        body = json.dumps(body_dict).encode()
        url = _GEMMA_ENDPOINT_TMPL.format(model=_GEMMA_MODEL)

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
            timeout_s = float(os.environ.get("PAL_HTTP_ATTEMPT_TIMEOUT_S", "240"))
            with _url_req.urlopen(req, timeout=timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except _url_err.HTTPError as exc:
            if exc.code == 429:
                try:
                    error_body = json.loads(exc.read().decode("utf-8"))
                except Exception:
                    error_body = {}
                reason, reset_ms = _parse_429_reason(error_body)
                raise _RateLimit429(reason, reset_ms, str(error_body)) from exc
            raise RuntimeError(
                f"Gemma API key generateContent HTTP {exc.code} for tool={tool_ctx}. "
                "Check key validity or quota."
            ) from exc
        except _url_err.URLError as exc:
            raise RuntimeError(f"Gemma API key generateContent network error: {exc}") from exc

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

        # Retry logic with progressive delays
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
                for m in allowed_models
                if "pro" in m and m in capability_map and capability_map[m].supports_extended_thinking
            ]
            if pro_thinking:
                return find_best(pro_thinking)

            # Then any model that supports thinking
            any_thinking = [
                m for m in allowed_models if m in capability_map and capability_map[m].supports_extended_thinking
            ]
            if any_thinking:
                return find_best(any_thinking)

            # Finally, just prefer Pro models even without thinking
            pro_models = [m for m in allowed_models if "pro" in m]
            if pro_models:
                return find_best(pro_models)

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer Flash models for speed
            flash_models = [m for m in allowed_models if "flash" in m]
            if flash_models:
                return find_best(flash_models)

        # Default for BALANCED or as fallback
        # Prefer Flash for balanced use, then Pro, then anything
        flash_models = [m for m in allowed_models if "flash" in m]
        if flash_models:
            return find_best(flash_models)

        pro_models = [m for m in allowed_models if "pro" in m]
        if pro_models:
            return find_best(pro_models)

        # Ultimate fallback to best available model
        return find_best(allowed_models)


# Load registry data at import time for registry consumers
GeminiModelProvider._ensure_registry()
