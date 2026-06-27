"""Tests for the grok CLI JSON parser."""

import json

import pytest

from clink.parsers.base import ParserError
from clink.parsers.grok import GrokJSONParser


def _build_grok_stdout(*, text: str = "Hello from grok", extra: dict | None = None) -> str:
    payload = {
        "text": text,
        "stopReason": "EndTurn",
        "sessionId": "sess-123",
        "requestId": "req-456",
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload)


def test_grok_parser_success():
    parser = GrokJSONParser()
    stdout = _build_grok_stdout(text="  Response text  ")

    parsed = parser.parse(stdout, stderr="")

    assert parsed.content == "Response text"
    assert parsed.metadata["session_id"] == "sess-123"
    assert parsed.metadata["stop_reason"] == "EndTurn"
    assert parsed.metadata["request_id"] == "req-456"


def test_grok_parser_tolerates_leading_noise_before_brace():
    parser = GrokJSONParser()
    stdout = "Loading model...\n" + _build_grok_stdout()

    parsed = parser.parse(stdout, stderr="")

    assert parsed.content == "Hello from grok"


def test_grok_parser_includes_stderr_in_metadata():
    parser = GrokJSONParser()
    stdout = _build_grok_stdout()

    parsed = parser.parse(stdout, stderr="  some log line  ")

    assert parsed.metadata["stderr"] == "some log line"


def test_grok_parser_empty_stdout_raises():
    parser = GrokJSONParser()

    with pytest.raises(ParserError, match="empty stdout"):
        parser.parse(stdout="", stderr="")


def test_grok_parser_no_brace_raises():
    parser = GrokJSONParser()

    with pytest.raises(ParserError, match="no JSON object"):
        parser.parse(stdout="not json at all", stderr="")


def test_grok_parser_malformed_json_raises_decode_error():
    parser = GrokJSONParser()

    # brace is present but the JSON is malformed -> exercises the decode-error branch
    with pytest.raises(ParserError, match="Failed to decode"):
        parser.parse(stdout="{not valid json", stderr="")


def test_grok_parser_tolerates_trailing_output_after_object():
    parser = GrokJSONParser()
    stdout = _build_grok_stdout() + "\nDone in 2.1s\n"

    parsed = parser.parse(stdout, stderr="")

    assert parsed.content == "Hello from grok"


def test_grok_parser_skips_leading_noise_containing_brace():
    parser = GrokJSONParser()
    # a leading log line that itself contains "{" must not derail the decode
    stdout = "Connecting to {endpoint}...\n" + _build_grok_stdout()

    parsed = parser.parse(stdout, stderr="")

    assert parsed.content == "Hello from grok"


def test_grok_parser_missing_text_raises():
    parser = GrokJSONParser()
    stdout = json.dumps({"stopReason": "EndTurn", "sessionId": "sess-123"})

    with pytest.raises(ParserError, match="missing a non-empty 'text' field"):
        parser.parse(stdout, stderr="")


def test_grok_parser_empty_text_raises():
    parser = GrokJSONParser()
    stdout = json.dumps({"text": "   ", "stopReason": "EndTurn"})

    with pytest.raises(ParserError, match="missing a non-empty 'text' field"):
        parser.parse(stdout, stderr="")
