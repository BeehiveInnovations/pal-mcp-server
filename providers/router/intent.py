"""User-intent classification + authorization-scope extraction.

This is the stage the architecture puts BEFORE llm planning: decide what the
user actually asked for, and derive the hard authorization boundary from THEIR
words — not from directory names, filenames, or leftover security context.

Two jobs:

1. :func:`classify_intent` — is this a security task, a git operation, a plain
   filesystem op, or general work? The key rule (fixing the "security-mission
   overinterpretation" bug): a security intent needs a security VERB applied to
   a TARGET (scan / enumerate / exploit a host/url/domain/api). A keyword that
   merely appears as the OBJECT of a filesystem/git verb — "create a directory
   called enumeration", "commit exploit.py", "push the auth module" — is NOT a
   security task.

2. :func:`scope_for_request` — build the :class:`~providers.tooling.authz.ToolScope`
   that the executor will enforce. For a git op with explicit paths ("push
   README.md", "commit a.txt and b.txt", "push src/") the scope is ``explicit``
   and a hard allow-list; a vague git op ("commit my changes") is ``open``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from providers.tooling.authz import ToolScope

# security VERBS: the user wants an offensive/recon action performed
_SEC_VERB = re.compile(
    r"\b(scan|enumerate|enum|recon|fuzz|brute[\s-]?force|exploit|attack|"
    r"pentest|pen[\s-]?test|probe|crawl|spider|nmap|nuclei|ffuf|gobuster|"
    r"sqlmap|nikto|subfinder|amass|httpx|dirb|dirbuster|hydra|test(?:ing)?\s+"
    r"(?:for|the)\s+(?:vuln|xss|ssrf|idor|sqli|rce|lfi|csrf)|hack|compromise|"
    r"take\s?over|bypass\s+(?:auth|login|waf))\b",
    re.IGNORECASE,
)
# a target that makes a security verb a real security task
_SEC_TARGET = re.compile(
    r"\b([a-z0-9-]+\.)+[a-z]{2,}\b"                 # domain
    r"|\bhttps?://|\b\d{1,3}(?:\.\d{1,3}){3}\b"      # url / ip
    r"|\b(host|hosts|target|endpoint|api|server|port|subdomain|url)\b",
    re.IGNORECASE,
)
# plain filesystem / vcs verbs — these are NORMAL ops, never security
_FS_VERB = re.compile(
    r"\b(create|make|mkdir|new|touch|move|mv|rename|copy|cp|delete|rm|remove|"
    r"write|save|organi[sz]e|list|show|read|cat|open|add|stage|commit|push|"
    r"pull|clone|checkout|merge|rebase|tag)\b",
    re.IGNORECASE,
)
_GIT_HINT = re.compile(r"\b(git|commit|staged?|push|pull|repo|repository|branch|pr\b)", re.IGNORECASE)
# a vulnerability-class noun + an assessment verb is also a security task
# ("test this API for vulnerabilities", "check the login for IDOR")
_VULN_NOUN = re.compile(
    r"\b(vulnerab\w*|xss|ssrf|idor|sqli|sql injection|rce|lfi|rfi|csrf|xxe|ssti|"
    r"open redirect|privilege escalation|privesc|cve-\d|security (?:hole|flaw|bug|issue))\b",
    re.IGNORECASE,
)
_ASSESS_VERB = re.compile(
    r"\b(test|assess|check|audit|find|hunt|look\s+for|probe|analy[sz]e|review|"
    r"evaluate|inspect|search\s+for)\b",
    re.IGNORECASE,
)


@dataclass
class Intent:
    kind: str = "general"      # security | git | fileops | general
    is_security: bool = False
    git_op: str = ""           # push | commit | add | ""
    explicit_paths: tuple[str, ...] = field(default_factory=tuple)
    scope_mode: str = "open"   # explicit | open


_PATH_RE = re.compile(
    r"(?<![\w./-])("                    # not mid-token
    r"[\w./-]+\.[A-Za-z0-9]{1,8}"       # a.txt, src/app.js, README.md
    r"|[\w-]+/(?:\*\*|\*)?"             # src/  src/**  src/*
    r")"
)
_STOPWORDS = {"e.g", "i.e", "etc", "vs", "a.k.a"}


def _extract_paths(text: str) -> list[str]:
    """Pull explicit file/dir tokens the user named, in order, de-duplicated."""
    out: list[str] = []
    for m in _PATH_RE.finditer(text or ""):
        tok = m.group(1).strip().rstrip(".,;")
        low = tok.lower()
        if low in _STOPWORDS or tok in out:
            continue
        # a bare "word/" directory normalises to a dir prefix
        out.append(tok)
    return out


def _git_op(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"\bpush\b", t):
        return "push"
    if re.search(r"\bcommit\b", t):
        return "commit"
    if re.search(r"\b(add|stage)\b", t) and _GIT_HINT.search(t):
        return "add"
    return ""


def classify_intent(request: str) -> Intent:
    text = request or ""
    low = text.lower()

    # --- security? requires a security VERB *and* a plausible target, and must
    #     NOT merely be a filesystem/git verb acting on a keyword object. ------
    sec_verb = bool(_SEC_VERB.search(text))
    sec_target = bool(_SEC_TARGET.search(text))
    starts_fs = bool(re.match(r"^\s*(?:please\s+|can you\s+|could you\s+)?" + _FS_VERB.pattern, low))
    vuln_hunt = bool(_VULN_NOUN.search(text)) and bool(_ASSESS_VERB.search(text))
    is_security = ((sec_verb and sec_target) or vuln_hunt) and not starts_fs

    # --- git op? ------------------------------------------------------------
    gop = _git_op(text)
    if gop:
        paths = _extract_paths(text)
        # "push everything/all/my changes" => open scope (no explicit allow-list)
        vague = bool(re.search(r"\b(everything|all|all changes|my changes|the repo|all files)\b", low))
        if paths and not vague:
            return Intent(kind="git", is_security=False, git_op=gop,
                          explicit_paths=tuple(paths), scope_mode="explicit")
        return Intent(kind="git", is_security=False, git_op=gop, scope_mode="open")

    if is_security:
        return Intent(kind="security", is_security=True, scope_mode="open")

    if _FS_VERB.search(text):
        return Intent(kind="fileops", is_security=False, scope_mode="open")

    return Intent(kind="general", is_security=False, scope_mode="open")


def scope_for_request(request: str, cwd: str | None = None) -> ToolScope:
    """Build the authorization boundary the executor will enforce."""
    it = classify_intent(request)
    cwd = cwd or os.getcwd()
    if it.kind == "git" and it.scope_mode == "explicit":
        return ToolScope(
            intent=f"git_{it.git_op or 'op'}",
            authorized_paths=it.explicit_paths,
            scope_mode="explicit",
            allow_scope_expansion=False,
            external_ok=True,
            cwd=cwd,
        )
    return ToolScope(
        intent=it.kind,
        scope_mode="open",
        allow_scope_expansion=False,
        external_ok=True,
        cwd=cwd,
    )
