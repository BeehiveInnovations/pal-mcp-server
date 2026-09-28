"""One-shot health probe for keyed providers.

Runs on first tool invocation (lazy) or from `pal --diag`. Marks each
provider up/down/skipped so `auto` mode never routes to a provider that
is currently returning 4xx/5xx on its model-listing endpoint.

Non-blocking on error; a probe failure only removes the provider from
'auto' for this process, not from explicit-model calls.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)


_STATUS: dict[str, dict] = {}
_DONE = threading.Event()
_LOCK = threading.Lock()


def is_enabled() -> bool:
    return os.getenv("PAL_HEALTH_PROBE", "1") not in ("0", "false", "no")


def mark(provider: str, ok: bool, detail: str = "") -> None:
    with _LOCK:
        _STATUS[provider] = {"ok": ok, "detail": detail, "ts": time.time()}


def is_up(provider: str) -> bool:
    if not is_enabled():
        return True
    entry = _STATUS.get(provider)
    return entry is None or entry.get("ok", True)


def snapshot() -> dict:
    with _LOCK:
        return dict(_STATUS)


def run_probe(probes: dict[str, Callable[[], None]]) -> None:
    """probes: {provider_name: zero-arg callable that raises on failure}.
    Executes them in parallel threads; each result is recorded via mark()."""
    if not is_enabled() or _DONE.is_set():
        return

    def _one(name: str, fn: Callable[[], None]) -> None:
        try:
            fn()
            mark(name, True, "ok")
        except Exception as exc:
            mark(name, False, str(exc)[:200])
            log.warning("health probe failed for %s: %s", name, exc)

    threads = [threading.Thread(target=_one, args=(n, f), daemon=True)
               for n, f in probes.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)
    _DONE.set()


def reset() -> None:
    with _LOCK:
        _STATUS.clear()
    _DONE.clear()
