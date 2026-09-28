"""Unit tests for the agentic toolbelt: toolbelt.py, agent_loop.py, bash adapter.

Covers the enable gate, registry/config semantics, the real bash allowlist,
and all three run_agentic paths (disabled passthrough, native function-calling,
ReAct text-protocol) using minimal fake providers.
"""

from __future__ import annotations

import json

import pytest

from providers.shared.model_response import ModelResponse
from providers.shared.provider_type import ProviderType
from providers.tooling import agent_loop
from providers.tooling.adapters import bash as bash_adapter
from providers.tooling.agent_loop import run_agentic
from providers.tooling.toolbelt import Toolbelt, ToolSpec, is_enabled


def _belt_with_ping() -> Toolbelt:
    """Fresh belt with a single allowlist-independent tool: ping -> pong."""
    b = Toolbelt()
    b.register(
        ToolSpec(
            name="ping",
            description="returns pong",
            parameters={"type": "object", "properties": {}},
            handler=lambda _args: "pong",
        )
    )
    b.enable("ping")
    return b


# --------------------------------------------------------------------------
# is_enabled gate
# --------------------------------------------------------------------------
def test_is_enabled_default_off(monkeypatch):
    monkeypatch.delenv("PAL_TOOLBELT", raising=False)
    assert is_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "yes"])
def test_is_enabled_truthy(monkeypatch, val):
    monkeypatch.setenv("PAL_TOOLBELT", val)
    assert is_enabled() is True


@pytest.mark.parametrize("val", ["0", "false", "no", ""])
def test_is_enabled_falsy(monkeypatch, val):
    monkeypatch.setenv("PAL_TOOLBELT", val)
    assert is_enabled() is False


# --------------------------------------------------------------------------
# registry: register / enable / snapshot
# --------------------------------------------------------------------------
def test_register_enable_snapshot():
    b = _belt_with_ping()
    snap = b.snapshot()
    assert snap["registered"] == ["ping"]
    assert snap["enabled"] == ["ping"]
    assert "log" in snap


def test_enable_unknown_tool_is_noop():
    b = Toolbelt()
    b.enable("does-not-exist")
    assert b.snapshot()["enabled"] == []


# --------------------------------------------------------------------------
# load_config: enable only configured + registered tools
# --------------------------------------------------------------------------
def test_load_config_enables_only_configured(tmp_path):
    b = Toolbelt()
    b.register(ToolSpec("keep", "k", {"type": "object", "properties": {}}, lambda _a: "k"))
    b.register(ToolSpec("skip", "s", {"type": "object", "properties": {}}, lambda _a: "s"))
    cfg = tmp_path / "toolbelt.json"
    cfg.write_text(json.dumps({"tools": [{"name": "keep", "enabled": True}, {"name": "skip", "enabled": False}]}))
    b.load_config(cfg)
    assert b.snapshot()["enabled"] == ["keep"]


def test_load_config_ignores_unregistered(tmp_path):
    b = Toolbelt()
    b.register(ToolSpec("keep", "k", {"type": "object", "properties": {}}, lambda _a: "k"))
    cfg = tmp_path / "toolbelt.json"
    cfg.write_text(json.dumps({"tools": [{"name": "ghost", "enabled": True}]}))
    b.load_config(cfg)
    assert b.snapshot()["enabled"] == []


def test_load_config_missing_file_is_safe(tmp_path):
    b = Toolbelt()
    b.register(ToolSpec("keep", "k", {"type": "object", "properties": {}}, lambda _a: "k"))
    b.load_config(tmp_path / "nope.json")
    assert b.snapshot()["enabled"] == []


# --------------------------------------------------------------------------
# execute: disabled tool guard + audit path
# --------------------------------------------------------------------------
def test_execute_disabled_tool_returns_error():
    b = Toolbelt()
    assert "not enabled" in b.execute("ghost", {})


def test_execute_enabled_tool_runs():
    b = _belt_with_ping()
    assert b.execute("ping", {}, caller_model="test") == "pong"


# --------------------------------------------------------------------------
# real bash adapter allowlist
# --------------------------------------------------------------------------
def test_bash_allowlisted_command_runs():
    out = bash_adapter._run({"command": "which bash"})
    assert "[exit=0]" in out


def test_bash_non_allowlisted_command_blocked():
    assert bash_adapter._run({"command": "echo hi"}) == "error: 'echo' not in PAL_BASH_ALLOWLIST"


def test_bash_empty_command():
    assert bash_adapter._run({"command": ""}) == "error: 'command' is required"


# --------------------------------------------------------------------------
# fake providers for run_agentic
# --------------------------------------------------------------------------
class _FakeFCProvider:
    """Provider exposing native chat_with_tools + generate_content."""

    FRIENDLY_NAME = "fake"

    def __init__(self, gen_returns=None, chat_returns=None):
        self._gen = list(gen_returns or [])
        self._chat = list(chat_returns or [])
        self.gen_calls = 0
        self.chat_calls = 0

    def get_provider_type(self):
        return ProviderType.OPENAI

    def generate_content(self, prompt, model_name, system_prompt=None, temperature=0.3, **kwargs):
        r = self._gen[self.gen_calls]
        self.gen_calls += 1
        return r

    def chat_with_tools(self, messages, tools, model_name, temperature=0.3, tool_choice="auto"):
        r = self._chat[self.chat_calls]
        self.chat_calls += 1
        return r


