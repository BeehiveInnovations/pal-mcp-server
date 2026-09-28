"""Session-scoped refusal memory.

Records (model, task_category) pairs that returned a refusal / 4xx / 5xx /
safety-block. `is_blacklisted()` lets the router skip those pairs for the
next N routing decisions.  Process-lifetime state only; a restart wipes.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

# how long a blacklist entry stays hot (seconds)
TTL = int(os.getenv("PAL_REFUSAL_TTL", "300"))


@dataclass
class _Entry:
    ts: float
    count: int
    reason: str


_MEM: dict[tuple[str, str], _Entry] = {}
_LOCK = threading.Lock()


def is_enabled() -> bool:
    return os.getenv("PAL_REFUSAL_MEMORY", "1") not in ("0", "false", "no")


REFUSAL_MARKERS = (
    "refuse", "cannot help", "cannot assist", "unable to", "policy",
    "safety", "unsafe", "harmful", "not able to comply",
)
STATUS_TRIGGERS = ("400", "401", "403", "422", "429", "500", "502", "503", "504",
                   "NOT_FOUND", "PERMISSION_DENIED", "RESOURCE_EXHAUSTED", "BLOCKED")


def classify(err_or_response: str) -> str | None:
    """Return short refusal tag if the text looks like a refusal / error, else None."""
    if not err_or_response:
        return None
    low = err_or_response.lower()
    for m in REFUSAL_MARKERS:
        if m in low:
            return f"refusal:{m}"
    for s in STATUS_TRIGGERS:
        if s in err_or_response:
            return f"status:{s}"
    return None


def record(model: str, category: str, reason: str) -> None:
    if not is_enabled():
        return
    key = (model, category)
    now = time.time()
    with _LOCK:
        cur = _MEM.get(key)
        _MEM[key] = _Entry(
            ts=now, count=(cur.count + 1 if cur else 1), reason=reason[:120]
        )
    log.info("refusal recorded: %s / %s (%s)", model, category, reason[:80])


def is_blacklisted(model: str, category: str) -> bool:
    if not is_enabled():
        return False
    key = (model, category)
    now = time.time()
    with _LOCK:
        entry = _MEM.get(key)
        if entry is None:
            return False
        if now - entry.ts > TTL:
            _MEM.pop(key, None)
            return False
        return entry.count >= 1


def clear() -> None:
    with _LOCK:
        _MEM.clear()


def snapshot() -> dict:
    now = time.time()
    with _LOCK:
        return {
            f"{m}/{c}": {
                "age_s": int(now - e.ts), "count": e.count, "reason": e.reason,
            }
            for (m, c), e in _MEM.items() if now - e.ts <= TTL
        }
