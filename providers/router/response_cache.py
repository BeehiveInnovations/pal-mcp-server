"""Content-hash response cache for PAL calls.

Key = SHA-256 over (model, tool, normalized_prompt, file bytes + mtime).
Hit -> return cached ModelResponse without a network round-trip.
TTL default 3600s; opt-out with PAL_CACHE=0 or PAL_CACHE_TTL=0.

In-memory + optional on-disk mirror at ~/.cache/pal/responses/.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import time
from pathlib import Path
from threading import Lock

log = logging.getLogger(__name__)

DEFAULT_TTL = int(os.getenv("PAL_CACHE_TTL", "3600"))
CACHE_DIR = Path(os.getenv("PAL_CACHE_DIR", str(Path.home() / ".cache/pal/responses")))

_MEM: dict[str, tuple[float, object]] = {}
_LOCK = Lock()
_STATS = {"hits": 0, "misses": 0, "writes": 0}


def is_enabled() -> bool:
    return DEFAULT_TTL > 0 and os.getenv("PAL_CACHE", "1") not in ("0", "false", "no")


def _normalize_prompt(p: str) -> str:
    # collapse repeated whitespace so trivially different prompts hit the same key
    return " ".join((p or "").split())


def _file_fingerprint(paths: list[str] | None) -> list[tuple[str, int, int]]:
    """Return (path, size, mtime_ns) triples for cache-invalidation."""
    if not paths:
        return []
    out: list[tuple[str, int, int]] = []
    for p in paths:
        try:
            st = os.stat(p)
            out.append((p, st.st_size, st.st_mtime_ns))
        except OSError:
            out.append((p, -1, 0))
    return out


def make_key(model: str, tool: str, prompt: str, files: list[str] | None = None, extra: dict | None = None) -> str:
    payload = {
        "model": model,
        "tool": tool,
        "prompt": _normalize_prompt(prompt),
        "files": _file_fingerprint(files),
        "extra": extra or {},
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def get(key: str):
    if not is_enabled():
        return None
    now = time.time()
    with _LOCK:
        entry = _MEM.get(key)
        if entry is not None:
            expiry, value = entry
            if expiry >= now:
                _STATS["hits"] += 1
                return value
            _MEM.pop(key, None)
    # disk fallback
    p = CACHE_DIR / f"{key[:2]}" / f"{key}.pkl"
    if not p.exists():
        with _LOCK:
            _STATS["misses"] += 1
        return None
    try:
        with p.open("rb") as fp:
            expiry, value = pickle.load(fp)
        if expiry < now:
            p.unlink(missing_ok=True)
            with _LOCK:
                _STATS["misses"] += 1
            return None
        with _LOCK:
            _MEM[key] = (expiry, value)
            _STATS["hits"] += 1
        return value
    except (OSError, EOFError, pickle.UnpicklingError, ValueError, AttributeError) as exc:
        # Corrupt/partial/incompatible pickle (e.g. truncated by a killed
        # process) must never crash the caller — treat as a miss and drop
        # the bad file so it doesn't fail again on the next lookup.
        log.debug("cache disk miss %s: %s", key[:8], exc)
        p.unlink(missing_ok=True)
        with _LOCK:
            _STATS["misses"] += 1
        return None


def put(key: str, value, ttl: int = DEFAULT_TTL) -> None:
    if not is_enabled():
        return
    expiry = time.time() + max(ttl, 1)
    with _LOCK:
        _MEM[key] = (expiry, value)
        _STATS["writes"] += 1
    try:
        d = CACHE_DIR / f"{key[:2]}"
        d.mkdir(parents=True, exist_ok=True)
        with (d / f"{key}.pkl").open("wb") as fp:
            pickle.dump((expiry, value), fp)
    except (OSError, pickle.PicklingError) as exc:
        log.debug("cache disk write skipped %s: %s", key[:8], exc)


def snapshot() -> dict:
    with _LOCK:
        return dict(_STATS) | {"entries_in_memory": len(_MEM), "ttl": DEFAULT_TTL}
