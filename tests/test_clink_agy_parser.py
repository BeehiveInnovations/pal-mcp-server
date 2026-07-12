"""Tests for the agy (Antigravity) CLI plain-text parser."""

import pytest

from clink.parsers.agy import AgyTextParser
from clink.parsers.base import ParserError


def test_agy_parser_success():
    parser = AgyTextParser()

    parsed = parser.parse("  Hello from agy  ", stderr="")

    assert parsed.content == "Hello from agy"
    assert parsed.metadata == {}


def test_agy_parser_includes_stderr_in_metadata():
    parser = AgyTextParser()

    parsed = parser.parse("ok", stderr="  some log line  ")

    assert parsed.metadata["stderr"] == "some log line"


def test_agy_parser_empty_stdout_raises():
    parser = AgyTextParser()

    with pytest.raises(ParserError, match="empty stdout"):
        parser.parse(stdout="", stderr="")


def test_agy_parser_whitespace_only_stdout_raises():
    parser = AgyTextParser()

    with pytest.raises(ParserError, match="empty stdout"):
        parser.parse(stdout="   \n  ", stderr="")


def test_agy_parser_preserves_multiline_content():
    parser = AgyTextParser()
    stdout = "line one\nline two\n"

    parsed = parser.parse(stdout, stderr="")

    assert parsed.content == "line one\nline two"
