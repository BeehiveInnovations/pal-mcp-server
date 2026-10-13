"""Tests for Cheaper Inference provider implementation."""

import os
from unittest.mock import MagicMock, patch

from providers.cheaperinference import CheaperInferenceModelProvider
from providers.shared import ModelCapabilities, ProviderType


class TestCheaperInferenceProvider:
    """Test Cheaper Inference provider functionality."""

    def setup_method(self):
        """Set up clean state before each test."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def teardown_method(self):
        """Clean up after each test to avoid singleton issues."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    @patch.dict(os.environ, {"CHEAPER_INFERENCE_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        provider = CheaperInferenceModelProvider("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.CHEAPERINFERENCE
        assert provider.base_url == "https://api.cheaperinference.com/v1"

    def test_initialization_with_custom_url(self):
        """Test provider initialization with custom base URL."""
        provider = CheaperInferenceModelProvider("test-key", base_url="https://custom.example.com/v1")
        assert provider.base_url == "https://custom.example.com/v1"

    @patch.dict(os.environ, {"CHEAPER_INFERENCE_ALLOWED_MODELS": ""})
    def test_model_validation(self):
        """Test model name validation."""
        provider = CheaperInferenceModelProvider("test-key")

        assert provider.validate_model_name("gpt-5.4-mini") is True
        assert provider.validate_model_name("ci-mini") is True
        assert provider.validate_model_name("claude-sonnet-5") is True
        assert provider.validate_model_name("glm-5.3") is True

        assert provider.validate_model_name("invalid-model") is False

    def test_resolve_model_name(self):
        """Test model name resolution."""
        provider = CheaperInferenceModelProvider("test-key")

        assert provider._resolve_model_name("ci-mini") == "gpt-5.4-mini"
        assert provider._resolve_model_name("ci-sonnet") == "claude-sonnet-5"
        assert provider._resolve_model_name("gpt-5.4") == "gpt-5.4"

    def test_get_capabilities(self):
        """Test getting model capabilities."""
        provider = CheaperInferenceModelProvider("test-key")

        capabilities = provider.get_capabilities("ci-mini")
        assert isinstance(capabilities, ModelCapabilities)
        assert capabilities.model_name == "gpt-5.4-mini"
        assert capabilities.friendly_name == "Cheaper Inference (GPT-5.4 Mini)"
        assert capabilities.provider == ProviderType.CHEAPERINFERENCE
        assert capabilities.context_window == 400_000

    @patch.dict(os.environ, {"CHEAPER_INFERENCE_ALLOWED_MODELS": "gpt-5.4-mini"})
    def test_model_restrictions(self):
        """Test model restrictions functionality."""
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()

        provider = CheaperInferenceModelProvider("test-key")

        assert provider.validate_model_name("gpt-5.4-mini") is True
        assert provider.validate_model_name("claude-sonnet-5") is False

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_resolves_alias_before_api_call(self, mock_openai_class):
        """Test that generate_content sends the resolved model name to the API."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-5.4-mini"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        provider = CheaperInferenceModelProvider("test-key")

        result = provider.generate_content(prompt="Test prompt", model_name="ci-mini", temperature=0.7)

        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-5.4-mini"
        assert call_kwargs["messages"][0]["content"] == "Test prompt"

        assert result.content == "Test response"
        assert result.model_name == "gpt-5.4-mini"
