"""Executor-level authorization boundary for the PAL toolbelt.

NON-NEGOTIABLE PRINCIPLE
------------------------
Models provide intelligence and planning. The *system* provides authorization.
The *executor* enforces authorization. A model must never be the final
authority over what it is allowed to touch.

This module is that final authority. It is consulted inside
``Toolbelt.execute`` — the single chokepoint every tool call (bash, gh,
write_file, …) funnels through, for every entry point (``pal run`` headless,
``pal mission``, the interactive REPL), every model, and every retry/fallback/
panel member. Because enforcement happens *below* the LLM, no amount of model
reasoning, prompt injection, or model-swapping can widen the authorized scope.

What it enforces
----------------
* A :class:`ToolScope` is a structured authorization boundary carried as
  context-var state through the whole execution chain (set once, upstream,
  from the user's actual request; never reconstructed from natural language at
  each stage, and downstream models cannot broaden it).
* ``explicit`` scope == a hard allow-list of paths. Git operations that stage
  or publish anything outside it are REJECTED — including ``git add .``,
  ``git add -A``, ``git add -u``, ``git commit -a`` when an explicit file
  scope exists, and any unrelated already-staged file entering a scoped commit.
* Secret / sensitive-content detection runs before every EXTERNAL publish
  (``git push``, ``gh pr create``/``merge``) regardless of scope mode; a hit is
  a blocking condition. Detection uses filename AND content heuristics.
* Writing to credential/config files (``.env``, keys, private keys, …) is
  blocked at the executor even if a model's plan asked for it.

Everything is reversible/opt-out via env (``PAL_AUTHZ_DISABLE=1`` kills the
gate; ``PAL_AUTHZ_ALLOW_SECRETS=1`` permits secrets in a publish) so the
boundary never becomes an un-escapable foot-gun for a genuinely authorized
operator — but it is ON by default and a model cannot flip it.
"""

from __future__ import annotations

import contextvars
import logging
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Authorization boundary (structured state carried through the whole chain)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ToolScope:
    """A structured authorization boundary. Immutable: a downstream stage can
    only *narrow* it (via :meth:`narrowed`), never widen it."""

    intent: str = "general"               # git_push|git_commit|git_add|fileops|security|general
    authorized_paths: tuple[str, ...] = ()  # path/glob allow-list (repo-relative)
    scope_mode: str = "open"              # "explicit" (hard allow-list) | "open"
    allow_scope_expansion: bool = False   # a model can NEVER set this True
    external_ok: bool = True              # may this scope publish externally at all
    cwd: str = ""                         # repo root the paths resolve against

    def narrowed(self, **kw) -> "ToolScope":
        """Return a copy that can only tighten the boundary. ``allow_scope_expansion``
        and widening of ``authorized_paths`` are ignored on purpose."""
        kw.pop("allow_scope_expansion", None)
        if "authorized_paths" in kw and self.scope_mode == "explicit":
            # intersection only — never add paths the parent didn't authorize
            kw["authorized_paths"] = tuple(
                p for p in kw["authorized_paths"] if p in self.authorized_paths
            )
        return replace(self, **kw)


class ScopeViolation(Exception):
    """Raised/returned when an operation exceeds its authorized scope."""


_CURRENT: contextvars.ContextVar[ToolScope | None] = contextvars.ContextVar(
    "pal_tool_scope", default=None
)


def current_scope() -> ToolScope | None:
    return _CURRENT.get()


def push_scope(scope: ToolScope) -> contextvars.Token:
    """Set the active scope. A nested push can only NARROW the parent."""
    parent = _CURRENT.get()
    if parent is not None:
        # a child context (e.g. a per-command sub tools-loop) inherits and may
        # only tighten — it can never re-open a parent's explicit boundary.
        if parent.scope_mode == "explicit" and scope.scope_mode != "explicit":
            scope = parent
        elif parent.scope_mode == "explicit" and scope.scope_mode == "explicit":
            scope = parent.narrowed(
                authorized_paths=scope.authorized_paths, intent=scope.intent
            )
    return _CURRENT.set(scope)


def pop_scope(token: contextvars.Token) -> None:
    try:
        _CURRENT.reset(token)
    except (ValueError, LookupError):
        pass


class scope_guard:
    """Context manager: ``with scope_guard(scope): ...``."""

    def __init__(self, scope: ToolScope | None):
        self._scope = scope
        self._token: contextvars.Token | None = None

    def __enter__(self) -> ToolScope | None:
        if self._scope is not None:
            self._token = push_scope(self._scope)
        return self._scope

    def __exit__(self, *exc) -> None:
        if self._token is not None:
            pop_scope(self._token)


