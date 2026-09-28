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
