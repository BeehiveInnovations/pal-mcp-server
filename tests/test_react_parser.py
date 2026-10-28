"""Regression tests for the multi-format ReAct tool-call parser."""
from __future__ import annotations

import pytest

from providers.tooling import react


@pytest.mark.parametrize("text,expected", [
    ('<tool_call>{"name":"bash","args":{"command":"ls"}}</tool_call>', [("bash", {"command": "ls"})]),
    ('<tool_call>{"name":"bash","arguments":{"command":"pwd"}}</tool_call>', [("bash", {"command": "pwd"})]),
    ('<tool_call>{"name":"bash","arguments":"{\\"command\\": \\"id\\"}"}</tool_call>', [("bash", {"command": "id"})]),
    ('<tool_call>\n<function=bash>\n{"command": "wc -l f"}\n</function>\n</tool_call>', [("bash", {"command": "wc -l f"})]),
    ('<function=read_file>{"path":"/etc/hostname"}</function>', [("read_file", {"path": "/etc/hostname"})]),
    ('<tool_call><function=bash><parameter=command>wc -l data.env</parameter></function></tool_call>',
     [("bash", {"command": "wc -l data.env"})]),
])
def test_formats(text, expected):
    assert react.extract_calls(text) == expected


def test_no_call_returns_empty():
    assert react.extract_calls("just a plain answer, no tools") == []


def test_multiple_calls():
    t = '<function=bash>{"command":"ls"}</function> then <function=read_file>{"path":"x"}</function>'
    got = react.extract_calls(t)
    assert ("bash", {"command": "ls"}) in got and ("read_file", {"path": "x"}) in got


@pytest.mark.parametrize("text,expected", [
    # model omitted "name": infer from arg keys
    ('<tool_call>{"command":"ls -la"}</tool_call>', [("bash", {"command": "ls -la"})]),
    ('<tool_call>{"path":"f","content":"hi"}</tool_call>', [("write_file", {"path": "f", "content": "hi"})]),
    ('<tool_call>{"path":"/etc/hostname"}</tool_call>', [("read_file", {"path": "/etc/hostname"})]),
    ('<tool_call>{"url":"http://x"}</tool_call>', [("web_fetch", {"url": "http://x"})]),
])
def test_name_inference(text, expected):
    assert react.extract_calls(text) == expected


def test_unknown_nameless_call_dropped():
    # no name and no recognizable keys -> cannot infer -> skip
    assert react.extract_calls('<tool_call>{"foo":"bar"}</tool_call>') == []
