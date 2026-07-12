"""Parser for agy (Antigravity) CLI plain-text output."""

from __future__ import annotations

from .base import BaseParser, ParsedCLIResponse, ParserError


class AgyTextParser(BaseParser):
    """Parse stdout produced by `agy --print`.

    Unlike claude/codex/gemini, agy has no structured output format (no
    `--output-format` flag as of v1.0.16) — `--print` writes the plain-text
    response straight to stdout. Any log/telemetry noise goes to stderr and is
    surfaced via metadata rather than mixed into the parsed content.
    """

    name = "agy_text"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        text = stdout.strip()
        if not text:
            raise ParserError("agy CLI returned empty stdout")

        metadata: dict[str, str] = {}
        if stderr and stderr.strip():
            metadata["stderr"] = stderr.strip()

        return ParsedCLIResponse(content=text, metadata=metadata)
