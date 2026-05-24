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
from .gemini_switcher_client import GeminiSwitcherClient, _atomic_write_json
from .registries.gemini import GeminiModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ModelResponse, ProviderType

logger = logging.getLogger(__name__)

# Lazy import to avoid circular; GeminiAccountExhausted lives in providers/__init__.py
# We import it inside the method to keep the module importable before __init__ resolves.
def _get_gemini_account_exhausted():
    from providers import GeminiAccountExhausted  # noqa: PLC0415
    return GeminiAccountExhausted

# ---------------------------------------------------------------------------
# OAuth / Code Assist constants (Gemini CLI installed-app credentials)
#
# Background (discovered during implementation — spec §Root cause):
#   The Gemini Developer API (generativelanguage.googleapis.com) only accepts
#   x-goog-api-key auth.  User OAuth tokens work ONLY with the Gemini Code
#   Assist API (cloudcode-pa.googleapis.com/v1internal), which is the actual
#   backend used by the Gemini CLI for its "oauth-personal" auth type.
#
#   The OAuth client credentials below are the PUBLIC installed-app credentials
#   embedded verbatim in the open-source Gemini CLI npm package.  They identify
#   the application (not the user) — analogous to a client_id in any OAuth
#   installed-app flow.  The user's actual credentials are the refresh_token
#   stored in ~/.gemini/oauth_creds.json by `gemini auth login`.
# ---------------------------------------------------------------------------
_GEMINI_CLI_CLIENT_ID = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
# Public Gemini CLI OAuth client — see https://github.com/google-gemini/gemini-cli
_GEMINI_CLI_CLIENT_SECRET = os.environ.get("GEMINI_CLI_CLIENT_SECRET", "<REDACTED_PUBLIC_CLI_SECRET>")  # noqa: S105 — public installed-app secret
_OAUTH_TOKEN_URI = "https://oauth2.googleapis.com/token"
_CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com"
_CODE_ASSIST_VERSION = "v1internal"
_OAUTH_CREDS_PATH = os.path.join(os.path.expanduser("~"), ".gemini", "oauth_creds.json")
# Refresh when < 5 minutes remain (expiry_date is epoch milliseconds in JSON)
_EXPIRY_BUFFER_MS = 5 * 60 * 1000

# ---------------------------------------------------------------------------
# TASK-20260528-218 — 4-combo rotation constants (mirror gemini-chain.js).
#   Cycle order: Flash-A -> Lite-A -> Flash-B -> Lite-B (combo state index 0..3).
#   Every non-200 advances to the next combo immediately (wait=0); per-combo
#   cooldownUntil prevents re-hitting a throttled combo within a cycle. Only a
#   fully-exhausted cycle triggers a single bounded wait, capped at MAX_FULL_CYCLES.
# ---------------------------------------------------------------------------
_FLASH = "gemini-2.5-flash"
_LITE = "gemini-2.5-flash-lite"
# (account_index, model) in the canonical order — matches gemini-combo-state.json combos[].
_COMBO_ORDER = [(0, _FLASH), (0, _LITE), (1, _FLASH), (1, _LITE)]
_CAPACITY_COOLDOWN_MS = int(os.environ.get("GEMINI_CAPACITY_COOLDOWN_MS", "90000"))
_SERVER_BLOCKED_STREAK_N = int(os.environ.get("GEMINI_SERVER_BLOCKED_STREAK_N", "2"))
_MAX_FULL_CYCLES = int(os.environ.get("GEMINI_MAX_FULL_CYCLES", "2"))
_RPM_WAIT_DEFAULT_MS = int(os.environ.get("GEMINI_RPM_WAIT_DEFAULT_MS", "13000"))
_FULL_CYCLE_WAIT_CAP_MS = int(os.environ.get("GEMINI_FULL_CYCLE_WAIT_CAP_MS", "20000"))
_MAX_AUTH_FAILURES = int(os.environ.get("GEMINI_MAX_AUTH_FAILURES", "12"))
# Daily-quota reason allow-list (mirror gemini-chain.js DAILY_REASONS — TASK-20260525-031).
_DAILY_REASONS = ("QUOTA_EXHAUSTED", "RESOURCE_EXHAUSTED")


