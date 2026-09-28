"""bash adapter — run a shell command, capture stdout+stderr."""

from __future__ import annotations

import os
import subprocess

from providers.tooling.toolbelt import ToolSpec, get_toolbelt

_UNRESTRICTED = os.getenv("PAL_BASH_UNRESTRICTED", "0") in ("1", "true", "yes", "*")
_ALLOWED_PREFIXES = tuple(
    p.strip()
    for p in os.getenv(
        "PAL_BASH_ALLOWLIST", "ls,cat,head,tail,grep,rg,find,jq,curl,gh,git,wc,awk,sed,file,stat,which"
    ).split(",")
    if p.strip()
)


def _run(args: dict) -> str:
    cmd = (args.get("command") or "").strip()
    if not cmd:
        return "error: 'command' is required"
    if not _UNRESTRICTED:
        first = cmd.split(None, 1)[0]
        if _ALLOWED_PREFIXES and first not in _ALLOWED_PREFIXES:
            return f"error: '{first}' not in PAL_BASH_ALLOWLIST (set PAL_BASH_UNRESTRICTED=1 to bypass)"
    timeout = int(args.get("timeout_s", 300))
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
            "Run a bash command. If PAL_BASH_UNRESTRICTED=1, any command is allowed; "
            "otherwise only PAL_BASH_ALLOWLIST prefixes. Returns stdout+stderr+exit."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "bash command"},
                "timeout_s": {"type": "integer", "default": 300, "description": "wall-clock seconds"},
            },
            "required": ["command"],
        },
        handler=_run,
        sandbox="write" if _UNRESTRICTED else "readonly",
    )
)
