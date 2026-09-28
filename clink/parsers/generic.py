"""Generic text parser for CLIs that stream plain text to stdout.

Used for aider/cline/cursor-agent under P4a — they don't emit a documented
JSON envelope, so we take stdout verbatim as the content and record stderr
as metadata for troubleshooting.
"""
from __future__ import annotations

from .base import BaseParser, ParsedCLIResponse


class GenericTextParser(BaseParser):
    name = "generic_text"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        content = (stdout or "").strip()
        meta: dict = {}
        if stderr and stderr.strip():
            meta["stderr"] = stderr.strip()[:2000]
        return ParsedCLIResponse(content=content, metadata=meta)
