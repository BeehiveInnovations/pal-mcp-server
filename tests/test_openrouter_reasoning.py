"""Tests for OpenRouter reasoning parameter forwarding and reasoning_details preservation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from providers.openai_compatible import OpenAICompatibleProvider
from providers.registries.openrouter import OpenRouterModelRegistry
from providers.shared import ModelCapabilities, ProviderType


class _DummyOpenRouterProvider(OpenAICompatibleProvider):
    FRIENDLY_NAME = "OpenRouter"

    def __init__(self, capabilities: ModelCapabilities):
        self._caps = capabilities
        self.api_key = "test-key"
        self.base_url = "https://openrouter.ai/api/v1"
        self._client = MagicMock()

    def get_provider_type(self) -> ProviderType:
        return ProviderType.OPENROUTER

    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        return self._caps

    def _resolve_model_name(self, model_name: str) -> str:
        return model_name

    def get_all_model_capabilities(self):
        return {self._caps.model_name: self._caps}


def _make_completion_response(model="openai/gpt-5.2", content="answer", reasoning_details=None):
    msg = SimpleNamespace(content=content, reasoning_details=reasoning_details)
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return SimpleNamespace(
        choices=[choice],
        usage=usage,
        model=model,
        id="chatcmpl-123",
        created=1700000000,
    )


def test_openrouter_reasoning_model_sends_extra_body_and_surfaces_reasoning_details():
    registry = OpenRouterModelRegistry()
    caps = registry.resolve("openai/gpt-5.2")
    assert caps is not None
    assert caps.supports_extended_thinking is True

    provider = _DummyOpenRouterProvider(caps)
    trace = [{"type": "reasoning.text", "text": "step by step"}]
    provider._client.chat.completions.create.return_value = _make_completion_response(
        model="openai/gpt-5.2", content="42", reasoning_details=trace
    )

    resp = provider.generate_content(prompt="What is 6*7?", model_name="openai/gpt-5.2")

    call_kwargs = provider._client.chat.completions.create.call_args.kwargs
    assert call_kwargs["extra_body"] == {"reasoning": {"effort": "medium"}}
    assert resp.metadata["reasoning_details"] == trace


def test_openrouter_thinking_mode_overrides_default_effort_including_max():
    registry = OpenRouterModelRegistry()
    caps = registry.resolve("openai/gpt-5.2")
    assert caps is not None

    provider = _DummyOpenRouterProvider(caps)
    provider._client.chat.completions.create.return_value = _make_completion_response()

    provider.generate_content(
        prompt="Solve", model_name="openai/gpt-5.2", thinking_mode="high"
    )
    assert provider._client.chat.completions.create.call_args.kwargs["extra_body"] == {
        "reasoning": {"effort": "high"}
    }

    provider.generate_content(
        prompt="Solve deeply", model_name="openai/gpt-5.2", thinking_mode="max"
    )
    assert provider._client.chat.completions.create.call_args.kwargs["extra_body"] == {
        "reasoning": {"effort": "xhigh"}
    }


def test_openrouter_non_reasoning_model_omits_reasoning_extra_body():
    caps = ModelCapabilities(
        provider=ProviderType.OPENROUTER,
        model_name="openai/gpt-4o-mini",
        friendly_name="GPT-4o mini",
        context_window=128000,
        max_output_tokens=4096,
        supports_extended_thinking=False,
    )
    provider = _DummyOpenRouterProvider(caps)
    provider._client.chat.completions.create.return_value = _make_completion_response(
        model="openai/gpt-4o-mini"
    )

    resp = provider.generate_content(prompt="Hi", model_name="openai/gpt-4o-mini")

    call_kwargs = provider._client.chat.completions.create.call_args.kwargs
    assert "extra_body" not in call_kwargs
    assert "reasoning_details" not in resp.metadata
