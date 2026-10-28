"""Outbound/inbound guardrail for provider sends.

Outbound: ``mask_outbound`` walks a request payload (system / messages / input /
prompt / nested content parts / tool results), replaces credentials and PII with
``[REDACTED:<kind>:<n>]`` placeholders and returns a per-call ``MaskContext``.
``unmask`` restores placeholders in the response using that context.

Design rules:
  * Restore maps live only in the ``MaskContext`` (per call, in memory). They are
    never written to disk, logged, cached, or put on telemetry.
  * Auth scheme prefixes survive: ``Authorization: Bearer <tok>`` becomes
    ``Authorization: Bearer [REDACTED:auth_header]``.
  * ``data:image/...`` URIs and image base64 blobs are exempt.
  * Inbound: ``scan_inbound`` looks for prompt-injection markers in model output.
    ``PAL_GUARDRAIL_INBOUND`` = block | warn | log (default warn). Only ``block``
    raises (``GuardrailBlocked``).
  * Fail-open: any internal error returns the input unchanged.
  * Telemetry / audit record only ``kind`` + ``count``, never matched text.

Env:
  PAL_GUARDRAIL           1 (default) | 0/false/off  -> master switch
  PAL_GUARDRAIL_INBOUND   block | warn (default) | log
  PAL_TOOL_LOG            audit log path (default ~/.cache/pal/tool-calls.log)
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

AUTH_KIND = "auth_header"


class GuardrailBlocked(RuntimeError):
    """Raised by scan_inbound in block mode."""


# ---- config ---------------------------------------------------------------
def is_enabled() -> bool:
    return os.getenv("PAL_GUARDRAIL", "1").strip().lower() not in ("0", "false", "off", "no", "")


def inbound_mode() -> str:
    m = os.getenv("PAL_GUARDRAIL_INBOUND", "warn").strip().lower()
    return m if m in ("block", "warn", "log") else "warn"


def _audit_path() -> Path:
    return Path(os.getenv("PAL_TOOL_LOG", str(Path.home() / ".cache/pal/tool-calls.log")))


# ---- patterns -------------------------------------------------------------
# (kind, regex, group index holding the secret; 0 = whole match). Order matters:
# earlier patterns claim text first.
_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), 0),
    # Authorization-style headers: keep header name + scheme, redact the credential
    (
        AUTH_KIND,
        re.compile(
            r"(?i)\b((?:proxy-)?authorization\s*[:=]\s*[\"']?(?:bearer|basic|token|digest|negotiate|apikey|hmac)\s+)"
            r"([A-Za-z0-9._~+/=\-:,\"]{6,})"
        ),
        2,
    ),
    (
        AUTH_KIND,
        re.compile(r"(?i)\b((?:x-api-key|x-auth-token|api-key)\s*[:=]\s*[\"']?)([A-Za-z0-9._~+/=\-]{8,})"),
        2,
    ),
    (AUTH_KIND, re.compile(r"(?i)\b(bearer\s+)(eyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-.]+|[A-Za-z0-9._~+/=\-]{20,})"), 2),
    ("cookie", re.compile(r"(?i)\b((?:set-)?cookie\s*:\s*)([^\r\n]{8,})"), 2),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"), 0),
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), 0),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"), 0),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), 0),
    ("google_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), 0),
    ("api_key", re.compile(r"\b(?:sk|gsk|xai|pk|rk)-[A-Za-z0-9_\-]{20,}\b"), 0),
    (
        "secret_assign",
        re.compile(
            r"(?i)\b((?:[a-z0-9_]*(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|"
            r"client[_-]secret|private[_-]key))\s*[\"']?\s*[:=]\s*[\"']?)([^\s\"',;&]{6,})"
        ),
        2,
    ),
    ("url_creds", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:([^\s/@]{3,})@"), 1),
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), 0),
    ("ssn", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"), 0),
    ("credit_card", re.compile(r"\b(?:\d[ \-]?){13,19}\b"), 0),  # Luhn-verified below
]

_INJECTION: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_instructions",
        re.compile(
            r"(?i)\b(ignore|disregard|forget)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all)\b[^.\n]{0,30}\b(instructions?|rules?|prompts?)\b"
        ),
    ),
    (
        "role_override",
        re.compile(
            r"(?i)\byou\s+are\s+now\s+(?:a|an|in)\b|\bnew\s+system\s+prompt\b|\bact\s+as\s+(?:dan|root|admin)\b"
        ),
    ),
    ("chat_template_token", re.compile(r"<\|(?:im_start|im_end|system|endoftext)\|>|\[/?INST\]|<<SYS>>")),
    (
        "prompt_leak",
        re.compile(r"(?i)\b(reveal|print|show|repeat)\b[^.\n]{0,30}\b(system\s+prompt|hidden\s+instructions)\b"),
    ),
    ("system_override", re.compile(r"(?im)^\s*(?:#+\s*|\[|<)?(?:system|assistant|developer)\s*(?:override|prompt|message|instruction)s?\s*[\]>:]|\bsystem\s*:\s*override\b|\b(?:override|bypass)\b[^.\n]{0,20}\b(?:system|safety)\b[^.\n]{0,20}\b(?:prompt|instructions?|rules?|guardrails?)\b")),
    ("fenced_system", re.compile(r"(?i)```\s*(?:system|instructions?|developer)\b|<(?:system|instructions?)>")),
    (
        "tool_call_spoof",
        re.compile(r"(?i)<tool_(?:call|use)\b|<function_calls?>|<function=|<tool_result\b|\"tool_calls?\"\s*:|\{\s*\"name\"\s*:\s*\"[^\"]+\"\s*,\s*\"(?:arguments|args|parameters)\""),
    ),
    ("exfil_instruction", re.compile(r"(?i)\b(send|post|upload|exfiltrate)\b[^.\n]{0,60}\b(to|at)\s+https?://")),
]

# keys whose values are never text to scan
_SKIP_KEYS = frozenset({"role", "model", "type", "mime_type", "mimeType", "media_type"})
_BINARY_KEYS = frozenset({"data", "bytes", "image", "b64_json", "base64"})


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


# ---- context --------------------------------------------------------------
@dataclass
class MaskContext:
    """Per-call restore map. In-memory only; excluded from repr to avoid log leaks."""

    _restore: dict[str, str] = field(default_factory=dict, repr=False)
    _seen: dict[tuple[str, str], str] = field(default_factory=dict, repr=False)
    counts: Counter = field(default_factory=Counter)

    def placeholder(self, kind: str, value: str) -> str:
        self.counts[kind] += 1
        if kind == AUTH_KIND:
            ph = f"[REDACTED:{AUTH_KIND}]"
            self._restore.setdefault(ph, value)
            # ambiguous if several distinct creds share one literal placeholder
            if self._restore[ph] != value:
                self._restore[ph] = ""
            return ph
        key = (kind, value)
        ph = self._seen.get(key)
        if ph is None:
            n = sum(1 for k in self._seen if k[0] == kind) + 1
            ph = f"[REDACTED:{kind}:{n}]"
            self._seen[key] = ph
            self._restore[ph] = value
        return ph

    def __bool__(self) -> bool:
        return bool(self.counts)


# ---- core text masking ----------------------------------------------------
_DATA_IMAGE = re.compile(r"data:image/[A-Za-z0-9.+\-]+;base64,[A-Za-z0-9+/=_\-]+")


def _mask_text(text: str, ctx: MaskContext) -> str:
    if not text or text.startswith("data:image/"):
        return text
    if "data:image/" in text:  # embedded (markdown/JSON) image blobs: mask only the gaps
        out, last = [], 0
        for m in _DATA_IMAGE.finditer(text):
            out.append(_mask_plain(text[last : m.start()], ctx))
            out.append(m.group(0))
            last = m.end()
        out.append(_mask_plain(text[last:], ctx))
        return "".join(out)
    return _mask_plain(text, ctx)


def _mask_plain(text: str, ctx: MaskContext) -> str:
    if not text:
        return text
    for kind, rx, grp in _PATTERNS:
        if kind == "credit_card":

            def _cc(m: re.Match[str], kind: str = kind) -> str:
                digits = re.sub(r"\D", "", m.group(0))
                if 13 <= len(digits) <= 19 and _luhn(digits):
                    return ctx.placeholder(kind, m.group(0))
                return m.group(0)

            text = rx.sub(_cc, text)
            continue

        def _sub(m: re.Match[str], kind: str = kind, grp: int = grp) -> str:
            secret = m.group(grp)
            if secret.startswith("[REDACTED:"):
                return m.group(0)
            ph = ctx.placeholder(kind, secret)
            if grp == 0:
                return ph
            s, e = m.start(grp) - m.start(0), m.end(grp) - m.start(0)
            whole = m.group(0)
            return whole[:s] + ph + whole[e:]

        text = rx.sub(_sub, text)
    return text


def _walk(obj: Any, ctx: MaskContext, key: str | None = None) -> Any:
    if isinstance(obj, str):
        if key in _SKIP_KEYS:
            return obj
        return _mask_text(obj, ctx)
    if isinstance(obj, dict):
        mime = str(obj.get("mime_type") or obj.get("mimeType") or obj.get("media_type") or "")
        is_image = mime.startswith("image/") or str(obj.get("type", "")).startswith("image")
        out = {}
        for k, v in obj.items():
            if is_image and k in _BINARY_KEYS:
                out[k] = v
            elif k == "source" and isinstance(v, dict) and v.get("type") == "base64":
                out[k] = v
            else:
                mk = _mask_text(k, ctx) if isinstance(k, str) else k
                out[mk] = _walk(v, ctx, k if isinstance(k, str) else None)
        return out
    if isinstance(obj, list):
        return [_walk(v, ctx, key) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_walk(v, ctx, key) for v in obj)
    if isinstance(obj, (set, frozenset)):
        return type(obj)(_walk(v, ctx, key) for v in obj)
    if isinstance(obj, (bytes, bytearray)) and key not in _BINARY_KEYS:
        try:
            return _mask_text(bytes(obj).decode("utf-8"), ctx).encode("utf-8")
        except UnicodeDecodeError:
            return obj
    return obj


# ---- public API -----------------------------------------------------------
def mask_outbound(payload: Any) -> tuple[Any, MaskContext]:
    """Redact ``payload`` (str or arbitrarily nested dict/list). Never raises."""
    ctx = MaskContext()
    if not is_enabled() or payload is None:
        return payload, ctx
    try:
        masked = _walk(payload, ctx)
    except Exception as exc:  # fail-open
        log.warning("guardrail mask_outbound failed open: %s", exc.__class__.__name__)
        return payload, MaskContext()
    if ctx:
        _record("outbound", ctx.counts)
    return masked, ctx


def unmask(text: Any, ctx: MaskContext | None) -> Any:
    """Restore placeholders in ``text`` from ``ctx``. Never raises."""
    if not isinstance(text, str) or ctx is None or not ctx._restore:
        return text
    try:
        for ph, val in ctx._restore.items():
            if val and ph in text:
                text = text.replace(ph, val)
        return text
    except Exception:
        return text


def redact_text(text: str) -> str:
    """One-shot redaction (no restore) for audit/log lines."""
    if not is_enabled() or not text:
        return text
    try:
        return _mask_text(text, MaskContext())
    except Exception:
        return text


def scan_inbound(text: Any, mode: str | None = None) -> list[str]:
    """Scan model output for injection markers. Returns matched kinds.

    warn -> logs a warning; log -> debug only; block -> raises GuardrailBlocked.
    """
    if not is_enabled() or not isinstance(text, str) or not text:
        return []
    try:
        hits = [k for k, rx in _INJECTION if rx.search(text)]
    except Exception:
        return []
    if not hits:
        return []
    mode = mode or inbound_mode()
    _record("inbound", Counter(hits))
    if mode == "block":
        raise GuardrailBlocked(f"inbound injection markers blocked: {','.join(sorted(hits))}")
    (log.warning if mode == "warn" else log.debug)("guardrail inbound injection markers: %s", ",".join(sorted(hits)))
    return hits


def guard_response(resp: Any, ctx: MaskContext | None) -> Any:
    """Scan then unmask ``resp.content`` in place (ModelResponse-like). Fail-open except block."""
    if not is_enabled() or resp is None:
        return resp
    try:
        content = getattr(resp, "content", None)
        if isinstance(content, str):
            scan_inbound(content)
            resp.content = unmask(content, ctx)
    except GuardrailBlocked:
        raise
    except Exception as exc:
        log.debug("guardrail guard_response failed open: %s", exc.__class__.__name__)
    return resp


# ---- telemetry / audit (kind + count only) --------------------------------
_STATS: Counter = Counter()
_LOCK = threading.Lock()


def stats() -> dict[str, int]:
    with _LOCK:
        return dict(_STATS)


def _record(direction: str, counts: Counter) -> None:
    clean = {str(k): int(v) for k, v in counts.items()}
    with _LOCK:
        for k, v in clean.items():
            _STATS[f"{direction}:{k}"] += v
    try:
        p = _audit_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps({"ts": time.time(), "event": "guardrail", "dir": direction, "kinds": clean}) + "\n")
    except OSError as exc:
        log.debug("guardrail audit write failed: %s", exc)
