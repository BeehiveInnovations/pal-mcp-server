from unittest.mock import MagicMock, patch

import pytest

from providers.anthropic_compatible import AnthropicCompatibleProvider
from providers.shared.provider_type import ProviderType


def test_refuse_anthropic_com_base_url():
    with pytest.raises(ValueError):
        AnthropicCompatibleProvider("test-key", base_url="https://api.anthropic.com")

    with pytest.raises(ValueError):
        AnthropicCompatibleProvider("test-key", base_url="https://API.ANTHROPIC.COM/v1")


def test_refuse_claude_model():
    provider = AnthropicCompatibleProvider("test-key", base_url="https://gateway.example.com")
    with pytest.raises(ValueError):
        provider.generate_content("hello", model_name="claude-3-opus")

    assert not provider.validate_model_name("claude-3-sonnet")
    assert provider.validate_model_name("some-other-model")


@patch("providers.anthropic_compatible.httpx.post")
def test_generate_content_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [
            {"type": "text", "text": "Hello from gateway!"}
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5}
    }
    mock_post.return_value = mock_response

    provider = AnthropicCompatibleProvider(
        api_key="my-key",
        base_url="https://gateway.example.com",
        extra_headers={"x-custom": "val"},
    )

    response = provider.generate_content(
        prompt="Hi",
        model_name="custom-model",
        system_prompt="Be nice",
        temperature=0.5,
        max_output_tokens=100
    )

    assert response.content == "Hello from gateway!"
    assert response.model_name == "custom-model"
    assert response.provider == ProviderType.ANTHROPIC_COMPAT
    assert response.usage == {"input_tokens": 10, "output_tokens": 5}

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
    assert kwargs["headers"]["x-api-key"] == "my-key"
    assert kwargs["headers"]["x-custom"] == "val"
    assert kwargs["json"]["model"] == "custom-model"
    assert kwargs["json"]["system"] == "Be nice"
