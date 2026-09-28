"""Self-heal on provider deprecation errors.

Google's Gemini API returns 404 NOT_FOUND with a text hint like:
    "This model models/gemini-3-pro-preview is no longer available.
     Please update your code to use models/gemini-3.1-pro-preview ..."

We parse the successor id, retry once with it, and update an in-process
alias map so subsequent calls skip the failed hop. Migrations are appended
to REGISTRY_DRIFT_LOG for user review.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_MIGRATION_RE = re.compile(
    r"models?/([A-Za-z0-9._-]+)\s+is\s+no\s+longer\s+available.*?" r"use\s+models?/([A-Za-z0-9._-]+)",
    re.IGNORECASE | re.DOTALL,
)

_ALIAS_MAP: dict[str, str] = {}
_LOCK = threading.Lock()

DRIFT_LOG = Path(os.getenv("PAL_DRIFT_LOG", str(Path.home() / ".cache/pal/registry-drift.log")))


def is_enabled() -> bool:
    return os.getenv("PAL_SELF_HEAL", "1") not in ("0", "false", "no")


def parse_migration(err_text: str) -> tuple[str, str] | None:
    """Return (dead_id, new_id) if the error text carries a migration hint."""
    m = _MIGRATION_RE.search(err_text or "")
    return (m.group(1), m.group(2)) if m else None


def record_migration(dead: str, new: str, provider: str = "unknown") -> None:
    with _LOCK:
        _ALIAS_MAP[dead] = new
    try:
        DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DRIFT_LOG.open("a", encoding="utf-8") as fp:
            fp.write(f"{datetime.now(timezone.utc).isoformat()}\t{provider}\t" f"{dead}\t->\t{new}\n")
    except OSError as exc:
        log.warning("could not write drift log %s: %s", DRIFT_LOG, exc)


def resolve(model_id: str) -> str:
    """Return the live successor id if the given id has been retired."""
    return _ALIAS_MAP.get(model_id, model_id)


def apply_after_retry(callable_, model_name: str, provider: str, *args, **kwargs):
    """Invoke `callable_(model_name, *args, **kwargs)`. On deprecation-404,
    look up the successor from the error text, record it, retry ONCE."""
    if not is_enabled():
        return callable_(model_name, *args, **kwargs)
    try:
        return callable_(model_name, *args, **kwargs)
    except Exception as exc:
        mig = parse_migration(str(exc))
        if not mig:
            raise
        dead, new = mig
        record_migration(dead, new, provider=provider)
        log.warning("self-heal: %s dead → migrating to %s", dead, new)
        return callable_(new, *args, **kwargs)