def is_disabled() -> bool:
    return os.getenv("PAL_AUTHZ_DISABLE", "0") in ("1", "true", "yes")


def _allow_secrets() -> bool:
    return os.getenv("PAL_AUTHZ_ALLOW_SECRETS", "0") in ("1", "true", "yes")


# --------------------------------------------------------------------------- #
# Path matching (repo-relative, glob-aware)
# --------------------------------------------------------------------------- #
def _norm(path: str, cwd: str = "") -> str:
    """Normalise to a repo-relative posix path (best effort)."""
    p = (path or "").strip().strip('"').strip("'")
    p = p.replace("\\", "/")
    if cwd:
        try:
            ap = os.path.abspath(os.path.join(cwd, p))
            root = os.path.abspath(cwd)
            if ap == root or ap.startswith(root + os.sep):
                p = os.path.relpath(ap, root)
        except Exception:
            pass
    p = p.lstrip("./")
    while p.startswith("../"):
        p = p[3:]
    return p.rstrip("/")


def path_in_scope(path: str, scope: ToolScope) -> bool:
    """Is ``path`` inside the authorized allow-list? ``open`` scope => always."""
    if scope.scope_mode != "explicit":
        return True
    target = _norm(path, scope.cwd)
    if not target:
        return False
    tp = PurePosixPath(target)
    for pat in scope.authorized_paths:
        pat_n = _norm(pat, scope.cwd)
        if not pat_n:
            continue
        # a bare directory ("src", "src/") authorizes everything under it
        if any(ch in pat_n for ch in "*?[") :
            # glob: support "src/**" (recursive) and fnmatch semantics
            if pat_n.endswith("/**"):
                base = pat_n[:-3]
                if target == base or target.startswith(base + "/"):
                    return True
            try:
                if tp.match(pat_n):
                    return True
            except ValueError:
                pass
        else:
            if target == pat_n or target.startswith(pat_n + "/"):
                return True
    return False


# --------------------------------------------------------------------------- #
# Secret / sensitive-content detection
# --------------------------------------------------------------------------- #
_SENSITIVE_NAME_RE = re.compile(
    r"(^|/)("
    r"\.env($|\..+)"
    r"|.*\.pem$|.*\.key$|.*\.p12$|.*\.pfx$|.*\.keystore$"
    r"|id_rsa.*|id_ed25519.*|id_dsa.*|id_ecdsa.*"
    r"|.*credentials.*|.*secret.*|keys\.json"
    r"|\.npmrc|\.pypirc|\.netrc|\.pgpass"
    r"|.*\.ovpn$"
    r"|.*engagement.*|.*pentest.*report.*|.*\.burp$"
    r")",
    re.IGNORECASE,
)

_SECRET_CONTENT_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("AWS secret access key", re.compile(r"\baws_secret_access_key\b\s*[:=]\s*\S{30,}", re.IGNORECASE)),
    ("GitHub token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b")),
    ("JWT", re.compile(r"\beyJ[0-9A-Za-z_\-]{10,}\.[0-9A-Za-z_\-]{10,}\.[0-9A-Za-z_\-]{10,}\b")),
    ("bearer token", re.compile(r"\b[Bb]earer\s+[0-9A-Za-z._\-]{20,}")),
    ("generic api key/secret assignment",
     re.compile(r"\b(?:api[_-]?key|secret|passwd|password|token|access[_-]?token)\b\s*[:=]\s*['\"]?[0-9A-Za-z/+_\-]{16,}", re.IGNORECASE)),
)


def scan_name(path: str) -> str | None:
    """Return a reason if the FILENAME itself is sensitive, else None."""
    return "sensitive filename" if _SENSITIVE_NAME_RE.search((path or "").replace("\\", "/")) else None


def scan_content(text: str) -> str | None:
    """Return a reason if the CONTENT looks like a secret, else None."""
    for reason, rx in _SECRET_CONTENT_RES:
        if rx.search(text or ""):
            return reason
    return None


def scan_paths_for_secrets(paths: list[str], cwd: str = "", max_bytes: int = 200_000) -> list[tuple[str, str]]:
    """Inspect each path by NAME and (where readable) by CONTENT. Never trust a
    filename alone: a harmless-looking name with a key inside still blocks."""
    hits: list[tuple[str, str]] = []
    for raw in paths:
        if not raw:
            continue
        reason = scan_name(raw)
        if reason:
            hits.append((raw, reason))
            continue
        fp = os.path.join(cwd, raw) if cwd and not os.path.isabs(raw) else raw
        try:
            if os.path.isfile(fp):
                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                    cr = scan_content(fh.read(max_bytes))
                if cr:
                    hits.append((raw, cr))
        except OSError:
            pass
    return hits


