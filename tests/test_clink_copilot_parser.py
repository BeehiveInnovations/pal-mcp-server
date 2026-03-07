"""Tests for the Copilot CLI JSONL parser."""

import pytest

from clink.parsers.base import ParserError
from clink.parsers.copilot import CopilotJSONLParser


def test_copilot_parser_success():
    parser = CopilotJSONLParser()
    stdout = (
        '{"type":"assistant.message","data":{"content":"Hello from Copilot"}}\n'
        '{"type":"result","sessionId":"sess-123","usage":{"input_tokens":10,"output_tokens":5}}\n'
    )
    parsed = parser.parse(stdout=stdout, stderr="")
    assert parsed.content == "Hello from Copilot"
    assert parsed.metadata["session_id"] == "sess-123"
    assert parsed.metadata["usage"]["output_tokens"] == 5


def test_copilot_parser_multiple_assistant_messages():
    parser = CopilotJSONLParser()
    stdout = (
        '{"type":"assistant.message","data":{"content":"First part"}}\n'
        '{"type":"assistant.message","data":{"content":"Second part"}}\n'
        '{"type":"result","sessionId":"sess-456"}\n'
    )
    parsed = parser.parse(stdout=stdout, stderr="")
    assert "First part" in parsed.content
    assert "Second part" in parsed.content


def test_copilot_parser_requires_assistant_message():
    parser = CopilotJSONLParser()
    stdout = '{"type":"result","sessionId":"sess-789"}\n'
    with pytest.raises(ParserError):
        parser.parse(stdout=stdout, stderr="")


def test_copilot_parser_skips_non_json_lines():
    parser = CopilotJSONLParser()
    stdout = "some debug output\n" '{"type":"assistant.message","data":{"content":"Answer"}}\n' '{"type":"result"}\n'
    parsed = parser.parse(stdout=stdout, stderr="")
    assert parsed.content == "Answer"


def test_copilot_parser_captures_stderr():
    parser = CopilotJSONLParser()
    stdout = '{"type":"assistant.message","data":{"content":"OK"}}\n'
    parsed = parser.parse(stdout=stdout, stderr="warning: something")
    assert parsed.metadata["stderr"] == "warning: something"


def test_copilot_parser_empty_content_skipped():
    parser = CopilotJSONLParser()
    stdout = (
        '{"type":"assistant.message","data":{"content":"  "}}\n'
        '{"type":"assistant.message","data":{"content":"Real answer"}}\n'
    )
    parsed = parser.parse(stdout=stdout, stderr="")
    assert parsed.content == "Real answer"
