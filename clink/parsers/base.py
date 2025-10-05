"""Parser interfaces for clink runner outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedCLIResponse:
    """Result of parsing CLI stdout/stderr."""

    content: str
    metadata: dict[str, Any]


class ParserError(RuntimeError):
    """Raised when CLI output cannot be parsed into a structured response."""


class BaseParser:
    """Base interface for CLI output parsers."""

    name: str = "base"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        raise NotImplementedError("Parsers must implement parse()")
