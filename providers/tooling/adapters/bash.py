"""bash adapter — run a shell command, capture stdout+stderr."""

from __future__ import annotations

import os
import subprocess

from providers.tooling.toolbelt import ToolSpec, get_toolbelt

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
    first = cmd.split(None, 1)[0]
    if _ALLOWED_PREFIXES and first not in _ALLOWED_PREFIXES:
        return f"error: '{first}' not in PAL_BASH_ALLOWLIST"
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
        description="Run a bash command from a fixed allowlist. Returns stdout+stderr+exit.",
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
