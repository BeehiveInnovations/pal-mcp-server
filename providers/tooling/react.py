"""ReAct-style tool-call extractor for providers without native function-calling.

Parses  <tool_call>{"name": "...", "args": {...}}</tool_call>  blocks from a
model response and returns (tool_name, args) pairs.
"""
from __future__ import annotations

import json
import re

_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL | re.IGNORECASE)


def extract_calls(text: str) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []
    for m in _CALL_RE.finditer(text or ""):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        name = obj.get("name")
        args = obj.get("args") or {}
        if isinstance(name, str) and isinstance(args, dict):
            calls.append((name, args))
    return calls


def format_result(name: str, result: str) -> str:
    return f"<tool_result name=\"{name}\">{result}</tool_result>"
