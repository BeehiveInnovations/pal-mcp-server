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


def _resolve_in_roots(path_str: str) -> tuple[Path | None, str]:
    p = Path(path_str or "")
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    else:
        p = p.resolve()
    if not any(str(p).startswith(str(r) + os.sep) or str(p) == str(r) for r in _roots()):
        return None, f"error: path {p} outside PAL_FS_ROOTS"
    return p, ""


def _write(args: dict) -> str:
    p, err = _resolve_in_roots(args.get("path", ""))
    if p is None:
        return err
    content = args.get("content", "")
    if not isinstance(content, str):
        content = str(content)
    overwrite = bool(args.get("overwrite", False))
    if p.exists() and not overwrite:
        return f"error: {p} exists; pass overwrite=true to replace it"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"error: {exc}"
    return f"wrote {len(content)} bytes to {p}"


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

get_toolbelt().register(
    ToolSpec(
        name="write_file",
        description=(
            "Create or overwrite a UTF-8 text file within PAL_FS_ROOTS (defaults to the "
            "current directory). Use this to CREATE files. Won't overwrite unless overwrite=true."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "file path, relative to the working dir"},
                "content": {"type": "string", "description": "file contents (may be empty)"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
        handler=_write,
        sandbox="write",
    )
)
