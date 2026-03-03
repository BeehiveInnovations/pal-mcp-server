"""Tests for Moonshot (Kimi) provider implementation."""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers.moonshot import MoonshotModelProvider
from providers.shared import ProviderType


class TestMoonshotProvider:
    """Test Moonshot provider functionality."""

    def setup_method(self):
        """Set up clean state before each test."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def teardown_method(self):
        """Clean up after each test to avoid singleton issues."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    @patch.dict(os.environ, {"MOONSHOT_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        provider = MoonshotModelProvider("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.MOONSHOT
        assert provider.base_url == "https://api.moonshot.cn/v1"

    def test_initialization_with_custom_url(self):
        """Test provider initialization with custom base URL."""
        provider = MoonshotModelProvider("test-key", base_url="https://api.moonshot.ai/v1")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://api.moonshot.ai/v1"

    def test_model_validation(self):
        """Test model name validation."""
        provider = MoonshotModelProvider("test-key")

        # Test valid models
        assert provider.validate_model_name("kimi-k2.5") is True
        assert provider.validate_model_name("kimi") is True
        assert provider.validate_model_name("kimi-k2") is True
        assert provider.validate_model_name("moonshot") is True
        assert provider.validate_model_name("kimi-k2-0905-preview") is True
        assert provider.validate_model_name("kimi-k2-0905") is True
        assert provider.validate_model_name("moonshot-v1-128k") is True
        assert provider.validate_model_name("moonshot-128k") is True
        assert provider.validate_model_name("moonshot-v1-32k") is True
        assert provider.validate_model_name("moonshot-32k") is True

        # Test invalid model
        assert provider.validate_model_name("invalid-model") is False
        assert provider.validate_model_name("gpt-4") is False
        assert provider.validate_model_name("gemini-pro") is False
        assert provider.validate_model_name("grok-4") is False

    def test_resolve_model_name(self):
        """Test model name resolution."""
        provider = MoonshotModelProvider("test-key")

        # Test shorthand resolution
        assert provider._resolve_model_name("kimi") == "kimi-k2.5"
        assert provider._resolve_model_name("kimi-k2") == "kimi-k2.5"
        assert provider._resolve_model_name("moonshot") == "kimi-k2.5"
        assert provider._resolve_model_name("kimi-k2-0905") == "kimi-k2-0905-preview"
        assert provider._resolve_model_name("moonshot-128k") == "moonshot-v1-128k"
        assert provider._resolve_model_name("moonshot-32k") == "moonshot-v1-32k"

        # Test full name passthrough
        assert provider._resolve_model_name("kimi-k2.5") == "kimi-k2.5"
        assert provider._resolve_model_name("moonshot-v1-128k") == "moonshot-v1-128k"

    def test_get_capabilities_kimi_k25(self):
        """Test getting model capabilities for Kimi K2.5."""
        provider = MoonshotModelProvider("test-key")

        capabilities = provider.get_capabilities("kimi-k2.5")
        assert capabilities.model_name == "kimi-k2.5"
        assert capabilities.friendly_name == "Moonshot (Kimi K2.5)"
        assert capabilities.context_window == 262_144
        assert capabilities.max_output_tokens == 65_535
        assert capabilities.provider == ProviderType.MOONSHOT
        assert capabilities.supports_extended_thinking is True
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_json_mode is True
        assert capabilities.supports_images is True

    def test_get_capabilities_legacy_model(self):
        """Test getting model capabilities for legacy Moonshot V1."""
        provider = MoonshotModelProvider("test-key")

        capabilities = provider.get_capabilities("moonshot-v1-128k")
        assert capabilities.model_name == "moonshot-v1-128k"
        assert capabilities.friendly_name == "Moonshot (V1 128K)"
        assert capabilities.context_window == 131_072
        assert capabilities.max_output_tokens == 8_192
        assert capabilities.provider == ProviderType.MOONSHOT
        assert capabilities.supports_extended_thinking is False
        assert capabilities.supports_images is False

    def test_get_capabilities_with_shorthand(self):
        """Test getting model capabilities with shorthand."""
        provider = MoonshotModelProvider("test-key")

        capabilities = provider.get_capabilities("kimi")
        assert capabilities.model_name == "kimi-k2.5"
        assert capabilities.context_window == 262_144

        capabilities_128k = provider.get_capabilities("moonshot-128k")
        assert capabilities_128k.model_name == "moonshot-v1-128k"

    def test_unsupported_model_capabilities(self):
        """Test error handling for unsupported models."""
        provider = MoonshotModelProvider("test-key")

        with pytest.raises(ValueError, match="Unsupported model 'invalid-model' for provider moonshot"):
            provider.get_capabilities("invalid-model")

    def test_extended_thinking_flags(self):
        """Moonshot capabilities should expose extended thinking support correctly."""
        provider = MoonshotModelProvider("test-key")

        thinking_models = ["kimi-k2.5", "kimi", "kimi-k2", "moonshot", "kimi-k2-0905-preview", "kimi-k2-0905"]
        for alias in thinking_models:
            assert provider.get_capabilities(alias).supports_extended_thinking is True

        non_thinking_models = ["moonshot-v1-128k", "moonshot-128k", "moonshot-v1-32k", "moonshot-32k"]
        for alias in non_thinking_models:
            assert provider.get_capabilities(alias).supports_extended_thinking is False

    def test_provider_type(self):
        """Test provider type identification."""
        provider = MoonshotModelProvider("test-key")
        assert provider.get_provider_type() == ProviderType.MOONSHOT

    @patch.dict(os.environ, {"MOONSHOT_ALLOWED_MODELS": "kimi-k2.5"})
    def test_model_restrictions(self):
        """Test model restrictions functionality."""
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()

        provider = MoonshotModelProvider("test-key")

        # kimi-k2.5 should be allowed (including alias)
        assert provider.validate_model_name("kimi-k2.5") is True
        assert provider.validate_model_name("kimi") is True

        # moonshot-v1-128k should be blocked by restrictions
        assert provider.validate_model_name("moonshot-v1-128k") is False
        assert provider.validate_model_name("moonshot-128k") is False

    @patch.dict(os.environ, {"MOONSHOT_ALLOWED_MODELS": ""})
    def test_empty_restrictions_allows_all(self):
        """Test that empty restrictions allow all models."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = MoonshotModelProvider("test-key")

        assert provider.validate_model_name("kimi-k2.5") is True
        assert provider.validate_model_name("moonshot-v1-128k") is True
        assert provider.validate_model_name("moonshot-v1-32k") is True
        assert provider.validate_model_name("kimi") is True

    def test_friendly_name(self):
        """Test friendly name constant."""
        provider = MoonshotModelProvider("test-key")
        assert provider.FRIENDLY_NAME == "Moonshot"

        capabilities = provider.get_capabilities("kimi-k2.5")
        assert capabilities.friendly_name == "Moonshot (Kimi K2.5)"

    def test_supported_models_structure(self):
        """Test that MODEL_CAPABILITIES has the correct structure."""
        provider = MoonshotModelProvider("test-key")

        # Check that all expected base models are present
        assert "kimi-k2.5" in provider.MODEL_CAPABILITIES
        assert "kimi-k2-0905-preview" in provider.MODEL_CAPABILITIES
        assert "moonshot-v1-128k" in provider.MODEL_CAPABILITIES
        assert "moonshot-v1-32k" in provider.MODEL_CAPABILITIES

        # Check model configs have required fields
        from providers.shared import ModelCapabilities

        kimi_config = provider.MODEL_CAPABILITIES["kimi-k2.5"]
        assert isinstance(kimi_config, ModelCapabilities)
        assert hasattr(kimi_config, "context_window")
        assert hasattr(kimi_config, "supports_extended_thinking")
        assert hasattr(kimi_config, "aliases")
        assert kimi_config.context_window == 262_144
        assert kimi_config.supports_extended_thinking is True

        # Check aliases are correctly structured
        assert "kimi" in kimi_config.aliases
        assert "kimi-k2.5" in kimi_config.aliases
        assert "kimi-k2" in kimi_config.aliases
        assert "moonshot" in kimi_config.aliases

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_resolves_alias_before_api_call(self, mock_openai_class):
        """Test that generate_content resolves aliases before making API calls."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "kimi-k2.5"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        provider = MoonshotModelProvider("test-key")

        result = provider.generate_content(prompt="Test prompt", model_name="kimi", temperature=0.7)

        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # CRITICAL: The API should receive "kimi-k2.5", not "kimi"
        assert call_kwargs["model"] == "kimi-k2.5", f"Expected 'kimi-k2.5' but API received '{call_kwargs['model']}'"

        assert result.content == "Test response"
        assert result.model_name == "kimi-k2.5"
