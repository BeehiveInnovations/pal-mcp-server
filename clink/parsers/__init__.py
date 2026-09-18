"""Parser registry for clink."""

from __future__ import annotations

from typing import Any

from .agy import AgyJSONParser
from .base import BaseParser, ParsedCLIResponse, ParserError
from .claude import ClaudeJSONParser
from .codex import CodexJSONLParser
from .gemini import GeminiJSONParser
from .generic import ConfigurableParser, GenericJSONLParser, GenericJSONParser, GenericTextParser

_PARSER_CLASSES: dict[str, type[BaseParser]] = {
    CodexJSONLParser.name: CodexJSONLParser,
    GeminiJSONParser.name: GeminiJSONParser,
    ClaudeJSONParser.name: ClaudeJSONParser,
    AgyJSONParser.name: AgyJSONParser,
    GenericJSONParser.name: GenericJSONParser,
    GenericJSONLParser.name: GenericJSONLParser,
    GenericTextParser.name: GenericTextParser,
}


def available_parsers() -> list[str]:
    """Return the sorted names of every registered parser."""

    return sorted(_PARSER_CLASSES)


def get_parser(name: str, options: dict[str, Any] | None = None) -> BaseParser:
    """Instantiate a parser by name.

    Parsers deriving from ConfigurableParser accept ``options`` sourced from a
    client's ``parser_options``; the CLI-specific parsers ignore them.
    """

    normalized = (name or "").lower()
    if normalized not in _PARSER_CLASSES:
        raise ParserError(f"No parser registered for '{name}'. Available parsers: {', '.join(available_parsers())}")
    parser_cls = _PARSER_CLASSES[normalized]
    if issubclass(parser_cls, ConfigurableParser):
        return parser_cls(options or {})
    return parser_cls()


__all__ = [
    "BaseParser",
    "ConfigurableParser",
    "ParsedCLIResponse",
    "ParserError",
    "available_parsers",
    "get_parser",
]
