"""Persistent, secret-masked input history for `pal chat`.

Phase 8: a Claude-Code-like input experience needs real history navigation
(Up/Down, Ctrl-P/Ctrl-N) backed by something more durable than
prompt_toolkit's in-memory `InMemoryHistory`. This module gives it a JSONL
log on disk, scoped to one REPL session (its own file, never mixed with any
other session's lines) and with obvious secrets masked before anything ever
touches the disk.

Design:
  * One file per session: ~/.pal/chat_history/<session_id>.jsonl
    "scoped to session" == its own file, so Up-arrow in session B never
    resurrects session A's lines. (Nothing to filter -- the scope IS the
    file.)
  * Append-only JSONL, one record per accepted line: {"ts", "session", "text"}.
  * `mask_secrets` runs on every line before it is written OR handed back to
    prompt_toolkit's in-memory list -- so a pasted API key never round-trips
    to disk in the clear, and Up-arrow recall shows the masked form too.
  * Implements prompt_toolkit's `History` interface so it drops straight into
    `PromptSession(history=...)` and gets its Up/Down/working-line/draft
    preservation machinery for free.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

try:
    from prompt_toolkit.history import History as _PTHistory
except ImportError:  # pragma: no cover - prompt_toolkit is an optional extra
    _PTHistory = object


def new_session_id() -> str:
    """One id per `pal chat` process -- ties the history file, not shared."""
    return f"{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def history_dir() -> Path:
    d = Path(os.getenv("PAL_CHAT_HISTORY_DIR", str(Path.home() / ".pal" / "chat_history")))
    # mode= is applied at mkdir(2) time (umask can only tighten it), so the leaf
    # dir is never briefly group/world-accessible; chmod covers a pre-existing dir.
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def history_path(session_id: str) -> Path:
    return history_dir() / f"{session_id}.jsonl"


# --- secret masking -------------------------------------------------------
# Conservative, high-precision patterns for things that are unambiguously a
# credential shape; false negatives are fine (best-effort), false positives
# on ordinary chat text are not.
_SECRET_PATTERNS = [
    # PEM private key blocks (multi-line; an unterminated paste is masked to end of text).
    # Must run before the generic key=value rule.
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.DOTALL),
        "<pem-private-key-redacted>",
    ),
    # HTTP Basic auth header; must precede the generic `authorization:` rule, which
    # would otherwise mask only the word "Basic" and leave the base64 credential.
    (re.compile(r"(?i)\bAuthorization\s*[:=]\s*Basic\s+[A-Za-z0-9+/=_-]{4,}"), "Authorization: Basic ***"),
    # Bare token form: require a digit, +, / or = so prose like "Basic principles" is untouched.
    (re.compile(r"\bBasic\s+(?=[A-Za-z0-9+/]*[0-9+/=])[A-Za-z0-9+/]{8,}={0,2}(?![A-Za-z0-9+/=])"), "Basic ***"),
    # user:pass@host in URLs
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^\s/:@]+:[^\s/@]+@"), r"\1***:***@"),
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"), "sk-***"),  # OpenAI-style
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA***"),  # AWS access key id
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "gh*_***"),  # GitHub tokens
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "xox*-***"),  # Slack tokens
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "<jwt-redacted>"),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|apikey|token|secret|password|passwd|authorization)\s*[:=]\s*['\"]?([^\s'\"]{4,})['\"]?"
        ),
        None,
    ),  # handled specially below (keep the key name, mask the value)
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{10,}\b"), "Bearer ***"),
]


def mask_secrets(text: str) -> str:
    """Best-effort redaction so obviously-secret-shaped substrings never hit disk."""
    if not text:
        return text
    out = text
    for pattern, repl in _SECRET_PATTERNS:
        if repl is None:
            out = pattern.sub(lambda m: f"{m.group(1)}={'*' * 3}", out)
        else:
            out = pattern.sub(repl, out)
    return out


class JsonlSessionHistory(_PTHistory):
    """prompt_toolkit `History` backed by a per-session JSONL file.

    Load reads back this session's own prior lines (masked, if this process
    restarted against an existing session id); store appends a masked
    record. Everything else (working-line index, draft preservation on
    Up/Down at the boundaries) is handled by prompt_toolkit's `Buffer`, which
    is why this class only has to satisfy the tiny `History` contract.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.path = history_path(session_id)
        super().__init__()

    def load_history_strings(self):
        lines: list[str] = []
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        rec = json.loads(raw)
                        lines.append(rec.get("text", ""))
                    except (ValueError, TypeError):
                        continue
        except FileNotFoundError:
            return []
        # prompt_toolkit wants most-recent-first
        return list(reversed(lines))

    def store_string(self, string: str) -> None:
        if not string.strip():
            return
        rec = {"ts": time.time(), "session": self.session_id, "text": mask_secrets(string)}
        try:
            # Create with 0600 atomically (no world-readable window); fchmod
            # tightens a pre-existing file that had looser permissions.
            fd = os.open(self.path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as fh:
                os.fchmod(fh.fileno(), 0o600)
                fh.write(json.dumps(rec) + "\n")
        except OSError:
            pass  # history is a convenience, never fatal to the chat itself
