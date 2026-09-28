"""nuclei adapter — run ProjectDiscovery nuclei against a target.

Active scanning: requires PAL_TOOL_SANDBOX=write (or PAL_ALLOW_ACTIVE_SCAN=1).
Blocks obviously dangerous flags. Truncates output. Always passes -silent -j
(JSONL) so downstream models parse cleanly.
"""

from __future__ import annotations

import os
import shlex
import subprocess

from providers.tooling.toolbelt import ToolSpec, get_toolbelt

_BLOCKED_FLAGS = (
    "-interactsh-server",
    "-iserver",
    "-headless",  # browser engine, sandbox escape risk
    "-system-resolvers",
    "-config",
    "-code",  # enables -code templates (arbitrary code exec templates)
)

_MAX_OUT = 40_000


def _allowed() -> bool:
    if os.getenv("PAL_ALLOW_ACTIVE_SCAN", "0") in ("1", "true", "yes"):
        return True
    return os.getenv("PAL_TOOL_SANDBOX", "readonly") == "write"


def _run(args: dict) -> str:
    target = (args.get("target") or "").strip()
    if not target:
        return "error: 'target' is required (URL or host)"
    if not _allowed():
        return "error: nuclei is an active scanner; requires " "PAL_TOOL_SANDBOX=write or PAL_ALLOW_ACTIVE_SCAN=1"

    templates = (args.get("templates") or "").strip()  # -t value(s), comma-sep
    tags = (args.get("tags") or "").strip()  # -tags
    severity = (args.get("severity") or "").strip()  # info,low,medium,high,critical
    extra = (args.get("extra") or "").strip()  # free-form extra flags
    timeout = int(args.get("timeout") or 300)
    timeout = max(30, min(timeout, 900))

    extra_parts = shlex.split(extra) if extra else []
    for bad in _BLOCKED_FLAGS:
        if any(p == bad or p.startswith(bad + "=") for p in extra_parts):
            return f"error: flag '{bad}' is blocked"

    cmd = ["nuclei", "-silent", "-j", "-nc", "-duc", "-u", target, "-timeout", "10", "-rate-limit", "50", "-c", "25"]
    if templates:
        cmd += ["-t", templates]
    if tags:
        cmd += ["-tags", tags]
    if severity:
        cmd += ["-severity", severity]
    cmd += extra_parts

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return "error: nuclei binary not found in PATH"
    except subprocess.TimeoutExpired:
        return f"error: nuclei timed out after {timeout}s"

    out = proc.stdout or ""
    if proc.stderr:
        out += "\n[stderr]\n" + proc.stderr
    if len(out) > _MAX_OUT:
        out = out[:_MAX_OUT] + f"\n... [truncated at {_MAX_OUT} bytes]"
    return out + f"\n[exit={proc.returncode}] cmd={' '.join(shlex.quote(c) for c in cmd)}"


get_toolbelt().register(
    ToolSpec(
        name="nuclei",
        description=(
            "ProjectDiscovery nuclei scanner. Runs against a single target. "
            "Output is JSONL findings. Active-scan gated: needs "
            "PAL_TOOL_SANDBOX=write or PAL_ALLOW_ACTIVE_SCAN=1."
        ),
        parameters={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "URL or host to scan, e.g. https://example.com"},
                "templates": {
                    "type": "string",
                    "description": "Optional -t value(s), comma-separated template paths or IDs",
                },
                "tags": {"type": "string", "description": "Optional -tags filter, e.g. 'cve,exposure'"},
                "severity": {"type": "string", "description": "Optional -severity filter, e.g. 'high,critical'"},
                "extra": {
                    "type": "string",
                    "description": "Extra nuclei flags (space-separated). Blocked: -interactsh-server, -headless, -code, -config, -system-resolvers",
                },
                "timeout": {"type": "integer", "description": "Wall-clock timeout seconds (30–900, default 300)"},
            },
            "required": ["target"],
        },
        handler=_run,
        sandbox="write",
    )
)
