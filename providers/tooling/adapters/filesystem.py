"""filesystem adapter — read files (allow-listed roots)."""

from __future__ import annotations

import os
from pathlib import Path

from providers.tooling.toolbelt import ToolSpec, get_toolbelt


def _roots() -> list[Path]:
    raw = os.getenv("PAL_FS_ROOTS", str(Path.cwd()))
    return [Path(p).resolve() for p in raw.split(":") if p.strip()]


def _read(args: dict) -> str:
    p = Path(args.get("path", ""))
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    if not any(str(p).startswith(str(r) + os.sep) or str(p) == str(r) for r in _roots()):
        return f"error: path {p} outside PAL_FS_ROOTS"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError) as exc:
        return f"error: {exc}"
    max_b = int(args.get("max_bytes", 20_000))
    if len(text) > max_b:
        text = text[:max_b] + f"\n... [truncated at {max_b} bytes]"
    return text


get_toolbelt().register(
    ToolSpec(
        name="read_file",
        description="Read a UTF-8 text file within PAL_FS_ROOTS. Returns first N bytes.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_bytes": {"type": "integer", "default": 20000},
            },
            "required": ["path"],
        },
        handler=_read,
        sandbox="readonly",
    )
)
