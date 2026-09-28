"""Cross-provider quota / availability probe.

Cheap `/models` (or equivalent) hit per configured provider to record whether
it is currently reachable, roughly-latent, or exhausted. Result is appended
as JSONL to ``~/.pal/provider_stats.jsonl`` so both the router and the operator
can read the last-known state without re-probing.

Callers:
    stats = probe_all({"groq": "https://api.groq.com/openai/v1",
                       "openrouter": "https://openrouter.ai/api/v1", ...})
    if not is_available("groq"):
        # skip this provider, pick another
        ...

Design choices:
- No auth on the probe URL (uses public /models endpoints where available so
  we don't burn quota on a keepalive check).
- 5 s per-probe timeout so a hung provider doesn't stall the whole run.
- Freshness window default 600 s — user can override with
  ``PAL_QUOTA_FRESHNESS_S``. A stale record is treated as unknown, not
  unavailable, so callers still attempt the provider.
"""

from __future__ import annotations

import calendar
import json
import logging
import os
import time
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

STATS_PATH = Path(os.getenv("PAL_QUOTA_STATS_JSONL", str(Path.home() / ".pal/provider_stats.jsonl")))
DEFAULT_TIMEOUT_S = 5
DEFAULT_FRESHNESS_S = int(os.getenv("PAL_QUOTA_FRESHNESS_S", "600"))

# Cheap probe URLs — prefer /models over anything that costs generation tokens.
PROBE_URLS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1/models",
    "openai": "https://api.openai.com/v1/models",
    "openrouter": "https://openrouter.ai/api/v1/models",
    "deepseek": "https://api.deepseek.com/models",
    "mistral": "https://api.mistral.ai/v1/models",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
    "cerebras": "https://api.cerebras.ai/v1/models",
    "zai": "https://api.z.ai/api/paas/v4/models",
    "requesty": "https://router.requesty.ai/v1/models",
    "xai": "https://api.x.ai/v1/models",
}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _http_get(url: str, timeout: float, requester: Callable | None = None):
    """Isolated for monkeypatching in tests. Uses httpx if installed, else urllib."""
    if requester is not None:
        return requester(url, timeout)
    try:
        import httpx

        return httpx.get(url, timeout=timeout)
    except ImportError:  # pragma: no cover
        import urllib.request

        req = urllib.request.Request(url, method="GET")
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)  # noqa: S310
            code = resp.getcode()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(str(exc)) from exc

        class _Shim:
            status_code = code

        return _Shim()


def probe_one(provider: str, url: str, timeout: float = DEFAULT_TIMEOUT_S, requester: Callable | None = None) -> dict:
    """Probe a single provider. Returns a dict — never raises."""
    started = time.monotonic()
    record: dict = {
        "provider": provider,
        "url": url,
        "checked_at": _now_iso(),
        "available": False,
        "latency_ms": 0,
        "status_code": None,
        "error": None,
    }
    try:
        resp = _http_get(url, timeout, requester)
        record["status_code"] = getattr(resp, "status_code", None)
        # 2xx / 401 (auth required but service alive) / 403 → available
        # 5xx / 429 / connection refused → unavailable
        code = record["status_code"]
        record["available"] = bool(code and (200 <= code < 500) and code != 429)
        if not record["available"] and code:
            record["error"] = f"status={code}"
    except Exception as exc:  # noqa: BLE001
        record["error"] = str(exc)[:200]
    record["latency_ms"] = int((time.monotonic() - started) * 1000)
    return record


def probe_all(providers: dict[str, str] | None = None, requester: Callable | None = None) -> dict[str, dict]:
    """Probe each provider in the map (defaults to PROBE_URLS). Appends every
    result to STATS_PATH as one JSONL line. Returns provider → record."""
    targets = providers if providers is not None else PROBE_URLS
    results: dict[str, dict] = {}
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATS_PATH.open("a", encoding="utf-8") as fp:
        for name, url in targets.items():
            rec = probe_one(name, url, requester=requester)
            results[name] = rec
            fp.write(json.dumps(rec) + "\n")
    return results


def is_available(provider: str, max_age_s: int | None = None) -> bool:
    """Read the LAST stats-file record for this provider and return its
    availability flag. Returns True (optimistic) when no record exists or the
    record is older than max_age_s — the caller should still try, since we
    don't want stale probes to mask a now-live provider."""
    freshness = max_age_s if max_age_s is not None else DEFAULT_FRESHNESS_S
    try:
        lines = STATS_PATH.read_text(encoding="utf-8").splitlines()
    except (OSError, FileNotFoundError):
        return True  # no data → let caller try
    # Scan from newest to oldest for the first record matching this provider.
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if rec.get("provider") != provider:
            continue
        checked = rec.get("checked_at", "")
        # Parse ISO-UTC back as UTC epoch (calendar.timegm, NOT time.mktime
        # which treats input as local time and misfires under any non-UTC TZ).
        try:
            ts = calendar.timegm(time.strptime(checked, "%Y-%m-%dT%H:%M:%SZ"))
        except (TypeError, ValueError):
            return True
        age = time.time() - ts
        if age > freshness:
            return True  # stale — optimistic
        return bool(rec.get("available"))
    return True  # never probed — optimistic
