import pytest

from clink.parsers.base import ParserError
from clink.parsers.codex import CodexJSONLParser
from clink.parsers.grok import GrokJSONParser
from clink.parsers.opencode import OpenCodeJSONLParser


def test_codex_parser_success():
    parser = CodexJSONLParser()
    stdout = """
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Hello"}}
{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}
"""
    parsed = parser.parse(stdout=stdout, stderr="")
    assert parsed.content == "Hello"
    assert parsed.metadata["usage"]["output_tokens"] == 5


def test_codex_parser_requires_agent_message():
    parser = CodexJSONLParser()
    stdout = '{"type":"turn.completed"}'
    with pytest.raises(ParserError):
        parser.parse(stdout=stdout, stderr="")


def test_grok_parser_success():
    parser = GrokJSONParser()
    stdout = """
{
  "text": "pong",
  "stopReason": "EndTurn",
  "sessionId": "sess-1",
  "requestId": "req-1"
}
"""
    parsed = parser.parse(stdout=stdout, stderr="")
    assert parsed.content == "pong"
    assert parsed.metadata["sessionId"] == "sess-1"
    assert parsed.metadata["stopReason"] == "EndTurn"


def test_grok_parser_error_payload():
    parser = GrokJSONParser()
    stdout = '{"type":"error","message":"auth failed"}'
    parsed = parser.parse(stdout=stdout, stderr="")
    assert parsed.content == "auth failed"
    assert parsed.metadata["is_error"] is True


def test_grok_parser_requires_text():
    parser = GrokJSONParser()
    with pytest.raises(ParserError):
        parser.parse(stdout='{"stopReason":"EndTurn"}', stderr="")


def test_opencode_parser_success():
    parser = OpenCodeJSONLParser()
    stdout = """
{"type":"step_start","sessionID":"ses_abc","part":{"type":"step-start"}}
{"type":"text","sessionID":"ses_abc","part":{"type":"text","text":"Hello from OpenCode"}}
{"type":"step_finish","sessionID":"ses_abc","part":{"type":"step-finish","reason":"stop","cost":0.01,"tokens":{"input":11,"output":4}}}
"""
    parsed = parser.parse(stdout=stdout, stderr="")
    assert parsed.content == "Hello from OpenCode"
    assert parsed.metadata["session_id"] == "ses_abc"
    assert parsed.metadata["usage"]["output"] == 4
    assert parsed.metadata["cost"] == 0.01


def test_opencode_parser_requires_text_event():
    parser = OpenCodeJSONLParser()
    stdout = '{"type":"step_start","sessionID":"ses_abc","part":{"type":"step-start"}}'
    with pytest.raises(ParserError):
        parser.parse(stdout=stdout, stderr="")