def _ms_until_next_utc_midnight() -> int:
    """Milliseconds from now until the next UTC midnight (daily-quota reset)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    nxt = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((nxt - now).total_seconds() * 1000)


def _classify_429(reason: str, reset_after_ms: int) -> str:
    """Classify a 429 into 'rpm' | 'capacity' | 'daily' (mirror gemini-chain.js
    classifyThrottle L693-708). rpm = RATE_LIMIT_EXCEEDED or unknown-with-hint;
    daily = allow-listed quota reasons; everything else = transient capacity."""
    if reason == "RATE_LIMIT_EXCEEDED" or (not reason and reset_after_ms > 0):
        return "rpm"
    if reason in _DAILY_REASONS:
        return "daily"
    return "capacity"


class _OAuthCodeAssistAdapterLegacy:
    """Thin adapter that calls the Gemini Code Assist API using user OAuth credentials.

    LEGACY path — used when PAL_USE_SHARED_SWITCHER != '1'.
    Per-instance credential caches (access_token, expiry_ms, project_id, refresh_token).
    This class is kept intact for rollback safety during the Phase 3 soak period.

    This replicates the auth path the Gemini CLI uses for "oauth-personal" auth:
      1. Read refresh_token from ~/.gemini/oauth_creds.json
      2. Exchange for a fresh access_token via oauth2.googleapis.com/token
      3. POST to cloudcode-pa.googleapis.com/v1internal:generateContent with Bearer auth

    The Code Assist API request/response schema differs from the Developer API —
    contents are wrapped under a "request" field and the project ID is required.
    Responses unwrap from response.candidates[*] (same shape as Developer API).

    SECURITY: access_token and refresh_token values are NEVER logged.
    """

    def __init__(self, creds_path: str = _OAUTH_CREDS_PATH) -> None:
        self._creds_path = creds_path
        self._access_token: Optional[str] = None
        self._expiry_ms: int = 0  # epoch-ms; 0 means already expired
        self._project_id: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._load_creds_file()

    def _load_creds_file(self) -> None:
        """Read refresh_token (and cached access_token if still fresh) from disk."""
        if not os.path.exists(self._creds_path):
            raise FileNotFoundError(
                f"OAuth credentials not found at {self._creds_path}. "
                "Run: gemini auth login"
            )
        try:
            with open(self._creds_path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to parse OAuth credentials at {self._creds_path}: {exc}"
            ) from exc

        self._refresh_token = raw.get("refresh_token")
        if not self._refresh_token:
            raise ValueError(
                "OAuth refresh_token missing from credentials. "
                "Re-authenticate with: gemini auth login"
            )
        # Use cached access_token only when still fresh (> 5-min buffer remaining)
        cached_token = raw.get("access_token")
        cached_expiry = int(raw.get("expiry_date", 0))
        now_ms = int(datetime.datetime.utcnow().timestamp() * 1000)
        if cached_token and (cached_expiry - now_ms) > _EXPIRY_BUFFER_MS:
            self._access_token = cached_token
            self._expiry_ms = cached_expiry

    def _get_access_token(self) -> str:
        """Return a valid access_token, refreshing if expired or near expiry.

        Raises:
            RuntimeError: If the token refresh request fails.
            ValueError: If refresh_token has expired (re-auth required).
        """
        import requests as _requests

        now_ms = int(datetime.datetime.utcnow().timestamp() * 1000)
        if self._access_token and (self._expiry_ms - now_ms) > _EXPIRY_BUFFER_MS:
            return self._access_token  # still fresh

        logger.debug("OAuth access_token expired or near expiry — refreshing")
        try:
            resp = _requests.post(
                _OAUTH_TOKEN_URI,
                data={
                    "client_id": _GEMINI_CLI_CLIENT_ID,
                    "client_secret": _GEMINI_CLI_CLIENT_SECRET,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=15,
            )
        except Exception as exc:
            raise RuntimeError(f"OAuth token refresh network error: {exc}") from exc

        if resp.status_code == 401:
            raise ValueError(
                "OAuth refresh_token has expired or been revoked. "
                "Re-authenticate with: gemini auth login"
            )
        if resp.status_code != 200:
            # Do NOT include response body — may contain partial token values
            raise RuntimeError(
                f"OAuth token refresh failed with HTTP {resp.status_code}. "
                "Run: gemini auth login"
            )

        token_data = resp.json()
        new_token = token_data.get("access_token")
        if not new_token:
            raise RuntimeError(
                "OAuth token refresh returned no access_token. "
                "Run: gemini auth login"
            )
        # SECURITY: new_token value is NOT logged
        expires_in = int(token_data.get("expires_in", 3600))
        self._access_token = new_token
        self._expiry_ms = now_ms + expires_in * 1000

        # Persist refreshed token to disk so next process start uses it
        try:
            with open(self._creds_path, encoding="utf-8") as fh:
                raw = json.load(fh)
            raw["access_token"] = new_token
            raw["expiry_date"] = self._expiry_ms
            with open(self._creds_path, "w", encoding="utf-8") as fh:
                json.dump(raw, fh, indent=2)
        except Exception as exc:
            logger.warning("Could not persist refreshed OAuth token to disk: %s", exc)

        return self._access_token

    def _get_project_id(self) -> str:
        """Return the Code Assist project ID for this account (cached after first call)."""
        import requests as _requests

        if self._project_id:
            return self._project_id

        token = self._get_access_token()
        url = f"{_CODE_ASSIST_ENDPOINT}/{_CODE_ASSIST_VERSION}:loadCodeAssist"
        try:
            resp = _requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "metadata": {
                        "ideType": "IDE_UNSPECIFIED",
                        "platform": "PLATFORM_UNSPECIFIED",
                        "pluginType": "GEMINI",
                    }
                },
                timeout=20,
            )
        except Exception as exc:
            raise RuntimeError(f"Code Assist loadCodeAssist network error: {exc}") from exc

        if resp.status_code != 200:
            raise RuntimeError(
                f"Code Assist loadCodeAssist failed with HTTP {resp.status_code}. "
                "Ensure the account has Gemini Code Assist enabled."
            )

        data = resp.json()
        project = data.get("cloudaicompanionProject")
        if not project:
            raise RuntimeError(
                "Code Assist loadCodeAssist did not return a project ID. "
                "Run: gemini auth login and ensure Gemini Code Assist is enabled."
            )
        self._project_id = project
        logger.info("Code Assist project ID resolved: %s", project)
        return self._project_id

    def generate_content(
        self,
        model_name: str,
        contents: list,
        generation_config,
    ) -> dict:
        """POST to Code Assist generateContent and return the inner response dict.

        Args:
            model_name: Resolved Gemini model name (e.g. "gemini-2.5-flash").
            contents: List of content dicts in Vertex AI format.
            generation_config: GenerateContentConfig object (temperature, tokens, etc.)

        Returns:
            The inner response dict (same shape as Developer API response).

        Raises:
            RuntimeError: On HTTP errors or malformed responses.
        """
        import uuid

        import requests as _requests

        token = self._get_access_token()
        project = self._get_project_id()

        # Build generationConfig dict from the SDK object
        gen_cfg: dict = {}
        if generation_config:
            try:
                gen_cfg["temperature"] = generation_config.temperature
            except AttributeError:
                pass
            try:
                gen_cfg["candidateCount"] = generation_config.candidate_count
            except AttributeError:
                pass
            try:
                if generation_config.max_output_tokens:
                    gen_cfg["maxOutputTokens"] = generation_config.max_output_tokens
            except AttributeError:
                pass
            try:
                if generation_config.thinking_config:
                    gen_cfg["thinkingConfig"] = {
                        "thinkingBudget": generation_config.thinking_config.thinking_budget
                    }
            except AttributeError:
                pass

        body = {
            "model": model_name,
            "project": project,
            "user_prompt_id": str(uuid.uuid4()),
            "request": {
                "contents": contents,
                "generationConfig": gen_cfg,
            },
        }

        url = f"{_CODE_ASSIST_ENDPOINT}/{_CODE_ASSIST_VERSION}:generateContent"
        try:
            resp = _requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=120,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Code Assist generateContent network error: {exc}"
            ) from exc

        if resp.status_code == 429:
            error_msg = resp.json().get("error", {}).get("message", "quota exhausted")
            raise RuntimeError(f"429 {error_msg}")

        if resp.status_code != 200:
            raise RuntimeError(
                f"Code Assist generateContent HTTP {resp.status_code}. "
                "Check quota or re-authenticate with: gemini auth login"
            )

        data = resp.json()
        # Unwrap: Code Assist wraps the actual response under "response" key
        inner = data.get("response", data)
        return inner


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


class _OAuthCodeAssistAdapterShared:
    """Shared-switcher Code Assist adapter.

    Used when PAL_USE_SHARED_SWITCHER='1'.
    Drops all per-instance credential caches.
    Routes every call through GeminiSwitcherClient (state consumer, never rotator).

    TASK-20260528-218 — 4-COMBO ROTATION (replaces same-account wait+retry):
      Cycles Flash-A -> Lite-A -> Flash-B -> Lite-B; first 200 wins. Every non-200
      ADVANCES to the next combo immediately (wait=0). Per-combo cooldownUntil
      timestamps (shared gemini-combo-state.json) prevent re-hitting a throttled
      combo. Error -> action matrix (Hamad msg-33261):
        200       -> use it; record_success(fp)
        429 rpm   -> combo cooldown = now + resetAfterMs; ADVANCE
        429 cap   -> combo cooldown = now + CAPACITY_COOLDOWN_MS; ADVANCE
        429 daily -> mark daily-exhausted till UTC midnight; ADVANCE (all 4 -> exhausted)
        5xx       -> ADVANCE; 2 consecutive same-account 5xx -> skip that account's OTHER combo
        401       -> one-shot token refresh for that account; still 401 -> skip account's combos
        403/400/IAM -> ADVANCE (permanent); hard-bail only when all 4 permanently dead
      Only a fully-cooling cycle triggers ONE bounded wait (shortest cooldown,
      capped); capped at GEMINI_MAX_FULL_CYCLES.

    SECURITY: access_token values are NEVER logged.
    """

    _FLASH_PRIMARY = "gemini-2.5-flash"
    _FLASH_LITE = "gemini-2.5-flash-lite"

    def __init__(self, model_name: str) -> None:
        self._model = model_name
        self._switcher = GeminiSwitcherClient()

    def generate_content(
        self,
        model_name: str,
        contents: list,
        generation_config,
    ) -> dict:
        """POST to Code Assist via the 4-combo rotation cycle; return the inner dict.

        Cycles Flash-A -> Lite-A -> Flash-B -> Lite-B (first 200 wins). The
        `model_name` arg is honored for the FIRST attempt's model only when it
        differs from Flash (callers requesting Lite enter at the matching combo);
        otherwise the canonical order is used. See class docstring for the matrix.

        Raises:
            GeminiAccountExhausted: When all 4 combos are daily-exhausted.
            RuntimeError: When all 4 combos are permanently dead (auth/IAM/cycle-cap).
        """
        return self._run_combo_cycle(model_name, contents, generation_config)

    def _run_combo_cycle(self, requested_model: str, contents: list, generation_config) -> dict:
        """Execute the bounded 4-combo rotation. Single site covering all endpoints."""
        last_error: Optional[str] = None
        server_streak: dict = {0: 0, 1: 0}   # per-account consecutive 5xx
        auth_dead: dict = {0: False, 1: False}
        auth_failures = 0
        permanent: dict = {}                 # combo_idx -> True when permanently dead

        full_cycles = 0
        while full_cycles < _MAX_FULL_CYCLES:
            full_cycles += 1
            combo_state = self._switcher.read_combo_state()
            combos = combo_state.get("combos", [])
            now_ms = int(time.time() * 1000)

            for ci, (acct_idx, model) in enumerate(_COMBO_ORDER):
                # Skip permanently-dead combos and dead-account combos.
                if permanent.get(ci) or auth_dead.get(acct_idx):
                    continue
                # Skip combos still cooling (per-combo cooldownUntil in shared state).
                cd = combos[ci].get("cooldownUntil") if ci < len(combos) else None
                if cd and self._iso_to_ms(cd) > now_ms:
                    continue

                try:
                    creds = self._switcher.get_credentials_for_account_index(acct_idx)
                except Exception as exc:
                    last_error = f"combo {ci} creds error: {exc}"
                    logger.warning("Combo %d (acct %d): credential read failed — advancing: %s", ci, acct_idx, exc)
                    continue

                try:
                    project = self._switcher.get_project_id(creds["fingerprint"])
                    result = self._post_code_assist(
                        creds["access_token"], project, model, contents, generation_config
                    )
                    self._switcher.record_success(creds["fingerprint"])
                    self._mark_combo(combo_state, ci, status="active", cooldown_until=None)
                    return result

                except _RateLimit429 as exc:
                    self._switcher.record_429(creds["fingerprint"], exc.reason, exc.reset_after_ms, model)
                    cls = _classify_429(exc.reason, exc.reset_after_ms)
                    if cls == "rpm":
                        wait_ms = exc.reset_after_ms if exc.reset_after_ms > 0 else _RPM_WAIT_DEFAULT_MS
                        self._mark_combo(combo_state, ci, status="cooldown",
                                         cooldown_until=self._ms_to_iso(now_ms + wait_ms))
                    elif cls == "daily":
                        self._mark_combo(combo_state, ci, status="daily",
                                         cooldown_until=self._ms_to_iso(now_ms + _ms_until_next_utc_midnight()))
                    else:  # capacity
                        self._mark_combo(combo_state, ci, status="cooldown",
                                         cooldown_until=self._ms_to_iso(now_ms + _CAPACITY_COOLDOWN_MS))
                    last_error = f"combo {ci} 429-{cls}"
                    # ADVANCE immediately (wait=0) — Hamad msg-33261.
                    continue

                except RuntimeError as exc:
                    status_code = self._status_from_runtime(exc)
                    if status_code and 500 <= status_code < 600:
                        server_streak[acct_idx] += 1
                        last_error = f"combo {ci} {status_code}"
                        if server_streak[acct_idx] >= _SERVER_BLOCKED_STREAK_N:
                            # 2-strike: bench BOTH combos of this account; jump to next account.
                            auth_dead[acct_idx] = True  # reuse account-skip gate
                            logger.warning("Account %d: %d consecutive 5xx — skipping its combos.",
                                           acct_idx, server_streak[acct_idx])
                        continue
                    if status_code == 401:
                        auth_failures += 1
                        if not self._refresh_account_once(acct_idx):
                            auth_dead[acct_idx] = True
                            last_error = f"combo {ci} 401-authDead"
                        continue
                    # 403 / 400 / IAM / PERMISSION_DENIED -> permanent for this combo.
                    permanent[ci] = True
                    auth_failures += 1
                    last_error = f"combo {ci} permanent: {exc}"
                    if auth_failures >= _MAX_AUTH_FAILURES:
                        break
                    continue

            # ── End of one full cycle ────────────────────────────────────────
            self._switcher.write_combo_state(combo_state)

            # All 4 daily-exhausted -> queue (no FRICTION-ALERT per matrix).
            if all(c.get("status") == "daily" for c in combos[:4]):
                self._switcher.request_rotation("all-accounts-daily")
                GeminiAccountExhausted = _get_gemini_account_exhausted()
                raise GeminiAccountExhausted("all-accounts-daily")

            # All 4 permanently dead / auth-cycling failed -> hard bail.
            if len(permanent) >= 4 or all(auth_dead.values()) or auth_failures >= _MAX_AUTH_FAILURES:
                raise RuntimeError(f"PAL combo cycle: all combos dead (auth-cycling-failed). last={last_error}")

            # Otherwise sleep the SHORTEST remaining cooldown (bounded) then restart.
            wait_ms = self._shortest_cooldown_ms(combos)
            if wait_ms <= 0:
                continue
            wait_s = min(wait_ms, _FULL_CYCLE_WAIT_CAP_MS) / 1000
            logger.warning("PAL combo cycle %d exhausted — bounded wait %.1fs before restart.", full_cycles, wait_s)
            time.sleep(wait_s)

        raise RuntimeError(f"PAL combo cycle: GEMINI_MAX_FULL_CYCLES ({_MAX_FULL_CYCLES}) reached. last={last_error}")

    # ── combo-cycle helpers ──────────────────────────────────────────────────

    def _refresh_account_once(self, acct_idx: int) -> bool:
        """One-shot forced token refresh for account `acct_idx`. Returns True if a
        fresh token was obtained (caller retries on next pass), False if still dead."""
        try:
            creds = self._switcher.get_credentials_for_account_index(acct_idx)
            return bool(creds.get("access_token"))
        except Exception as exc:
            logger.warning("Account %d one-shot refresh failed: %s", acct_idx, exc)
            return False

    @staticmethod
    def _mark_combo(state: dict, idx: int, status: str, cooldown_until) -> None:
        combos = state.setdefault("combos", [])
        while len(combos) <= idx:
            combos.append({"status": "active", "cooldownUntil": None, "note": ""})
        combos[idx]["status"] = status
        combos[idx]["cooldownUntil"] = cooldown_until

    @staticmethod
    def _shortest_cooldown_ms(combos: list) -> int:
        now_ms = int(time.time() * 1000)
        remaining = []
        for c in combos[:4]:
            cd = c.get("cooldownUntil")
            if cd:
                ms = _OAuthCodeAssistAdapterShared._iso_to_ms(cd) - now_ms
                if ms > 0:
                    remaining.append(ms)
        return min(remaining) if remaining else 0

    @staticmethod
    def _iso_to_ms(iso: str) -> int:
        try:
            s = iso.replace("Z", "+00:00")
            return int(datetime.datetime.fromisoformat(s).timestamp() * 1000)
        except Exception:
            return 0

    @staticmethod
    def _ms_to_iso(ms: int) -> str:
        return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _status_from_runtime(exc: RuntimeError) -> Optional[int]:
        """Extract the HTTP status code embedded in a RuntimeError message
        ('... HTTP 503 ...'). Returns None if no code is present (e.g. network error)."""
        import re
        m = re.search(r"HTTP\s+(\d{3})", str(exc))
        return int(m.group(1)) if m else None

    @staticmethod
    def _post_code_assist(
        access_token: str,
        project: str,
        model_name: str,
        contents: list,
        generation_config,
    ) -> dict:
        """Execute HTTP POST to Code Assist generateContent.

        Raises:
            _RateLimit429: On HTTP 429 (classified).
            RuntimeError: On other HTTP errors.
        """
        import uuid
        import urllib.request as _url_req
        import urllib.error as _url_err

        gen_cfg: dict = {}
        if generation_config:
            try:
                gen_cfg["temperature"] = generation_config.temperature
            except AttributeError:
                pass
            try:
                gen_cfg["candidateCount"] = generation_config.candidate_count
            except AttributeError:
                pass
            try:
                if generation_config.max_output_tokens:
                    gen_cfg["maxOutputTokens"] = generation_config.max_output_tokens
            except AttributeError:
                pass
            try:
                if generation_config.thinking_config:
                    gen_cfg["thinkingConfig"] = {
                        "thinkingBudget": generation_config.thinking_config.thinking_budget
                    }
            except AttributeError:
                pass

        body = json.dumps({
            "model": model_name,
            "project": project,
            "user_prompt_id": str(uuid.uuid4()),
            "request": {
                "contents": contents,
                "generationConfig": gen_cfg,
            },
        }).encode()

        url = f"{_CODE_ASSIST_ENDPOINT}/{_CODE_ASSIST_VERSION}:generateContent"
        req = _url_req.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with _url_req.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            inner = data.get("response", data)
            return inner
        except _url_err.HTTPError as exc:
            if exc.code == 429:
                try:
                    error_body = json.loads(exc.read().decode("utf-8"))
                except Exception:
                    error_body = {}
                reason, reset_ms = _parse_429_reason(error_body)
                raise _RateLimit429(reason, reset_ms, str(error_body)) from exc
            raise RuntimeError(
                f"Code Assist generateContent HTTP {exc.code}. "
                "Check quota or re-authenticate with: gemini auth login"
            ) from exc
        except _url_err.URLError as exc:
            raise RuntimeError(f"Code Assist generateContent network error: {exc}") from exc


def _OAuthCodeAssistAdapter(creds_path: str = _OAUTH_CREDS_PATH):  # noqa: N802
    """Factory function: returns legacy or shared-switcher adapter per PAL_USE_SHARED_SWITCHER.

    Feature flag:
      PAL_USE_SHARED_SWITCHER=0 (default) → _OAuthCodeAssistAdapterLegacy (existing behavior)
      PAL_USE_SHARED_SWITCHER=1           → _OAuthCodeAssistAdapterShared (new shared-state path)

    Phase 3 soak: flip env var to '1' to enable. Rollback: set back to '0'.
    No restart required (flag read at instantiation time).

    NOTE: This is a factory function, not a class. Callers that do isinstance() checks
    will see the concrete type (_OAuthCodeAssistAdapterLegacy or _OAuthCodeAssistAdapterShared).
    """
    use_shared = os.environ.get("PAL_USE_SHARED_SWITCHER", "0").strip() == "1"
    if use_shared:
        logger.info(
            "PAL_USE_SHARED_SWITCHER=1 — using shared GeminiSwitcherClient adapter"
        )
        return _OAuthCodeAssistAdapterShared(model_name=_OAuthCodeAssistAdapterShared._FLASH_PRIMARY)
    return _OAuthCodeAssistAdapterLegacy(creds_path=creds_path)


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
        """Initialize Gemini provider with API key and optional base URL.

        When api_key is empty or None, the provider falls back to OAuth
        credentials loaded from ~/.gemini/oauth_creds.json (Gemini CLI flow).
        """
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._client = None
        self._token_counters = {}  # Cache for token counting
        self._base_url = kwargs.get("base_url", None)  # Optional custom endpoint
        self._timeout_override = self._resolve_http_timeout()
        self._invalidate_capability_cache()
        # OAuth path: build Code Assist adapter when no API key is present.
        # Errors surface at startup rather than at first request.
        self._oauth_adapter = None  # _OAuthCodeAssistAdapterLegacy | _OAuthCodeAssistAdapterShared
        self._oauth_credentials = None  # legacy sentinel — keeps client property coherent
        # OAuth precedence flag: when GEMINI_OAUTH_PREFER=true, OAuth becomes the
        # primary auth path even if GEMINI_API_KEY is present. This allows free-tier
        # OAuth quota to be used preferentially over paid API key usage.
        _oauth_prefer = (get_env("GEMINI_OAUTH_PREFER", "false") or "false").strip().lower() in ("1", "true", "yes", "on")
        if not self.api_key or _oauth_prefer:
            try:
                self._oauth_adapter = _OAuthCodeAssistAdapter()
                if _oauth_prefer and self.api_key:
                    # Suppress the API key so downstream client init uses OAuth path.
                    logger.info(
                        "Gemini provider: GEMINI_OAUTH_PREFER=true — OAuth/Code Assist "
                        "adapter takes precedence over GEMINI_API_KEY"
                    )
                    self.api_key = ""
                else:
                    logger.info(
                        "Gemini provider initialized with OAuth/Code Assist adapter "
                        "(GEMINI_API_KEY not set — using ~/.gemini/oauth_creds.json)"
                    )
            except (FileNotFoundError, ValueError, RuntimeError) as exc:
                logger.warning(
                    "Gemini OAuth credentials unavailable: %s. "
                    "Set GEMINI_API_KEY or run: gemini auth login",
                    exc,
                )

    # ------------------------------------------------------------------
    # Capability surface
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Client access
    # ------------------------------------------------------------------

    @property
    def client(self):
        """Lazy initialization of Gemini client.

        Auth priority:
          1. GEMINI_API_KEY (env var, existing path — unchanged)
          2. OAuth credentials from ~/.gemini/oauth_creds.json (Gemini CLI flow)

        On 429 quota exhaustion with API key, callers should clear self._client
        (set to None) and re-enter this property; _oauth_credentials will be
        used on the next call if available.
        """
        if self._client is None:
            http_options_kwargs: dict[str, object] = {}
            if self._base_url:
                http_options_kwargs["base_url"] = self._base_url
            if self._timeout_override is not None:
                http_options_kwargs["timeout"] = self._timeout_override

            http_options = types.HttpOptions(**http_options_kwargs) if http_options_kwargs else None

            if self.api_key:
                # --- Path 1: API key (existing behaviour, unchanged) ---
                if http_options:
                    logger.debug(
                        "Initializing Gemini client with API key + options: base_url=%s timeout=%s",
                        http_options_kwargs.get("base_url"),
                        http_options_kwargs.get("timeout"),
                    )
                    self._client = genai.Client(api_key=self.api_key, http_options=http_options)
                else:
                    self._client = genai.Client(api_key=self.api_key)
            elif self._oauth_credentials is not None:
                # --- Path 2: OAuth credentials (Gemini CLI user account) ---
                # google-auth auto-refreshes when the token is < 5 min from expiry.
                # SECURITY: access_token value is never logged.
                logger.debug("Initializing Gemini client with OAuth credentials")
                if http_options:
                    self._client = genai.Client(
                        credentials=self._oauth_credentials,
                        http_options=http_options,
                    )
                else:
                    self._client = genai.Client(credentials=self._oauth_credentials)
            else:
                # Neither API key nor OAuth — attempt to surface a clear error
                raise RuntimeError(
                    "Gemini provider has no authentication. "
                    "Set GEMINI_API_KEY or run: gemini auth login"
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
            if self._oauth_adapter is not None:
                # --- Code Assist adapter path (OAuth, no SDK client) ---
                inner = self._oauth_adapter.generate_content(
                    resolved_model_name, contents, generation_config
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
            return self._run_with_retries(
                operation=_attempt,
                max_attempts=max_retries,
                delays=retry_delays,
                log_prefix=f"Gemini API ({resolved_model_name})",
            )
        except Exception as exc:
            exc_str = str(exc).lower()
            # 429 / quota-exhausted fallback: if API key is set but quota is
            # exhausted AND OAuth credentials are available, retry once via OAuth.
            # SECURITY: exc_str never contains access_token values (quota errors
            # reference quota metrics, not auth tokens).
            if (
                self.api_key
                and ("429" in exc_str or "quota" in exc_str or "resource_exhausted" in exc_str)
            ):
                # Lazily build Code Assist adapter for 429 fallback if not already available
                if self._oauth_adapter is None:
                    try:
                        self._oauth_adapter = _OAuthCodeAssistAdapter()
                    except (FileNotFoundError, ValueError, RuntimeError) as adapter_exc:
                        raise RuntimeError(
                            f"Gemini API quota exhausted (429) and OAuth/Code Assist adapter "
                            f"unavailable: {adapter_exc}. Run: gemini auth login"
                        ) from exc
                logger.warning(
                    "Gemini API key quota exhausted (429). "
                    "Attempting one-time fallback via OAuth/Code Assist adapter."
                )
                try:
                    return self._run_with_retries(
                        operation=_attempt,
                        max_attempts=2,
                        delays=[1, 3],
                        log_prefix=f"Gemini OAuth/Code-Assist fallback ({resolved_model_name})",
                    )
                except Exception as oauth_exc:
                    raise RuntimeError(
                        f"Gemini API quota exhausted and OAuth/Code Assist fallback also failed "
                        f"for model {resolved_model_name}: {oauth_exc}"
                    ) from oauth_exc

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
