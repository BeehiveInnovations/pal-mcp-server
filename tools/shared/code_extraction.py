"""
Fenced code block extraction from AI responses.

Intercepts standard markdown fenced code blocks (```lang ... ```) in tool responses,
writes them to local files, and replaces them with compact references. This prevents
large code blocks from consuming the MCP client's context window.

Runs deterministically via regex — no LLM fallback, no latency, no cost.

Configuration via environment variables:
    PAL_FENCED_CODE_EXTRACTION  — Enable/disable (default: true)
    PAL_FENCED_CODE_MIN_LINES   — Minimum lines to trigger extraction (default: 30)
    PAL_FENCED_CODE_MIN_CHARS   — Minimum chars to trigger extraction (default: 800)
    PAL_FENCED_CODE_OUTPUT_DIR  — Subdirectory name within working_directory (default: pal)
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Language identifier → file extension mapping
LANG_EXTENSION_MAP = {
    "python": "py", "py": "py",
    "typescript": "ts", "ts": "ts",
    "tsx": "tsx", "jsx": "jsx",
    "javascript": "js", "js": "js",
    "json": "json", "jsonc": "json",
    "html": "html", "css": "css", "scss": "scss",
    "sql": "sql", "bash": "sh", "sh": "sh", "shell": "sh",
    "yaml": "yaml", "yml": "yaml",
    "markdown": "md", "md": "md",
    "go": "go", "rust": "rs", "java": "java",
    "ruby": "rb", "php": "php", "c": "c", "cpp": "cpp",
    "csharp": "cs", "swift": "swift", "kotlin": "kt",
    "toml": "toml", "xml": "xml", "graphql": "graphql",
    "dockerfile": "dockerfile", "makefile": "makefile",
}


def is_fenced_code_extraction_enabled() -> bool:
    """Check whether fenced code extraction is enabled via env var."""
    return os.environ.get("PAL_FENCED_CODE_EXTRACTION", "true").lower() in ("true", "1", "yes")


def extract_fenced_code_blocks(text: str) -> list[dict]:
    """
    Extract markdown fenced code blocks that exceed size thresholds.

    Returns list of dicts with keys: language, content, start, end, line_count, char_count.
    Only includes blocks exceeding the configured minimum lines OR minimum chars.
    """
    min_lines = int(os.environ.get("PAL_FENCED_CODE_MIN_LINES", "30"))
    min_chars = int(os.environ.get("PAL_FENCED_CODE_MIN_CHARS", "800"))

    blocks = []
    for match in re.finditer(r"```(\w*)\n(.*?)```", text, flags=re.DOTALL):
        content = match.group(2)
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        char_count = len(content)

        if line_count >= min_lines or char_count >= min_chars:
            blocks.append({
                "language": match.group(1) or "",
                "content": content,
                "start": match.start(),
                "end": match.end(),
                "line_count": line_count,
                "char_count": char_count,
            })
    return blocks


def persist_fenced_code_blocks(blocks: list[dict], working_directory: str) -> list[dict]:
    """
    Write extracted code blocks to numbered files in {working_directory}/{output_subdir}/.

    Returns list of dicts with keys: file_path, rel_path, filename, line_count, language, start, end.
    """
    output_subdir = os.environ.get("PAL_FENCED_CODE_OUTPUT_DIR", "pal")
    expanded = os.path.expanduser(working_directory)
    output_dir = Path(expanded).resolve() / output_subdir
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for idx, block in enumerate(blocks, start=1):
        lang = block["language"].lower()
        ext = LANG_EXTENSION_MAP.get(lang, "txt")
        label = lang if lang else "code"
        filename = f"{idx:03d}-{label}.{ext}"
        file_path = output_dir / filename

        content = block["content"]
        if not content.endswith("\n"):
            content += "\n"
        file_path.write_text(content, encoding="utf-8")
        logger.info("Fenced code block written to %s", file_path)

        rel_path = f"{output_subdir}/{filename}"
        saved.append({
            "file_path": str(file_path),
            "rel_path": rel_path,
            "filename": filename,
            "line_count": block["line_count"],
            "language": block["language"],
            "start": block["start"],
            "end": block["end"],
        })
    return saved


def build_fenced_code_reference(saved_files: list[dict]) -> str:
    """
    Build a compact summary of extracted code files with instructions for the MCP client.

    Tells the receiving agent NOT to auto-read the files — instead, prompt the user
    to ask which (if any) they want read.
    """
    total_lines = sum(f["line_count"] for f in saved_files)
    file_count = len(saved_files)
    output_dir = saved_files[0]["rel_path"].rsplit("/", 1)[0] if saved_files else "pal"

    lines = [
        f"Code extracted to ./{output_dir}/ ({file_count} file{'s' if file_count != 1 else ''}, ~{total_lines} lines total):"
    ]
    for f in saved_files:
        lines.append(f"  - {f['filename']} ({f['line_count']} lines)")

    lines.append("")
    lines.append(
        "IMPORTANT: Do NOT read these files automatically. "
        "Ask the user which files (if any) they would like you to read or apply. "
        "The files are saved to disk and available on demand."
    )
    return "\n".join(lines)


def apply_fenced_code_extraction(body: str, working_directory: str) -> str:
    """
    Top-level convenience: extract fenced code blocks, persist to disk, replace inline.

    Returns the modified body text with code blocks replaced by compact references.
    If extraction is disabled or no blocks exceed thresholds, returns body unchanged.
    """
    if not is_fenced_code_extraction_enabled():
        return body

    fenced_blocks = extract_fenced_code_blocks(body)
    if not fenced_blocks:
        return body

    try:
        saved = persist_fenced_code_blocks(fenced_blocks, working_directory)
        # Replace each block in body with a one-line reference (reverse to preserve positions)
        for block_info in reversed(saved):
            placeholder = f"[-> See ./{block_info['rel_path']} ({block_info['line_count']} lines)]"
            body = body[:block_info['start']] + placeholder + body[block_info['end']:]
        # Append summary
        reference = build_fenced_code_reference(saved)
        body = _join_sections(body, reference)
    except Exception as exc:
        logger.warning("Fenced code extraction failed, keeping inline: %s", exc)

    return body


def _join_sections(*sections: str) -> str:
    """Join non-empty text sections with double newlines."""
    chunks = [s.strip() for s in sections if s and s.strip()]
    return "\n\n".join(chunks)