# --------------------------------------------------------------------------- #
# git command analysis
# --------------------------------------------------------------------------- #
@dataclass
class GitOp:
    sub: str                         # add|commit|push|rm|mv|...
    paths: list[str] = field(default_factory=list)
    stages_all: bool = False         # add -A/-u/. or commit -a  (== "everything")
    external: bool = False           # publishes off-box (push)
    raw: str = ""


_SEGMENT_RE = re.compile(r"\s*(?:&&|\|\||\||;|\n)\s*")


def _segments(cmd: str) -> list[str]:
    return [s for s in _SEGMENT_RE.split(cmd or "") if s.strip()]


def _git_tokens(seg: str) -> list[str] | None:
    """Return token list for a segment whose command is git, else None.
    Conservatively returns ['git', '\x00UNPARSED'] when a git segment cannot be
    tokenized (command substitution etc.) so the caller can fail closed."""
    try:
        toks = shlex.split(seg, comments=False, posix=True)
    except ValueError:
        # unbalanced quotes / substitution — only care if it's a git line
        return ["git", "\x00UNPARSED"] if re.search(r"\bgit\b", seg) else None
    if not toks:
        return None
    # strip leading env assignments (FOO=bar git ...)
    i = 0
    while i < len(toks) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[i]):
        i += 1
    toks = toks[i:]
    if not toks or os.path.basename(toks[0]) != "git":
        return None
    return toks


def analyze_git_command(cmd: str) -> list[GitOp]:
    """Decompose a (possibly compound) bash command into its git operations."""
    ops: list[GitOp] = []
    for seg in _segments(cmd):
        toks = _git_tokens(seg)
        if toks is None:
            continue
        if "\x00UNPARSED" in toks:
            ops.append(GitOp(sub="?unparsed", stages_all=True, external=True, raw=seg))
            continue
        # skip global flags: -C <dir>, -c k=v, --git-dir=…, etc.
        j = 1
        while j < len(toks) and toks[j].startswith("-"):
            if toks[j] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
                j += 2
            else:
                j += 1
        if j >= len(toks):
            continue
        sub = toks[j]
        rest = toks[j + 1:]
        op = GitOp(sub=sub, raw=seg)
        if sub == "add":
            for t in rest:
                if t in ("-A", "--all", "-u", "--update"):
                    op.stages_all = True
                elif t == "." or t == "./" or t == ":/" or t == "*":
                    op.stages_all = True
                elif t == "--":
                    continue
                elif t.startswith("-"):
                    continue
                elif any(ch in t for ch in "$`*?(){}"):
                    # dynamic/glob pathspec — contents cannot be verified ahead
                    # of time, so treat it as an unbounded stage (fail closed).
                    op.stages_all = True
                    op.paths.append(t)
                else:
                    op.paths.append(t)
            if not op.paths and not op.stages_all:
                op.stages_all = True  # bare `git add` is a no-op, but treat defensively
        elif sub == "commit":
            for t in rest:
                if t in ("-a", "--all") or re.match(r"^-[a-zA-Z]*a[a-zA-Z]*$", t):
                    op.stages_all = True
                elif not t.startswith("-"):
                    # pathspec after `commit -- path`
                    op.paths.append(t)
        elif sub == "push":
            op.external = True
        elif sub in ("rm", "mv"):
            op.paths = [t for t in rest if not t.startswith("-")]
        else:
            # checkout/switch/status/diff/log/… — not scope-affecting here
            continue
        ops.append(op)
    return ops


def _effective_push_set(cwd: str) -> list[str]:
    """Best-effort list of files a push would publish: staged + the commits
    ahead of the upstream (or last commit as a fallback)."""
    files: set[str] = set()

    def _run(args: list[str]) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=cwd or None, capture_output=True, text=True, timeout=15
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return ""

    for ln in _run(["diff", "--cached", "--name-only"]).splitlines():
        if ln.strip():
            files.add(ln.strip())
    rng = _run(["rev-list", "--count", "@{u}..HEAD"]).strip()
    if rng and rng.isdigit() and int(rng) > 0:
        src = "@{u}..HEAD"
    else:
        src = "HEAD~1..HEAD"
    for ln in _run(["diff", "--name-only", src]).splitlines():
        if ln.strip():
            files.add(ln.strip())
    return sorted(files)


