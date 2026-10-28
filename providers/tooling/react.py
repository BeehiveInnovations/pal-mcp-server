"""ReAct-style tool-call extractor for providers without native function-calling.

Different open models emit tool calls in different shapes; we accept all of:
  * <tool_call>{"name":"bash","args":{...}}</tool_call>            (PAL native)
  * <tool_call>{"name":"bash","arguments":{...}}</tool_call>       (OpenAI-style)
  * <tool_call><function=bash>{...}</function></tool_call>         (Hermes/Qwen)
  * <function=bash>{...}</function>                                 (bare Hermes)
and return (tool_name, args) pairs.
"""

from __future__ import annotations

import json
import re

_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL | re.IGNORECASE)
# Hermes/Qwen: <function=NAME> ...body... </function>  (body = JSON or <parameter=..> tags)
_FUNC_RE = re.compile(r"<function\s*=\s*([A-Za-z0-9_]+)\s*>(.*?)</function>", re.DOTALL | re.IGNORECASE)
_PARAM_RE = re.compile(r"<parameter\s*=\s*([A-Za-z0-9_]+)\s*>(.*?)</parameter>", re.DOTALL | re.IGNORECASE)
_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _coerce_args(args) -> dict:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return {}
    return args if isinstance(args, dict) else {}


def _infer_name(args: dict) -> str | None:
    """Some models omit the tool name and emit only args. Infer from keys."""
    if "command" in args:
        return "bash"
    if "path" in args and "content" in args:
        return "write_file"
    if "path" in args:
        return "read_file"
    if "url" in args:
        return "web_fetch"
    return None


def _parse_func_body(body: str) -> dict:
    """A <function> body may be JSON or a set of <parameter=k>v</parameter> tags."""
    body = body.strip()
    jm = _JSON_OBJ_RE.search(body)
    if jm:
        try:
            return _coerce_args(json.loads(jm.group(0)))
        except json.JSONDecodeError:
            pass
    params = {k: v.strip() for k, v in _PARAM_RE.findall(body)}
    return params


def extract_calls(text: str) -> list[tuple[str, dict]]:
    text = text or ""
    calls: list[tuple[str, dict]] = []

    # 1) JSON-object form inside <tool_call>{...}</tool_call>
    for m in _CALL_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        name = obj.get("name")
        args = obj.get("args")
        if args is None:
            args = obj.get("arguments")
        if args is None:
            # no wrapper; the object itself is the args, e.g. {"command": "ls"}
            args = {k: v for k, v in obj.items() if k not in ("name", "args", "arguments")}
        args = _coerce_args(args or {})
        if not isinstance(name, str):
            name = _infer_name(args)  # model omitted the name -> infer from keys
        if isinstance(name, str):
            calls.append((name, args))

    # 2) Hermes/Qwen <function=NAME>…</function> (JSON body OR <parameter> tags)
    for m in _FUNC_RE.finditer(text):
        name = m.group(1)
        if isinstance(name, str):
            calls.append((name, _parse_func_body(m.group(2))))

    return calls


def format_result(name: str, result: str) -> str:
    # Tool output is untrusted: flag injection markers (block mode -> neutralised notice)
    try:
        from providers.router import guardrail

        guardrail.scan_inbound(result)
    except Exception as exc:  # GuardrailBlocked or fail-open
        if exc.__class__.__name__ == "GuardrailBlocked":
            result = f"[tool output withheld by guardrail: {exc}]"
    return f'<tool_result name="{name}">{result}</tool_result>'
