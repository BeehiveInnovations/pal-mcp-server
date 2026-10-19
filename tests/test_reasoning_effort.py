"""Explicit reasoning effort: thinking_mode -> effort mapping and the request shape on each route.

Models that declare ``effort_levels`` get the tool's thinking_mode as an explicit effort, clamped to
the levels the route accepts. Models without ``effort_levels`` keep their previous request shape.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from providers.openai import OpenAIModelProvider
from providers.openrouter import OpenRouterProvider
from providers.shared.effort import DEFAULT_EFFORT, resolve_reasoning_effort


def _caps(levels):
    return SimpleNamespace(effort_levels=levels)


FULL = ["low", "medium", "high", "xhigh", "max"]
NO_MAX = ["low", "medium", "high", "xhigh"]


@pytest.mark.parametrize(
    "thinking_mode,levels,expected",
    [
        ("high", FULL, "high"),
        ("max", FULL, "max"),
        ("max", NO_MAX, "xhigh"),  # native OpenAI Chat Completions rejects "max"
        ("minimal", FULL, "low"),  # no level below low -> the lowest accepted level
        ("minimal", ["none", "low", "medium"], "none"),
        (None, FULL, DEFAULT_EFFORT),
        ("bogus", FULL, DEFAULT_EFFORT),
        ("high", [], None),  # no declared levels -> send nothing
        ("high", None, None),
    ],
)
def test_resolve_reasoning_effort(thinking_mode, levels, expected):
    assert resolve_reasoning_effort(thinking_mode, _caps(levels)) == expected


def _chat_response():
    message = SimpleNamespace(content="pong")
    choice = SimpleNamespace(message=message, finish_reason="stop")
    usage = SimpleNamespace(prompt_tokens=3, completion_tokens=1, total_tokens=4)
    return SimpleNamespace(choices=[choice], usage=usage, model="m", id="id", created=0)


def _with_mock_client(provider):
    client = MagicMock()
    client.chat.completions.create.return_value = _chat_response()
    provider._client = client
    return client


class TestOpenAINative:
    def test_gpt6_sends_effort_clamped_below_max(self):
        provider = OpenAIModelProvider("test-key")
        client = _with_mock_client(provider)
        resp = provider.generate_content(prompt="hi", model_name="sol", temperature=1.0, thinking_mode="max")
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "gpt-6.1-sol"
        assert kwargs["reasoning_effort"] == "xhigh"
        assert resp.metadata["reasoning_effort"] == "xhigh"

    def test_tool_default_thinking_mode_sends_medium(self):
        provider = OpenAIModelProvider("test-key")
        client = _with_mock_client(provider)
        provider.generate_content(prompt="hi", model_name="luna", temperature=1.0, thinking_mode="medium")
        assert client.chat.completions.create.call_args.kwargs["reasoning_effort"] == "medium"

    def test_model_without_effort_levels_is_unchanged(self):
        provider = OpenAIModelProvider("test-key")
        client = _with_mock_client(provider)
        provider.generate_content(prompt="hi", model_name="gpt-5.2", temperature=1.0, thinking_mode="high")
        assert "reasoning_effort" not in client.chat.completions.create.call_args.kwargs


class TestMaxOutputTokensField:
    def test_native_openai_sends_max_completion_tokens(self):
        # OpenAI's reasoning models reject max_tokens on Chat Completions.
        provider = OpenAIModelProvider("test-key")
        client = _with_mock_client(provider)
        provider.generate_content(prompt="hi", model_name="astra", temperature=1.0, max_output_tokens=2000)
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["max_completion_tokens"] == 2000
        assert "max_tokens" not in kwargs

    def test_openrouter_keeps_max_tokens(self):
        provider = OpenRouterProvider("test-key")
        client = _with_mock_client(provider)
        provider.generate_content(prompt="hi", model_name="or-gpt6-astra", temperature=1.0, max_output_tokens=2000)
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["max_tokens"] == 2000
        assert "max_completion_tokens" not in kwargs


class TestOpenRouter:
    @pytest.mark.parametrize(
        "model,thinking_mode,expected",
        [
            ("or-gpt6.1-sol", "max", "max"),
            ("or-gpt6-luna", "high", "high"),
            ("anthropic/claude-sonnet-5.5", "low", "low"),
            ("anthropic/claude-opus-5.5", "minimal", "low"),
        ],
    )
    def test_openrouter_sends_top_level_reasoning_effort(self, model, thinking_mode, expected):
        provider = OpenRouterProvider("test-key")
        client = _with_mock_client(provider)
        provider.generate_content(prompt="hi", model_name=model, temperature=1.0, thinking_mode=thinking_mode)
        assert client.chat.completions.create.call_args.kwargs["reasoning_effort"] == expected

    def test_openrouter_model_without_effort_levels_is_unchanged(self):
        provider = OpenRouterProvider("test-key")
        client = _with_mock_client(provider)
        provider.generate_content(prompt="hi", model_name="grok-4.7", temperature=1.0, thinking_mode="high")
        assert "reasoning_effort" not in client.chat.completions.create.call_args.kwargs
