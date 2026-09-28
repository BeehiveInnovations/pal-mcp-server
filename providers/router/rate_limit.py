"""Rolling-window rate-limit accountant.

Tracks token-per-minute and requests-per-minute per (provider, model). If a
call would exceed the configured cap, `should_downshift()` returns True so
the router can pick the next model instead of eating a 429.

State is process-local. Ships defaults for common caps:
    groq/gpt-oss-120b     : 8_000 TPM,  500 RPM
    openrouter (default)  : 200_000 TPM,   0 (RPM unlimited)
    gemini (default)      : 1_000_000 TPM,   0
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass

WINDOW_SECONDS = 60.0

# (provider, model_prefix) -> (tpm_cap, rpm_cap). Match by prefix; 0 == unlimited.
_CAPS: dict[tuple[str, str], tuple[int, int]] = {
    ("custom", "gpt-oss-120b"): (8_000, 500),  # groq via CUSTOM_API_URL
    ("custom", "openai/gpt-oss"): (8_000, 500),
    ("openrouter", ""): (200_000, 0),
    ("google", ""): (1_000_000, 0),
    ("xai", ""): (200_000, 0),
}


@dataclass
class _Bucket:
    tokens: deque  # (ts, count) pairs
    reqs: deque  # ts values


_BUCKETS: dict[tuple[str, str], _Bucket] = {}
_LOCK = threading.Lock()


def is_enabled() -> bool:
    return os.getenv("PAL_RATE_LIMIT", "1") not in ("0", "false", "no")


def _cap(provider: str, model: str) -> tuple[int, int]:
    for (p, prefix), caps in _CAPS.items():
        if p == provider and (prefix == "" or model.startswith(prefix)):
            return caps
    return (0, 0)


def _bucket(provider: str, model: str) -> _Bucket:
    key = (provider, model)
    b = _BUCKETS.get(key)
    if b is None:
        b = _Bucket(tokens=deque(), reqs=deque())
        _BUCKETS[key] = b
    return b


def _sweep(b: _Bucket, now: float) -> None:
    cutoff = now - WINDOW_SECONDS
    while b.tokens and b.tokens[0][0] < cutoff:
        b.tokens.popleft()
    while b.reqs and b.reqs[0] < cutoff:
        b.reqs.popleft()


def should_downshift(provider: str, model: str, est_tokens: int) -> tuple[bool, str]:
    """Return (True, reason) if the request would exceed either cap."""
    if not is_enabled():
        return (False, "")
    tpm_cap, rpm_cap = _cap(provider, model)
    if tpm_cap == 0 and rpm_cap == 0:
        return (False, "")
    now = time.monotonic()
    with _LOCK:
        b = _bucket(provider, model)
        _sweep(b, now)
        used_t = sum(c for _, c in b.tokens)
        used_r = len(b.reqs)
        if tpm_cap and (used_t + est_tokens) > tpm_cap:
            return (True, f"TPM {used_t + est_tokens}>{tpm_cap}")
        if rpm_cap and (used_r + 1) > rpm_cap:
            return (True, f"RPM {used_r + 1}>{rpm_cap}")
    return (False, "")


def record(provider: str, model: str, tokens_used: int) -> None:
    if not is_enabled():
        return
    now = time.monotonic()
    with _LOCK:
        b = _bucket(provider, model)
        _sweep(b, now)
        b.tokens.append((now, tokens_used))
        b.reqs.append(now)


# ---------------------------------------------------------------------------
# Retry-After honor: parse the Retry-After header (seconds or HTTP-date) and
# common body patterns like "Please try again in 6.2s" / "retry in 12000ms".
# Cap the honored wait at MAX_HONOR_S so a pathological Retry-After: 3600
# does not block the caller forever — beyond that we fall through and let the
# fallback_chain switch model.
# ---------------------------------------------------------------------------
MAX_HONOR_S = int(os.getenv("PAL_RATE_LIMIT_MAX_HONOR_S", "15"))


def parse_retry_after(headers: dict | None, body: str | None) -> int | None:
    """Return an integer seconds-to-wait if the response tells us how long,
    else None. Honors the standard Retry-After header (delta-seconds only —
    HTTP-date parsing is intentionally not implemented; providers don't use
    it in practice for rate-limit errors) and scans the body for common
    provider phrasings."""
    # Header: canonical or lowercase key
    if headers:
        for key in ("Retry-After", "retry-after", "RETRY-AFTER"):
            val = headers.get(key)
            if val is None:
                continue
            try:
                secs = int(float(str(val).strip()))
                if secs >= 0:
                    return secs
            except (TypeError, ValueError):
                continue

    if not body:
        return None
    import re

    text = body.lower()
    # "please try again in 6.2s" / "retry in 6.2 seconds"
    m = re.search(r"(?:retry|try again)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)\s*s(?:ec(?:ond)?s?)?\b", text)
    if m:
        return max(0, int(float(m.group(1))))
    # "retry in 12000ms" / "wait 500 ms"
    m = re.search(r"(?:retry|wait)[^0-9]{0,20}([0-9]+)\s*ms\b", text)
    if m:
        return max(0, int(m.group(1)) // 1000)
    # groq-style "Please retry in 6.168596011s"
    m = re.search(r"please retry in\s+([0-9]+(?:\.[0-9]+)?)s", text)
    if m:
        return max(0, int(float(m.group(1))))
    return None


def honor_retry_after(headers: dict | None, body: str | None, sleep=time.sleep) -> int:
    """If a Retry-After hint is present and fits under MAX_HONOR_S, sleep for
    that long and return the seconds slept. Otherwise return 0 (caller should
    fall through to the fallback chain instead of blocking further)."""
    hint = parse_retry_after(headers, body)
    if hint is None:
        return 0
    wait = min(hint, MAX_HONOR_S)
    if wait > 0:
        sleep(wait)
    return wait


def snapshot() -> dict:
    """Diagnostic snapshot for `pal --diag`."""
    now = time.monotonic()
    out: dict[str, dict] = {}
    with _LOCK:
        for (p, m), b in _BUCKETS.items():
            _sweep(b, now)
            out[f"{p}/{m}"] = {
                "tpm_used": sum(c for _, c in b.tokens),
                "rpm_used": len(b.reqs),
                "tpm_cap": _cap(p, m)[0],
                "rpm_cap": _cap(p, m)[1],
            }
    return out
