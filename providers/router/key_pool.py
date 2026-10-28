"""Multi-key rotation pool.

Reads ``~/.pal/keys.json`` and rotates API keys per provider on rate-limit /
credit errors, so PAL can spread load across several free-tier accounts (for
example two separate Groq accounts, each with its own token budget) without a
database.

Design notes:
- In-memory cooldown only. Keys are never written back to disk; ``keys.json``
  is user-managed and already chmod 600.
- Full key values are never logged (only a masked prefix).
- This module only rotates keys for an already-selected non-Claude provider.
  It never selects a model or a provider, so it cannot route toward Anthropic /
  Claude; the Claude-exclusion invariant lives in the routing layer.
- Everything degrades gracefully: a missing ``keys.json`` yields an empty pool
  and every call becomes a no-op, so existing single-key behaviour is unchanged.

keys.json shape (either form accepted per provider)::

    {"groq": {"keys": ["gsk_a", "gsk_b"], "base": "..."},
     "openrouter": ["sk-or-1", "sk-or-2"]}
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time

log = logging.getLogger(__name__)

_lock = threading.Lock()
_pool: dict[str, list[str]] | None = None
_cool: dict[str, float] = {}  # key[:16] -> epoch when the key becomes usable again
_idx: dict[str, int] = {}  # provider name -> rotation cursor

_RATE_MARKERS = (
    "429",
    "402",
    "rate_limit",
    "rate limit",
    "otpm",
    "tpm",
    "too many requests",
    "quota",
    "insufficient",
    "credit",
    "exceed your available",
    "resource package",
)


def _keys_path() -> str:
    return os.path.expanduser(os.getenv("PAL_KEYS_FILE", "~/.pal/keys.json"))


def _cooldown() -> float:
    try:
        return float(os.getenv("PAL_KEY_COOLDOWN", "60"))
    except ValueError:
        return 60.0


def is_enabled() -> bool:
    return os.getenv("PAL_KEY_ROTATE", "1").lower() not in ("0", "false", "no")


def _mask(k: str | None) -> str:
    return (k[:10] + "…") if k else "(none)"


def _load() -> dict[str, list[str]]:
    global _pool
    if _pool is not None:
        return _pool
    data: dict[str, list[str]] = {}
    try:
        with open(_keys_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
        for prov, val in (raw or {}).items():
            keys = val.get("keys") if isinstance(val, dict) else val
            keys = [k for k in (keys or []) if isinstance(k, str) and k.strip()]
            if keys:
                data[prov] = keys
    except FileNotFoundError:
        pass
    except Exception as exc:  # malformed file must not break routing
        log.warning("key_pool: could not read %s: %s", _keys_path(), exc)
    _pool = data
    return _pool


def _reset() -> None:
    """Test hook: forget the cached pool and rotation state."""
    global _pool
    with _lock:
        _pool = None
        _cool.clear()
        _idx.clear()


def keys_for(provider: str) -> list[str]:
    return list(_load().get(provider, []))


def _healthy(provider: str) -> list[str]:
    now = time.time()
    return [k for k in keys_for(provider) if _cool.get(k[:16], 0.0) <= now]


def current(provider: str) -> str | None:
    """Return the active key for a provider, skipping cooling keys."""
    with _lock:
        healthy = _healthy(provider)
        if not healthy:
            all_keys = keys_for(provider)
            return all_keys[0] if all_keys else None
        return healthy[_idx.get(provider, 0) % len(healthy)]


def rotate(provider: str, bad_key: str | None, reason: str = "") -> str | None:
    """Cool ``bad_key`` for the cooldown TTL and return the next healthy key.

    Returns None when no other healthy key exists (caller then falls back to
    model-level fallback).
    """
    with _lock:
        if bad_key:
            _cool[bad_key[:16]] = time.time() + _cooldown()
            log.warning(
                "key_pool: cooling %s for %s (%s)", _mask(bad_key), provider, (reason or "")[:60]
            )
        healthy = _healthy(provider)
        if not healthy:
            return None
        _idx[provider] = (_idx.get(provider, 0) + 1) % len(healthy)
        nxt = healthy[_idx[provider]]
        return nxt if nxt != bad_key else (healthy[(_idx[provider] + 1) % len(healthy)] if len(healthy) > 1 else None)


def mark_ok(provider: str, key: str | None) -> None:
    with _lock:
        if key:
            _cool.pop(key[:16], None)


def is_rate_or_credit_error(msg: str) -> bool:
    m = (msg or "").lower()
    return any(x in m for x in _RATE_MARKERS)


def name_for_type(provider_type_value: str | None) -> str | None:
    """Map a PAL ProviderType value to a keys.json provider name."""
    v = (provider_type_value or "").lower()
    if v in ("openrouter", "openai", "xai"):
        return v
    if v == "google":
        return "gemini"
    if v == "custom":
        url = (os.getenv("CUSTOM_API_URL", "") or "").lower()
        return "groq" if "groq" in url else "custom"
    return v or None


def stats() -> dict:
    """Per-provider counts for diagnostics. Never includes key values."""
    now = time.time()
    out: dict[str, dict] = {}
    for prov, ks in _load().items():
        cooling = sum(1 for k in ks if _cool.get(k[:16], 0.0) > now)
        out[prov] = {"keys": len(ks), "cooling": cooling, "active_index": _idx.get(prov, 0)}
    return out
