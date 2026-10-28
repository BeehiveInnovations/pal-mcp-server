"""Headroom: shrink oversized tool/debate output before it eats context window.

Large recon/scan output (nmap -A on a /24, a nuclei JSON run, an sqlmap
verbose transcript, an HTTP response dump, a multi-round debate transcript)
routinely blows past what's useful to the model while adding nothing but
tokens. Headroom sits between masking and the size_guard/fallback/send path
and rewrites those *bodies* down to a bounded, information-dense form —
counts, unique findings, head/tail slices — while leaving canonical evidence
and outbound tool arguments untouched.

Pipeline position (per call):
    mask_outbound(payload)          # guardrail.py — credential/PII redaction
      -> headroom_adapter.compress_payload(masked)   # <— this module
      -> size_guard.check_or_reroute(...)            # cap check on the
         (compression can only shrink the estimate, never grow it, so
         running headroom first can only help a borderline-over-cap prompt
         clear the gate — it never hides an over-cap prompt from the guard)
      -> fallback_chain.call_with_fallback(...)       # resilience/retry
      -> provider.generate_content(...)               # send

Design rules (mirrors guardrail.py's contract):
  * NEVER touch canonical evidence. Any dict carrying a truthy
    ``canonical``, ``evidence``, or ``poc`` key, or a string tagged via
    ``mark_canonical()``, passes through byte-for-byte. When in doubt about
    whether a blob is evidence, don't compress it.
  * NEVER alter tool call arguments (the command/request about to be sent
    downstream). Only tool *results* (stdout, response bodies, prior-turn
    transcripts) already inside a payload are candidates.
  * Fail-open: any internal error returns the input unchanged and logs a
    warning; headroom never turns into an outage.
  * Compression is lossy-summarize, not truncate-and-hope: it keeps
    structure (counts, uniques, severities, status codes) so a downstream
    reader can still reason about what happened, plus a retrieval handle
    so the original bytes are one ``safe_retrieve()`` call away.

Env:
  PAL_HEADROOM              1 (default) | 0/false/off -> master switch
  PAL_HEADROOM_MIN_BYTES    minimum blob size before compression kicks in
                            (default 4000)
  PAL_HEADROOM_KEEP_HEAD    lines/bytes kept from the start of a blob
  PAL_HEADROOM_KEEP_TAIL    lines/bytes kept from the end of a blob
  PAL_HEADROOM_MAX_ITEMS    max structured findings kept verbatim per class
                            before the rest are counted-and-dropped
  PAL_HEADROOM_STORE_DIR    on-disk store for safe_retrieve() originals
                            (default ~/.cache/pal/headroom/)
  PAL_HEADROOM_PROXY_URL    optional external compression proxy (e.g. an
                            LLMLingua-style service). If set AND healthy,
                            used instead of the local heuristics below.
  PAL_HEADROOM_PROXY_TIMEOUT  proxy request timeout in seconds (default 3)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_CANONICAL_KEYS = ("canonical", "evidence", "poc", "raw_evidence")

_STATS_LOCK = threading.Lock()
_STATS = {
    "seen": 0,
    "compressed": 0,
    "skipped_canonical": 0,
    "skipped_small": 0,
    "bytes_in": 0,
    "bytes_out": 0,
    "errors": 0,
    "proxy_used": 0,
    "proxy_failed": 0,
}

_STORE_DIR = Path(os.getenv("PAL_HEADROOM_STORE_DIR", str(Path.home() / ".cache/pal/headroom")))

_PROXY_HEALTH: dict[str, Any] = {"ok": None, "ts": 0.0}
_PROXY_HEALTH_TTL = 30.0


# ---- config -----------------------------------------------------------


def is_enabled() -> bool:
    return os.getenv("PAL_HEADROOM", "1") not in ("0", "false", "no")


def _min_bytes() -> int:
    # Headroom-ultra compresses smaller blobs too (lower threshold by default).
    default = "200" if os.getenv("PAL_HEADROOM_MODE", "").lower() == "ultra" else "4000"
    return int(os.getenv("PAL_HEADROOM_MIN_BYTES", default))


def _keep_head() -> int:
    return int(os.getenv("PAL_HEADROOM_KEEP_HEAD", "40"))


def _keep_tail() -> int:
    return int(os.getenv("PAL_HEADROOM_KEEP_TAIL", "15"))


def _max_items() -> int:
    return int(os.getenv("PAL_HEADROOM_MAX_ITEMS", "25"))


def _proxy_url() -> str | None:
    return os.getenv("PAL_HEADROOM_PROXY_URL") or None


def _proxy_timeout() -> float:
    return float(os.getenv("PAL_HEADROOM_PROXY_TIMEOUT", "3"))


# ---- canonical-evidence guard ------------------------------------------


def _is_canonical(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(obj.get(k) for k in _CANONICAL_KEYS)
    return False


def mark_canonical(text: str) -> str:
    """Wrap a string so compress_* treats it as canonical evidence and
    passes it through untouched, even outside a dict wrapper."""
    return f"\x00CANONICAL\x00{text}"


def _unwrap_canonical(text: str) -> tuple[str, bool]:
    if isinstance(text, str) and text.startswith("\x00CANONICAL\x00"):
        return text[len("\x00CANONICAL\x00") :], True
    return text, False


# ---- retrieval store -----------------------------------------------------


def _store(original: str) -> str:
    """Persist the untouched original and return a short retrieval handle."""
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(original.encode("utf-8", errors="replace")).hexdigest()[:24]
    p = _STORE_DIR / f"{key}.txt"
    try:
        if not p.exists():
            p.write_text(original, encoding="utf-8", errors="replace")
    except OSError as exc:
        log.warning("headroom: store failed open: %s", exc.__class__.__name__)
    return f"headroom://{key}"


def safe_retrieve(handle: str) -> str | None:
    """Return the original blob for a ``headroom://<key>`` handle, or None
    if unknown/unreadable. Never raises."""
    try:
        if not handle or not handle.startswith("headroom://"):
            return None
        key = handle[len("headroom://") :]
        if not re.fullmatch(r"[0-9a-f]{24}", key):
            return None
        p = _STORE_DIR / f"{key}.txt"
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # fail-open
        log.warning("headroom: safe_retrieve failed open: %s", exc.__class__.__name__)
        return None


# ---- proxy health --------------------------------------------------------


def proxy_healthy() -> bool:
    """Cheap, cached health check for an optional local compression proxy.
    Fails closed (returns False) on any error so callers fall back to the
    local heuristics below."""
    url = _proxy_url()
    if not url:
        return False
    now = time.time()
    if _PROXY_HEALTH["ok"] is not None and now - _PROXY_HEALTH["ts"] < _PROXY_HEALTH_TTL:
        return bool(_PROXY_HEALTH["ok"])
    ok = False
    try:
        import urllib.request

        req = urllib.request.Request(url.rstrip("/") + "/health", method="GET")
        with urllib.request.urlopen(req, timeout=_proxy_timeout()) as resp:
            ok = 200 <= resp.status < 300
    except Exception as exc:
        log.debug("headroom: proxy health check failed: %s", exc.__class__.__name__)
        ok = False
    _PROXY_HEALTH.update(ok=ok, ts=now)
    return ok


def _proxy_compress(text: str, kind: str) -> str | None:
    """Best-effort call to the external proxy. Returns None on any failure
    so the caller falls back to local heuristics (fail-open)."""
    url = _proxy_url()
    if not url or not proxy_healthy():
        return None
    try:
        import urllib.request

        body = json.dumps({"kind": kind, "text": text}).encode("utf-8")
        req = urllib.request.Request(
            url.rstrip("/") + "/compress",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_proxy_timeout()) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        with _STATS_LOCK:
            _STATS["proxy_used"] += 1
        return data.get("text")
    except Exception as exc:
        log.debug("headroom: proxy compress failed open: %s", exc.__class__.__name__)
        with _STATS_LOCK:
            _STATS["proxy_failed"] += 1
        return None


# ---- format detection -----------------------------------------------------

_NMAP_HINT = re.compile(r"Starting Nmap|Nmap scan report for|PORT\s+STATE\s+SERVICE", re.I)
_NUCLEI_HINT = re.compile(r'"template-id"|\[[a-z0-9-]+\]\s+\[\w+\]\s+\[\w+\]', re.I)
_SQLMAP_HINT = re.compile(r"sqlmap resumed|the back-end DBMS is|Parameter:.*is vulnerable", re.I)
_HTTP_HINT = re.compile(r"^HTTP/\d(\.\d)?\s+\d{3}", re.M)


def _detect_kind(text: str) -> str:
    stripped = text.lstrip()
    if _NMAP_HINT.search(text):
        return "nmap"
    if _SQLMAP_HINT.search(text):
        return "sqlmap"
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(text)
            return "json"
        except (ValueError, TypeError):
            pass
    if _NUCLEI_HINT.search(text):
        return "nuclei"
    if _HTTP_HINT.search(text):
        return "http"
    # log-ish: many lines, mostly short, timestamps common
    if text.count("\n") > 50:
        return "log"
    return "text"


# ---- per-format compressors ------------------------------------------------
# Each takes the raw text and returns a bounded summary string. None of
# these mutate the input; they only ever read it.


def _head_tail_lines(lines: list[str], head: int, tail: int) -> list[str]:
    if len(lines) <= head + tail:
        return lines
    dropped = len(lines) - head - tail
    return lines[:head] + [f"... [{dropped} lines omitted by headroom] ..."] + lines[-tail:]


def _compress_nmap(text: str) -> str:
    lines = text.splitlines()
    keep = [ln for ln in lines if re.search(r"Nmap scan report|open|filtered|closed|OS details|Service Info", ln, re.I)]
    hosts_up = len(re.findall(r"Nmap scan report for", text))
    open_ports = len(re.findall(r"^\d+/\w+\s+open", text, re.M))
    header = f"[headroom: nmap summary — {hosts_up} host(s), {open_ports} open port(s)]"
    body = _head_tail_lines(keep, _keep_head(), _keep_tail())
    return header + "\n" + "\n".join(body)


def _compress_nuclei(text: str) -> str:
    # nuclei -jsonl (one JSON object per line) or plain [tag] output
    findings = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
            findings.append(
                f"[{obj.get('info', {}).get('severity', '?')}] "
                f"{obj.get('template-id', '?')} -> {obj.get('matched-at', obj.get('host', '?'))}"
            )
        except (ValueError, TypeError):
            findings.append(ln)
    total = len(findings)
    kept = findings[: _max_items()]
    header = f"[headroom: nuclei summary — {total} finding(s), showing {len(kept)}]"
    return header + "\n" + "\n".join(kept)


def _compress_sqlmap(text: str) -> str:
    lines = text.splitlines()
    keep = [
        ln
        for ln in lines
        if re.search(
            r"back-end DBMS|Parameter:.*vulnerable|Type:|Title:|Payload:|available databases|current user|current database",
            ln,
            re.I,
        )
    ]
    header = "[headroom: sqlmap summary — confirmations + payload lines only]"
    body = _head_tail_lines(keep, _keep_head(), _keep_tail())
    return header + "\n" + "\n".join(body)


def _compress_http(text: str) -> str:
    lines = text.splitlines()
    # keep status line + headers verbatim, collapse body
    split_at = next((i for i, ln in enumerate(lines) if ln.strip() == ""), len(lines))
    head_part = lines[:split_at]
    body_part = lines[split_at:]
    body_bytes = sum(len(ln) for ln in body_part)
    if len("\n".join(body_part)) <= _min_bytes():
        return text
    body_kept = _head_tail_lines(body_part, _keep_head(), _keep_tail())
    header = f"[headroom: HTTP body summary — {body_bytes} bytes original]"
    return "\n".join(head_part) + "\n" + header + "\n" + "\n".join(body_kept)


def _compress_json(text: str) -> str:
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return _compress_log(text)

    def _walk(o: Any, depth: int = 0) -> Any:
        if isinstance(o, list):
            if len(o) > _max_items():
                return [_walk(x, depth + 1) for x in o[: _max_items()]] + [
                    f"... [{len(o) - _max_items()} more items omitted by headroom]"
                ]
            return [_walk(x, depth + 1) for x in o]
        if isinstance(o, dict):
            if _is_canonical(o):
                return o
            return {k: _walk(v, depth + 1) for k, v in o.items()}
        if isinstance(o, str) and len(o) > 2000:
            return o[:1500] + f"... [{len(o) - 1500} chars omitted by headroom]"
        return o

    trimmed = _walk(obj)
    return json.dumps(trimmed, ensure_ascii=False, indent=2)


def _compress_log(text: str) -> str:
    lines = text.splitlines()
    seen: dict[str, int] = {}
    first: dict[str, str] = {}
    order: list[str] = []
    for ln in lines:
        key = re.sub(r"\d+", "#", ln.strip())
        if key not in seen:
            order.append(key)
            first[key] = ln.rstrip()  # keep the real first-seen line, not the digit-masked key
        seen[key] = seen.get(key, 0) + 1
    dedup_repr = []
    for key in order[: _max_items()]:
        count = seen[key]
        dedup_repr.append(first[key] + (f"  [x{count}]" if count > 1 else ""))
    header = f"[headroom: log summary — {len(lines)} lines, {len(order)} unique pattern(s), showing {min(len(order), _max_items())}]"
    return header + "\n" + "\n".join(dedup_repr)


def _compress_text(text: str) -> str:
    lines = text.splitlines()
    kept = _head_tail_lines(lines, _keep_head(), _keep_tail())
    return "\n".join(kept)


_COMPRESSORS = {
    "nmap": _compress_nmap,
    "nuclei": _compress_nuclei,
    "sqlmap": _compress_sqlmap,
    "http": _compress_http,
    "json": _compress_json,
    "log": _compress_log,
    "text": _compress_text,
}


# ---- public entry points ---------------------------------------------------


_PROSE_KINDS = ("log", "text")



# ---- real Headroom (headroom-ai) SmartCrusher backend ---------------------
_SMARTCRUSHER = None


def _headroom_crush(text: str) -> str | None:
    """Compress a blob with the real Headroom SmartCrusher (headroom-ai).

    Returns the compressed string when it is genuinely smaller, else None so the
    caller falls back to the proxy / homegrown summarisers (fail-open). Disable
    with PAL_HEADROOM_ENGINE=local.
    """
    if os.getenv("PAL_HEADROOM_ENGINE", "headroom").lower() != "headroom":
        return None
    global _SMARTCRUSHER
    try:
        if _SMARTCRUSHER is None:
            from headroom import SmartCrusher

            _SMARTCRUSHER = SmartCrusher()
        r = _SMARTCRUSHER.crush(text)
        comp = getattr(r, "compressed", None)
        if comp and getattr(r, "was_modified", False) and len(comp) < len(text):
            with _STATS_LOCK:
                _STATS["headroom_used"] = _STATS.get("headroom_used", 0) + 1
            return comp
    except Exception as exc:  # fail-open
        log.debug("headroom: SmartCrusher failed open: %s", exc.__class__.__name__)
    return None


def compress_tool_result(text: str, tool_name: str | None = None, structured_only: bool = False) -> str:
    """Compress a single tool result blob (stdout/response body). Returns the
    text unchanged if headroom is disabled, the blob is small, marked
    canonical, or anything goes wrong (fail-open).

    ``structured_only``: only compress recognised structured scanner/HTTP/JSON
    output; never apply the generic log/text summarisers. Used for prompts and
    system/user messages, which are prose the model must read verbatim."""
    with _STATS_LOCK:
        _STATS["seen"] += 1

    if not isinstance(text, str) or not is_enabled():
        return text

    text, canonical = _unwrap_canonical(text)
    if canonical:
        with _STATS_LOCK:
            _STATS["skipped_canonical"] += 1
        return text

    if len(text) < _min_bytes():
        with _STATS_LOCK:
            _STATS["skipped_small"] += 1
        return text

    try:
        kind = _detect_kind(text)
        if structured_only and kind in _PROSE_KINDS:
            return text
        crushed = _headroom_crush(text)
        if crushed is not None:
            summary = crushed
        else:
            proxied = _proxy_compress(text, kind)
            summary = proxied if proxied is not None else _COMPRESSORS.get(kind, _compress_text)(text)

        if len(summary) >= len(text):
            # never let a "compressor" grow the payload
            return text

        handle = _store(text)
        out = f"{summary}\n[headroom: full {kind} output retrievable via safe_retrieve('{handle}')]"

        with _STATS_LOCK:
            _STATS["compressed"] += 1
            _STATS["bytes_in"] += len(text)
            _STATS["bytes_out"] += len(out)
        return out
    except Exception as exc:  # fail-open — never block a send over a summarizer bug
        log.warning("headroom: compress_tool_result failed open (%s): %s", tool_name, exc.__class__.__name__)
        with _STATS_LOCK:
            _STATS["errors"] += 1
        return text


def compress_payload(payload: Any) -> Any:
    """Walk an outbound payload (post ``guardrail.mask_outbound``) and
    compress any oversized tool-result strings found in it.

    Only touches values under known tool-result keys/shapes so it can never
    reach into — and rewrite — the arguments of a pending tool call. Any
    dict/string flagged canonical is skipped. Fail-open on any error."""
    if not is_enabled():
        return payload
    try:
        return _walk_payload(payload)
    except Exception as exc:
        log.warning("headroom: compress_payload failed open: %s", exc.__class__.__name__)
        with _STATS_LOCK:
            _STATS["errors"] += 1
        return payload


_RESULT_KEYS = {"content", "output", "result", "stdout", "text", "body", "tool_result"}
_ARG_KEYS = {"arguments", "args", "input", "params", "tool_input", "command"}


def _walk_payload(obj: Any, in_args: bool = False) -> Any:
    if isinstance(obj, dict):
        if _is_canonical(obj):
            return obj
        role = obj.get("role")
        if role in ("system", "developer", "user", "assistant"):
            # Prompts, instructions, history and tool-call arguments are never
            # tool output. Only nested tool_result blocks (Anthropic-style, in a
            # list ``content``) are candidates; plain string content is verbatim.
            content = obj.get("content")
            if isinstance(content, list):
                out = dict(obj)
                out["content"] = [
                    _walk_payload(b, in_args=in_args) if isinstance(b, dict) and b.get("type") == "tool_result" else b
                    for b in content
                ]
                return out
            return obj
        out = {}
        for k, v in obj.items():
            child_in_args = in_args or (k in _ARG_KEYS)
            if isinstance(v, str) and k in _RESULT_KEYS and not child_in_args:
                out[k] = compress_tool_result(v)
            else:
                out[k] = _walk_payload(v, in_args=child_in_args)
        return out
    if isinstance(obj, list):
        return [_walk_payload(x, in_args=in_args) for x in obj]
    return obj


def compress_debate_state(state: Any) -> Any:
    """Compress prior-round debate transcripts before they're re-sent as
    context for the next round. Keeps each round's stance/conclusion line(s)
    and compresses only the bulk supporting text; never touches the current
    round's live prompt or any round flagged canonical (final verdict)."""
    if not is_enabled():
        return state
    try:
        if not isinstance(state, dict):
            return state
        rounds = state.get("rounds")
        if not isinstance(rounds, list):
            return state
        new_rounds = []
        for i, rnd in enumerate(rounds):
            if not isinstance(rnd, dict) or _is_canonical(rnd):
                new_rounds.append(rnd)
                continue
            is_last = i == len(rounds) - 1
            new_rnd = dict(rnd)
            for k, v in rnd.items():
                if isinstance(v, str) and k in ("argument", "response", "content", "transcript") and not is_last:
                    new_rnd[k] = compress_tool_result(v)
            new_rounds.append(new_rnd)
        out = dict(state)
        out["rounds"] = new_rounds
        return out
    except Exception as exc:
        log.warning("headroom: compress_debate_state failed open: %s", exc.__class__.__name__)
        with _STATS_LOCK:
            _STATS["errors"] += 1
        return state


def stats() -> dict:
    with _STATS_LOCK:
        d = dict(_STATS)
    d["ratio"] = (d["bytes_out"] / d["bytes_in"]) if d["bytes_in"] else None
    d["proxy_configured"] = bool(_proxy_url())
    d["proxy_healthy"] = proxy_healthy() if _proxy_url() else None
    return d
