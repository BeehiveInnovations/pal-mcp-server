"""bash adapter — run a shell command, capture stdout+stderr."""

from __future__ import annotations

import os
import subprocess

from providers.tooling.toolbelt import ToolSpec, get_toolbelt

_DEFAULT_ALLOW = "ls,cat,head,tail,grep,rg,find,jq,curl,gh,git,wc,awk,sed,file,stat,which"
# git subcommands that do NOT mutate the working tree / repo / remote. In
# read-only mode `git` is allow-listed for inspection ONLY; add/commit/push/etc.
# are blocked here so read-only mode cannot stage or publish anything.
_GIT_RO_SUBS = frozenset({
    "status", "log", "diff", "show", "branch", "remote", "rev-parse", "rev-list",
    "ls-files", "ls-tree", "cat-file", "describe", "shortlog", "blame", "config",
    "for-each-ref", "symbolic-ref", "name-rev", "whatchanged", "reflog",
})


def _allowlist() -> tuple[str, ...]:
    # read at call-time so the allowlist / unrestricted flag can change per run
    raw = os.getenv("PAL_BASH_ALLOWLIST", _DEFAULT_ALLOW)
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def _unrestricted() -> bool:
    return os.getenv("PAL_BASH_UNRESTRICTED", "0") in ("1", "true", "yes")


def _git_is_readonly(cmd: str) -> bool:
    """True only if EVERY git invocation in a (possibly compound) command uses a
    read-only subcommand. Unparseable git => not read-only (fail closed)."""
    import re
    import shlex

    for seg in re.split(r"\s*(?:&&|\|\||\||;|\n)\s*", cmd):
        if not re.search(r"\bgit\b", seg):
            continue
        try:
            toks = shlex.split(seg, posix=True)
        except ValueError:
            return False
        i = 0
        while i < len(toks) and "=" in toks[i].split("/")[-1] and os.path.basename(toks[i]).split("=")[0].isidentifier():
            i += 1
        toks = toks[i:]
        if not toks or os.path.basename(toks[0]) != "git":
            continue
        j = 1
        while j < len(toks) and toks[j].startswith("-"):
            j += 2 if toks[j] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
        if j >= len(toks) or toks[j] not in _GIT_RO_SUBS:
            return False
    return True


def _run(args: dict) -> str:
    cmd = (args.get("command") or "").strip()
    if not cmd:
        return "error: 'command' is required"
    if not _unrestricted():
        first = cmd.split(None, 1)[0]
        allow = _allowlist()
        if allow and first not in allow:
            return (
                f"error: '{first}' is not in the read-only allowlist. "
                "This is read-only /tools mode; use /tools:full to run arbitrary commands."
            )
        # git is allow-listed for INSPECTION only in read-only mode
        if "git" in cmd.split() and not _git_is_readonly(cmd):
            return (
                "error: in read-only mode 'git' may only run inspection subcommands "
                "(status/log/diff/show/…); staging, committing and pushing require full mode."
            )
    timeout = int(args.get("timeout_s", 30))
    try:
        proc = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"error: timed out after {timeout}s"
    out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
    if len(out) > 20_000:
        out = out[:20_000] + f"\n... [truncated, {len(out)} bytes total]"
    return out + f"\n[exit={proc.returncode}]"


get_toolbelt().register(
    ToolSpec(
        name="bash",
        description=(
            "Run a bash shell command; returns stdout+stderr+exit code. In read-only mode "
            "only allow-listed binaries run; in full mode any command runs (nmap, nuclei, "
            "ffuf, etc.). Launch GUI/long-running apps detached: setsid <cmd> >/dev/null 2>&1 &"
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "bash command; only allow-listed leading binaries"},
                "timeout_s": {"type": "integer", "default": 30},
            },
            "required": ["command"],
        },
        handler=_run,
        sandbox="readonly",  # allow-list keeps this de-facto readonly
    )
)
