"""Tests covering shared retry behaviour for providers."""

from types import SimpleNamespace

import pytest

from providers.openai import OpenAIModelProvider


def _mock_chat_response(content: str = "retry success") -> SimpleNamespace:
    """Create a minimal chat completion response for tests."""

    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    return SimpleNamespace(choices=[choice], model="gpt-4.1", id="resp-1", created=123, usage=usage)


def test_openai_provider_retries_on_transient_error(monkeypatch):
    """Provider should retry once for retryable errors and eventually succeed."""

    monkeypatch.setattr("providers.base.time.sleep", lambda _: None)

    provider = OpenAIModelProvider(api_key="test-key")

    # Force use of Chat API (not Responses API) for this test
    mock_caps = SimpleNamespace(
        use_openai_response_api=False,
        supports_temperature=True,
        get_effective_temperature=lambda temp: temp,
    )
    monkeypatch.setattr(
        provider,
        "get_capabilities",
        lambda model_name: mock_caps,
    )

    attempts = {"count": 0}

    def create_completion(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary network interruption")
        return _mock_chat_response("second attempt response")

    provider._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create_completion)),
        responses=SimpleNamespace(create=lambda **_: None),
    )

    result = provider.generate_content("hello", "gpt-4.1")

    assert attempts["count"] == 2, "Expected a retry before succeeding"
    assert result.content == "second attempt response"


def test_openai_provider_bails_on_non_retryable_error(monkeypatch):
    """Provider should stop immediately when the error is marked non-retryable."""

    monkeypatch.setattr("providers.base.time.sleep", lambda _: None)

    provider = OpenAIModelProvider(api_key="test-key")

    # Force use of Chat API (not Responses API) for this test
    mock_caps = SimpleNamespace(
        use_openai_response_api=False,
        supports_temperature=True,
        get_effective_temperature=lambda temp: temp,
    )
    monkeypatch.setattr(
        provider,
        "get_capabilities",
        lambda model_name: mock_caps,
    )

    attempts = {"count": 0}

    def create_completion(**kwargs):
        attempts["count"] += 1
        raise RuntimeError("context length exceeded 429")

    provider._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create_completion)),
        responses=SimpleNamespace(create=lambda **_: None),
    )

    monkeypatch.setattr(
        OpenAIModelProvider,
        "_is_error_retryable",
        lambda self, error: False,
    )

    with pytest.raises(RuntimeError) as excinfo:
        provider.generate_content("hello", "gpt-4.1")

    assert "after 1 attempt" in str(excinfo.value)
    assert attempts["count"] == 1
