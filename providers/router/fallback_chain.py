"""Auto-fallback chain: try every model in a category before surfacing failure.

Motivation: providers hit rate-limits, quota exhaustion, and silent policy blocks
constantly. Rather than bounce failures back to the caller after one attempt,
this module cycles through same-category alternatives from ``~/.pal/env.json``
until one succeeds or the list is exhausted.

Triggers a fallback on:
  - HTTP status 413 (payload too large) / 402 (credits) / 429 (rate) / 503 (down)
  - Silent policy blocks: response text containing markers like
    "Response blocked or incomplete" or "Finish reason: Unknown"
  - Provider deprecation 404s already handled by self_heal.apply_after_retry

Env: PAL_FALLBACK=0 disables (default on). PAL_FALLBACK_MAX caps attempts (default 8).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

FALLBACK_TRIGGERS: frozenset[int] = frozenset({402, 413, 429, 503})

SILENT_BLOCK_MARKERS: tuple[str, ...] = (
    "response blocked or incomplete",
    "finish reason: unknown",
    "content_filter",
    "safety block",
    "content policy",
    "response was blocked",
)


def _env_path() -> Path:
    return Path(os.getenv("PAL_ENV_JSON", str(Path.home() / ".pal/env.json")))


def is_enabled() -> bool:
    return os.getenv("PAL_FALLBACK", "1") not in ("0", "false", "no")


def _max_attempts() -> int:
    try:
        return max(1, int(os.getenv("PAL_FALLBACK_MAX", "8")))
    except ValueError:
        return 8


@lru_cache(maxsize=8)
def _load_categories_from(path_str: str) -> dict[str, list[str]]:
    p = Path(path_str)
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError) as exc:
        log.debug("fallback: cannot load %s (%s)", p, exc)
        return {}
    return dict(data.get("categories", {}) or {})


def _load_categories() -> dict[str, list[str]]:
    return _load_categories_from(str(_env_path()))


def reset_cache() -> None:
    """Test helper — drop cached categories map so env changes are re-read."""
    _load_categories_from.cache_clear()


def category_for(model: str) -> str | None:
    for cat, models in _load_categories().items():
        if model in models:
            return cat
    return None


def chain_for(model: str) -> list[str]:
    """Ordered list of fallback models: same-category peers after `model`,
    then peers before `model` (wrap-around), de-duplicated."""
    cat = category_for(model)
    if not cat:
        return []
    peers = _load_categories().get(cat, [])
    try:
        i = peers.index(model)
        rotated = peers[i + 1 :] + peers[:i]
    except ValueError:
        rotated = list(peers)
    seen: set[str] = {model}
    ordered: list[str] = []
    for m in rotated:
        if m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered


def should_fallback(status_code: int | None, response_text: str | Exception) -> bool:
    if status_code in FALLBACK_TRIGGERS:
        return True
    haystack = str(response_text or "").lower()
    if not haystack:
        return False
    return any(marker in haystack for marker in SILENT_BLOCK_MARKERS)


def _extract_status_and_text(exc: Exception) -> tuple[int | None, str]:
    """Best-effort pull of an HTTP status + human-readable text from an exception."""
    text = str(exc)
    status: int | None = None
    for attr in ("status_code", "http_status", "code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int) and 100 <= val <= 599:
            status = val
            break
    resp = getattr(exc, "response", None)
    if resp is not None and status is None:
        val = getattr(resp, "status_code", None)
        if isinstance(val, int):
            status = val
    # scrape common inline codes: "Error code: 413" / "429" / "402"
    if status is None:
        import re

        m = re.search(r"\b(4\d\d|5\d\d)\b", text)
        if m:
            status = int(m.group(1))
    return status, text


def call_with_fallback(
    call: Callable[[str], object],
    model: str,
    *,
    on_switch: Callable[[str, str, str], None] | None = None,
) -> object:
    """Invoke ``call(model)`` and, on a fallback-worthy failure, retry against
    each same-category peer in order. Raises the LAST exception when the whole
    chain is exhausted.

    ``on_switch(prev_model, next_model, reason)`` fires before every switch —
    use it to log the trail to the operator.
    """
    if not is_enabled():
        return call(model)

    attempted: list[str] = [model]
    chain = [model, *chain_for(model)][: _max_attempts()]
    last_exc: Exception | None = None

    for i, candidate in enumerate(chain):
        try:
            result = call(candidate)
        except Exception as exc:  # noqa: BLE001 — we deliberately catch to reroute
            status, text = _extract_status_and_text(exc)
            if not should_fallback(status, text):
                raise
            last_exc = exc
            if i + 1 < len(chain):
                reason = f"status={status} | {text[:120]}"
                log.warning("fallback: %s → %s (%s)", candidate, chain[i + 1], reason)
                if on_switch:
                    try:
                        on_switch(candidate, chain[i + 1], reason)
                    except Exception:  # noqa: BLE001
                        pass
                attempted.append(chain[i + 1])
            continue
        # Non-exception result: check for embedded silent-block markers
        result_text = _stringify_result(result)
        if should_fallback(None, result_text):
            if i + 1 < len(chain):
                reason = f"silent-block on {candidate}"
                log.warning("fallback: %s → %s (%s)", candidate, chain[i + 1], reason)
                if on_switch:
                    try:
                        on_switch(candidate, chain[i + 1], reason)
                    except Exception:  # noqa: BLE001
                        pass
                attempted.append(chain[i + 1])
                last_exc = RuntimeError(f"silent-block on {candidate}")
                continue
            # exhausted — return the last (blocked) result rather than raise
            return result
        return result

    # Whole chain exhausted with failures
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"fallback chain exhausted for {model}; tried {attempted}")


def _stringify_result(result: object) -> str:
    """Coerce a provider response into text for silent-block scanning."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    for attr in ("content", "text", "message"):
        val = getattr(result, attr, None)
        if isinstance(val, str) and val:
            return val
    try:
        return json.dumps(result, default=str)[:2000]
    except (TypeError, ValueError):
        return str(result)[:2000]


def describe_chain(model: str) -> Iterable[str]:
    """Introspection helper: full ordered attempt list a real call would try."""
    return [model, *chain_for(model)][: _max_attempts()]
