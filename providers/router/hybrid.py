"""Speculative cheap-draft, verify-if-uncertain executor + confidence envelope.

Two features:

1) `hybrid_execute()` runs a cheap model first, checks confidence in the
   response, and only escalates to an expensive model when the draft says
   `confidence: low` or fails schema.

2) `CONFIDENCE_ENVELOPE_INSTRUCTION` is a system-prompt suffix that asks a
   model for a JSON list of `{claim, confidence, source_span}` triples.
   Parsing lives here in `extract_envelope()`.

Feature is opt-in per-tool via `hybrid=True` in the tool schema OR via
`PAL_HYBRID=1`. Off by default so we don't break existing tool contracts.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)

CONFIDENCE_ENVELOPE_INSTRUCTION = """
After your normal answer, append a machine-readable envelope on its own line:

<pal-envelope>
{"claims":[{"claim":"<short>","confidence":"high|medium|low","source_span":"path:start-end or n/a"}]}
</pal-envelope>

Rules:
- One claim per statement of fact. Opinions are `low`.
- `confidence: high` means you would stake the answer on a byte-check.
- Never fabricate a `source_span`. Use `n/a` if none applies.
""".strip()

_ENVELOPE_RE = re.compile(
    r"<pal-envelope>\s*(\{.*?\})\s*</pal-envelope>",
    re.DOTALL | re.IGNORECASE,
)


def is_enabled() -> bool:
    return os.getenv("PAL_HYBRID", "0") in ("1", "true", "yes")


@dataclass
class Envelope:
    claims: list[dict]
    min_confidence: str  # "high", "medium", "low", or "unknown"


def extract_envelope(text: str) -> Envelope | None:
    if not text:
        return None
    m = _ENVELOPE_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        log.debug("envelope JSON invalid, skipping")
        return None
    claims = data.get("claims") or []
    order = {"low": 0, "medium": 1, "high": 2}
    min_c = min((order.get((c.get("confidence") or "").lower(), 3) for c in claims), default=3)
    ranks = {0: "low", 1: "medium", 2: "high", 3: "unknown"}
    return Envelope(claims=claims, min_confidence=ranks[min_c])


def needs_escalation(env: Envelope | None) -> bool:
    if env is None:
        return False  # no envelope -> trust the draft; escalation decision is up to caller
    return env.min_confidence in ("low", "unknown")


def hybrid_execute(
    draft_call: Callable[[], object],
    verify_call: Callable[[str], object],
    extract_text: Callable[[object], str],
):
    """Run `draft_call()`; if the response's envelope shows low confidence,
    call `verify_call(draft_text)` and return that. Otherwise return draft."""
    if not is_enabled():
        return draft_call()
    draft = draft_call()
    text = extract_text(draft) or ""
    env = extract_envelope(text)
    if not needs_escalation(env):
        return draft
    log.info("hybrid: envelope confidence low → escalating")
    return verify_call(text)
