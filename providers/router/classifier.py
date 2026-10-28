"""Prompt-content classifier.

Cheap regex heuristics that inspect the user's actual prompt (and any
attached file list) to pick a tighter task category than the tool's static
`get_model_category()`.  Returns the tool's original category unchanged when
no strong signal fires so the caller can fall through safely.

Signals (highest wins):
    security_permissive     recon / attack-surface / vuln hunting language
    long_context_bulk       > LONG_CTX_THRESHOLD bytes of attached files
    structured_extract      "return json", "schema", "extract fields"
    long_form_prose         "write a report", "post-mortem", "release notes"
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# byte total across attached files that flips to bulk mode
LONG_CTX_THRESHOLD = int(os.getenv("PAL_LONG_CTX_BYTES", "300000"))

_SEC_RE = re.compile(
    r"\b(recon|subdomain|nuclei|ffuf|amass|takeover|ssrf|idor|xss|sqli|"
    r"csrf|xxe|rce|lfi|rfi|smuggling|prototype pollution|jwt|oauth attack|"
    r"exploit|payload|bypass|attack surface|bug bounty|pentest)\b",
    re.IGNORECASE,
)

_STRUCT_RE = re.compile(
    r"\b(return\s+json|json\s+schema|extract\s+fields|parse\s+into|" r"as\s+a\s+json|structured\s+output|schema:)",
    re.IGNORECASE,
)

_PROSE_RE = re.compile(
    r"\b(write\s+a\s+report|post-?mortem|release\s+notes|executive\s+summary|"
    r"draft\s+a\s+writeup|remediation\s+report|vulnerability\s+report)\b",
    re.IGNORECASE,
)


def is_enabled() -> bool:
    return os.getenv("PAL_CLASSIFIER", "1") not in ("0", "false", "no")


def _files_byte_total(paths: list[str] | None) -> int:
    if not paths:
        return 0
    total = 0
    for p in paths:
        try:
            total += Path(p).stat().st_size
        except OSError:
            pass
    return total


def classify(prompt: str, files: list[str] | None = None, tool_default: str = "") -> str:
    """Return a category string. Falls back to `tool_default` on no match."""
    if not is_enabled():
        return tool_default
    text = prompt or ""
    if _SEC_RE.search(text):
        # A security keyword appearing only as the OBJECT of a filesystem/git
        # verb ("commit exploit.py", "mkdir enumeration") is NOT a security
        # task — do not route it to the permissive security model.
        try:
            from providers.router import intent as _intent

            it = _intent.classify_intent(text)
            if it.kind in ("git", "fileops") and not it.is_security:
                pass  # fall through to the non-security signals below
            else:
                return "security_permissive"
        except Exception:
            return "security_permissive"
    if _files_byte_total(files) > LONG_CTX_THRESHOLD:
        return "long_context_bulk"
    if _STRUCT_RE.search(text):
        return "structured_extract"
    if _PROSE_RE.search(text):
        return "long_form_prose"
    return tool_default


# Preferred model per PAL classifier category. Order is intent; the router
# picks the first entry available with a keyed provider (and not blacklisted).
CATEGORY_PREFERENCES: dict[str, tuple[str, ...]] = {
    "security_permissive": ("gpt-oss-120b", "openai/gpt-oss-120b", "nemotron-3-nano:30b", "openrouter/free", "grok-4-fast"),
    "long_context_bulk": ("nemotron-3-nano:30b", "openrouter/free", "flash-lite", "gemini-3.5-flash-lite"),
    "structured_extract": ("gemini-3.5-flash-lite", "flash-lite", "qwen3", "openrouter/free"),
    "long_form_prose": ("gpt-oss-120b", "openai/gpt-oss-120b", "command-r-08-2024", "gemini-3.5-flash-lite"),
}
