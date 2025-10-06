"""Tests for the Gemini CLI JSON parser."""

import pytest

from clink.parsers.gemini import GeminiJSONParser, ParserError


def _build_rate_limit_stdout() -> str:
    return (
        "{\n"
        '  "response": "",\n'
        '  "stats": {\n'
        '    "models": {\n'
        '      "gemini-2.5-pro": {\n'
        '        "api": {\n'
        '          "totalRequests": 5,\n'
        '          "totalErrors": 5,\n'
        '          "totalLatencyMs": 13319\n'
        "        },\n"
        '        "tokens": {"prompt": 0, "candidates": 0, "total": 0, "cached": 0, "thoughts": 0, "tool": 0}\n'
        "      }\n"
        "    },\n"
        '    "tools": {"totalCalls": 0},\n'
        '    "files": {"totalLinesAdded": 0, "totalLinesRemoved": 0}\n'
        "  }\n"
        "}"
    )


def test_gemini_parser_handles_rate_limit_empty_response():
    parser = GeminiJSONParser()
    stdout = _build_rate_limit_stdout()
    stderr = "Attempt 1 failed with status 429. Retrying with backoff... ApiError: quota exceeded"

    parsed = parser.parse(stdout, stderr)

    assert "429" in parsed.content
    assert parsed.metadata.get("rate_limit_status") == 429
    assert parsed.metadata.get("empty_response") is True
    assert "Attempt 1 failed" in parsed.metadata.get("stderr", "")


def test_gemini_parser_still_errors_when_no_fallback_available():
    parser = GeminiJSONParser()
    stdout = '{"response": "", "stats": {}}'

    with pytest.raises(ParserError):
        parser.parse(stdout, stderr="")