class _ReactProvider:
    """Provider WITHOUT chat_with_tools -> forces the ReAct text path."""

    FRIENDLY_NAME = "fake"

    def __init__(self, gen_returns):
        self._gen = list(gen_returns)
        self.gen_calls = 0

    def get_provider_type(self):
        return ProviderType.OPENAI

    def generate_content(self, prompt, model_name, system_prompt=None, temperature=0.3, **kwargs):
        r = self._gen[self.gen_calls]
        self.gen_calls += 1
        return r


# --------------------------------------------------------------------------
# run_agentic: disabled -> passthrough
# --------------------------------------------------------------------------
def test_run_agentic_passthrough_when_disabled(monkeypatch):
    monkeypatch.setattr(agent_loop, "is_enabled", lambda: False)
    sentinel = ModelResponse(content="PASSTHROUGH", model_name="m")
    p = _FakeFCProvider(gen_returns=[sentinel])
    resp = run_agentic(p, prompt="hi", model_name="m")
    assert resp.content == "PASSTHROUGH"
    assert p.gen_calls == 1
    assert p.chat_calls == 0


# --------------------------------------------------------------------------
# run_agentic: native function-calling
# --------------------------------------------------------------------------
def test_run_agentic_native_fc(monkeypatch):
    monkeypatch.setattr(agent_loop, "is_enabled", lambda: True)
    belt = _belt_with_ping()
    monkeypatch.setattr(agent_loop, "get_toolbelt", lambda: belt)

    turn1 = {
        "content": None,
        "tool_calls": [{"id": "1", "name": "ping", "arguments": "{}"}],
        "usage": {"total_tokens": 1},
        "finish_reason": "tool_calls",
    }
    turn2 = {"content": "done via tool", "tool_calls": [], "usage": {}, "finish_reason": "stop"}
    p = _FakeFCProvider(chat_returns=[turn1, turn2])

    resp = run_agentic(p, prompt="q", model_name="gpt")
    assert resp.metadata["toolbelt_mode"] == "native_fc"
    assert resp.metadata["toolbelt_used"] is True
    assert resp.metadata["toolbelt_calls"] >= 1
    assert resp.content == "done via tool"
    assert p.chat_calls == 2


# --------------------------------------------------------------------------
# run_agentic: ReAct text-protocol fallback
# --------------------------------------------------------------------------
def test_run_agentic_react(monkeypatch):
    monkeypatch.setattr(agent_loop, "is_enabled", lambda: True)
    belt = _belt_with_ping()
    monkeypatch.setattr(agent_loop, "get_toolbelt", lambda: belt)

    r1 = ModelResponse(content='<tool_call>{"name":"ping","args":{}}</tool_call>', model_name="g")
    r2 = ModelResponse(content="final answer", model_name="g")
    p = _ReactProvider([r1, r2])

    resp = run_agentic(p, prompt="q", model_name="gemini")
    assert resp.metadata["toolbelt_used"] is True
    assert resp.metadata["toolbelt_calls"] == 1
    assert "final answer" in resp.content
    assert "<tool_call>" not in resp.content
    assert "<tool_result>" not in resp.content


# --------------------------------------------------------------------------
# additional coverage (authored via PAL groq, verified locally)
# --------------------------------------------------------------------------
def _make_ping_tool():
    return ToolSpec(
        name="ping",
        description="returns pong",
        parameters={},
        handler=lambda _a: "pong",
    )


def test_schemas_respect_enabled_and_blocklist():
    belt = Toolbelt()
    belt.register(ToolSpec(name="a", description="A tool", parameters={}, handler=lambda _a: ""))
    belt.register(
        ToolSpec(
            name="b",
            description="B tool",
            parameters={},
            handler=lambda _a: "",
            provider_blocklist=("gpt",),
        )
    )
    belt.enable("a")
    belt.enable("b")

    schema = belt.openai_schema(provider="gpt")
    assert [f["function"]["name"] for f in schema] == ["a"]

    react = belt.react_schema(provider="gpt")
    assert "- a(" in react
    assert "- b(" not in react

    assert Toolbelt().react_schema(provider="any") == ""


def test_run_agentic_native_fc_truncation(monkeypatch):
    fake_provider = _FakeFCProvider(gen_returns=[], chat_returns=[])
    fake_provider.chat_with_tools = lambda **_: {
        "tool_calls": [{"id": "1", "name": "ping", "arguments": "{}"}],
        "content": "",
        "usage": {},
        "finish_reason": "tool_calls",
    }
    belt = _belt_with_ping()
    monkeypatch.setattr(agent_loop, "is_enabled", lambda: True)
    monkeypatch.setattr(agent_loop, "get_toolbelt", lambda: belt)

    resp = run_agentic(fake_provider, prompt="q", model_name="gpt", max_iters=2)
    assert resp.metadata.get("toolbelt_truncated") is True
    assert resp.metadata.get("toolbelt_mode") == "native_fc"


def test_bash_output_truncation():
    result = bash_adapter._run({"command": "head -c 40000 /dev/zero"})
    assert "[truncated," in result
    assert "bytes total]" in result


def test_execute_writes_audit_log(tmp_path):
    belt = Toolbelt()
    belt._log_path = tmp_path / "tc.log"
    belt.register(_make_ping_tool())
    belt.enable("ping")
    belt.execute("ping", {})
    assert belt._log_path.is_file()
    assert '"tool": "ping"' in belt._log_path.read_text()
