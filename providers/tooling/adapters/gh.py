"""gh adapter — GitHub CLI in scoped subcommand mode.

Only allow-listed subcommands are permitted. Write subcommands (`pr create`,
`issue comment`) require PAL_TOOL_SANDBOX=write.
"""

from __future__ import annotations

import os
import subprocess

from providers.tooling.toolbelt import ToolSpec, get_toolbelt

_READ_ONLY = (
    "pr view",
    "pr list",
    "pr diff",
    "pr checks",
    "issue view",
    "issue list",
    "repo view",
    "run list",
    "run view",
    "api",
)
_WRITE_OK = ("pr comment", "issue comment", "pr review")


def _allowed(sub: str) -> bool:
    if os.getenv("PAL_TOOL_SANDBOX", "readonly") == "write":
        return any(sub.startswith(s) for s in _READ_ONLY + _WRITE_OK)
    return any(sub.startswith(s) for s in _READ_ONLY)


def _run(args: dict) -> str:
    sub = (args.get("subcommand") or "").strip()
    if not sub or not _allowed(sub):
        return f"error: gh subcommand '{sub}' not allowed under current sandbox"
    try:
        proc = subprocess.run(
            ["gh"] + sub.split(),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return "error: gh CLI not installed"
    except subprocess.TimeoutExpired:
        return "error: gh timed out after 60s"
    out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
    if len(out) > 20_000:
        out = out[:20_000] + "\n... [truncated]"
    return out + f"\n[exit={proc.returncode}]"


get_toolbelt().register(
    ToolSpec(
        name="gh",
        description="GitHub CLI (allow-listed subcommands). Use pr/issue/repo/api verbs.",
        parameters={
            "type": "object",
            "properties": {
                "subcommand": {"type": "string", "description": "e.g. 'pr view 42 --repo owner/repo'"},
            },
            "required": ["subcommand"],
        },
        handler=_run,
        sandbox="readonly",
    )
)