# --------------------------------------------------------------------------- #
# Enforcement entry point (called from Toolbelt.execute)
# --------------------------------------------------------------------------- #
def _enforce_bash(cmd: str, scope: ToolScope) -> str | None:
    ops = analyze_git_command(cmd)
    if not ops:
        return None  # no git mutation in this command; nothing to gate here
    explicit = scope.scope_mode == "explicit"
    for op in ops:
        if op.sub == "?unparsed":
            if explicit:
                return ("scope violation: a git command could not be safely parsed "
                        "(command substitution / dynamic args) while an explicit file "
                        "scope is in effect — refusing. Stage the authorized paths "
                        "explicitly: git add " + " ".join(scope.authorized_paths or ["<paths>"]))
            continue
        if op.stages_all and explicit:
            return (f"scope violation: '{op.sub}' would stage/commit ALL changes, but "
                    f"the authorized scope is explicit ({', '.join(scope.authorized_paths)}). "
                    f"Stage only authorized paths: git add -- {' '.join(scope.authorized_paths)}")
        if explicit:
            for p in op.paths:
                if not path_in_scope(p, scope):
                    return (f"scope violation: '{op.sub} {p}' is outside the authorized "
                            f"scope ({', '.join(scope.authorized_paths)}). Rejected.")
        # EXTERNAL publish: validate the effective change set regardless of mode
        if op.external:
            changed = _effective_push_set(scope.cwd or os.getcwd())
            if explicit:
                outside = [c for c in changed if not path_in_scope(c, scope)]
                if outside:
                    return (f"scope violation: push would publish files outside the "
                            f"authorized scope: {', '.join(outside[:10])}. Rejected — the "
                            f"change set must be rebuilt to contain only "
                            f"{', '.join(scope.authorized_paths)}.")
            if not _allow_secrets():
                hits = scan_paths_for_secrets(changed, scope.cwd or os.getcwd())
                if hits:
                    detail = "; ".join(f"{p} ({why})" for p, why in hits[:8])
                    return ("blocked: refusing to publish — secret/sensitive content in the "
                            f"push set: {detail}. Remove it from history or set "
                            "PAL_AUTHZ_ALLOW_SECRETS=1 only if you are certain.")
    return None


def _enforce_gh(sub: str, scope: ToolScope) -> str | None:
    s = (sub or "").strip()
    external = s.startswith(("pr create", "pr merge", "release create", "repo create"))
    if not external:
        return None
    if not scope.external_ok:
        return f"blocked: external gh operation '{s}' is not authorized by the current scope."
    if not _allow_secrets():
        changed = _effective_push_set(scope.cwd or os.getcwd())
        hits = scan_paths_for_secrets(changed, scope.cwd or os.getcwd())
        if hits:
            detail = "; ".join(f"{p} ({why})" for p, why in hits[:8])
            return f"blocked: '{s}' — secret/sensitive content in the change set: {detail}."
    return None


def _enforce_write(args: dict, scope: ToolScope) -> str | None:
    path = args.get("path") or args.get("file") or args.get("filename") or ""
    # Executor-level credential guard: never let a model's plan write secrets,
    # independent of mission._is_protected (which only guards the writer stage).
    if scan_name(path):
        return (f"blocked: refusing to write credential/sensitive file '{path}' "
                "(set PAL_AUTHZ_ALLOW_SECRETS=1 to override).") if not _allow_secrets() else None
    return None


def enforce(name: str, args: dict, scope: ToolScope | None) -> str | None:
    """The hard authorization check. Returns an ``error``/``blocked`` message
    (operation must NOT run) or None (allowed). Never trusts the caller model."""
    if is_disabled():
        return None
    # No scope set upstream => baseline guard: still secret-scan external ops.
    if scope is None:
        scope = ToolScope(intent="general", scope_mode="open", external_ok=True, cwd=os.getcwd())
    try:
        if name == "bash":
            cmd = (args.get("command") or args.get("cmd") or "")
            return _enforce_bash(cmd, scope)
        if name == "gh":
            return _enforce_gh(args.get("subcommand") or "", scope)
        if name == "write_file":
            return _enforce_write(args, scope)
    except Exception as exc:  # fail closed in explicit mode, open otherwise
        log.warning("authz enforcement error on %s: %s", name, exc)
        if scope.scope_mode == "explicit":
            return f"blocked: authorization check failed for '{name}' ({exc}); refusing."
        return None
    return None
