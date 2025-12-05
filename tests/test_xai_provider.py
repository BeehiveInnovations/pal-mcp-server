"""Tests for X.AI provider implementation."""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers.shared import ProviderType
from providers.xai import XAIModelProvider


class TestXAIProvider:
    """Test X.AI provider functionality."""

    def setup_method(self):
        """Set up clean state before each test."""
        # Clear restriction service cache before each test
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def teardown_method(self):
        """Clean up after each test to avoid singleton issues."""
        # Clear restriction service cache after each test
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    @patch.dict(os.environ, {"XAI_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        provider = XAIModelProvider("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.XAI
        assert provider.base_url == "https://api.x.ai/v1"

    def test_initialization_with_custom_url(self):
        """Test provider initialization with custom base URL."""
        provider = XAIModelProvider("test-key", base_url="https://custom.x.ai/v1")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.x.ai/v1"

    def test_model_validation(self):
        """Test model name validation."""
        provider = XAIModelProvider("test-key")

        # Test valid models (grok-4/4.1 aliases removed except "grok" which points to 4.1)
        assert provider.validate_model_name("grok-4") is True
        assert provider.validate_model_name("grok-3") is True
        assert provider.validate_model_name("grok-3-fast") is True
        assert provider.validate_model_name("grok") is True  # Points to grok-4-1-fast-reasoning now
        assert provider.validate_model_name("grok3") is True
        assert provider.validate_model_name("grokfast") is True
        assert provider.validate_model_name("grok3fast") is True

        # Test invalid model
        assert provider.validate_model_name("invalid-model") is False
        assert provider.validate_model_name("gpt-4") is False
        assert provider.validate_model_name("gemini-pro") is False

    def test_resolve_model_name(self):
        """Test model name resolution."""
        provider = XAIModelProvider("test-key")

        # Test shorthand resolution (grok now points to grok-4-1-fast-reasoning)
        assert provider._resolve_model_name("grok") == "grok-4-1-fast-reasoning"
        assert provider._resolve_model_name("grok3") == "grok-3"
        assert provider._resolve_model_name("grokfast") == "grok-3-fast"
        assert provider._resolve_model_name("grok3fast") == "grok-3-fast"

        # Test full name passthrough
        assert provider._resolve_model_name("grok-4") == "grok-4"
        assert provider._resolve_model_name("grok-3") == "grok-3"
        assert provider._resolve_model_name("grok-3-fast") == "grok-3-fast"

    def test_get_capabilities_grok3(self):
        """Test getting model capabilities for GROK-3."""
        provider = XAIModelProvider("test-key")

        capabilities = provider.get_capabilities("grok-3")
        assert capabilities.model_name == "grok-3"
        assert capabilities.friendly_name == "X.AI (Grok 3)"
        assert capabilities.context_window == 131_072
        assert capabilities.provider == ProviderType.XAI
        assert not capabilities.supports_extended_thinking
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True

        # Test temperature range
        assert capabilities.temperature_constraint.min_temp == 0.0
        assert capabilities.temperature_constraint.max_temp == 2.0
        assert capabilities.temperature_constraint.default_temp == 0.3

    def test_get_capabilities_grok4(self):
        """Test getting model capabilities for GROK-4."""
        provider = XAIModelProvider("test-key")

        capabilities = provider.get_capabilities("grok-4")
        assert capabilities.model_name == "grok-4"
        assert capabilities.friendly_name == "X.AI (Grok 4)"
        assert capabilities.context_window == 256_000
        assert capabilities.provider == ProviderType.XAI
        assert capabilities.supports_extended_thinking is True
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_json_mode is True
        assert capabilities.supports_images is True

        # Test temperature range
        assert capabilities.temperature_constraint.min_temp == 0.0
        assert capabilities.temperature_constraint.max_temp == 2.0
        assert capabilities.temperature_constraint.default_temp == 0.3

    def test_get_capabilities_grok3_fast(self):
        """Test getting model capabilities for GROK-3 Fast."""
        provider = XAIModelProvider("test-key")

        capabilities = provider.get_capabilities("grok-3-fast")
        assert capabilities.model_name == "grok-3-fast"
        assert capabilities.friendly_name == "X.AI (Grok 3 Fast)"
        assert capabilities.context_window == 131_072
        assert capabilities.provider == ProviderType.XAI
        assert not capabilities.supports_extended_thinking

    def test_get_capabilities_with_shorthand(self):
        """Test getting model capabilities with shorthand."""
        provider = XAIModelProvider("test-key")

        capabilities = provider.get_capabilities("grok")
        assert capabilities.model_name == "grok-4-1-fast-reasoning"  # Points to latest 4.1 now
        assert capabilities.context_window == 2_000_000  # 2M context for 4.1

        capabilities_fast = provider.get_capabilities("grokfast")
        assert capabilities_fast.model_name == "grok-3-fast"  # Should resolve to full name

    def test_unsupported_model_capabilities(self):
        """Test error handling for unsupported models."""
        provider = XAIModelProvider("test-key")

        with pytest.raises(ValueError, match="Unsupported model 'invalid-model' for provider xai"):
            provider.get_capabilities("invalid-model")

    def test_extended_thinking_flags(self):
        """X.AI capabilities should expose extended thinking support correctly."""
        provider = XAIModelProvider("test-key")

        # grok-4 and grok (points to 4.1) support extended thinking
        thinking_aliases = ["grok-4", "grok"]
        for alias in thinking_aliases:
            assert provider.get_capabilities(alias).supports_extended_thinking is True

        non_thinking_aliases = ["grok-3", "grok-3-fast", "grokfast"]
        for alias in non_thinking_aliases:
            assert provider.get_capabilities(alias).supports_extended_thinking is False

    def test_provider_type(self):
        """Test provider type identification."""
        provider = XAIModelProvider("test-key")
        assert provider.get_provider_type() == ProviderType.XAI

    @patch.dict(os.environ, {"XAI_ALLOWED_MODELS": "grok-3"})
    def test_model_restrictions(self):
        """Test model restrictions functionality."""
        # Clear cached restriction service
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()

        provider = XAIModelProvider("test-key")

        # grok-3 should be allowed
        assert provider.validate_model_name("grok-3") is True
        assert provider.validate_model_name("grok3") is True  # Shorthand for grok-3

        # grok should be blocked (resolves to grok-4 which is not allowed)
        assert provider.validate_model_name("grok") is False

        # grok-3-fast should be blocked by restrictions
        assert provider.validate_model_name("grok-3-fast") is False
        assert provider.validate_model_name("grokfast") is False

    @patch.dict(os.environ, {"XAI_ALLOWED_MODELS": "grok,grok-3-fast"})
    def test_multiple_model_restrictions(self):
        """Test multiple models in restrictions."""
        # Clear cached restriction service
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()

        provider = XAIModelProvider("test-key")

        # Shorthand "grok" should be allowed (resolves to grok-4)
        assert provider.validate_model_name("grok") is True

        # Full name "grok-4" should NOT be allowed (only shorthand "grok" is in restriction list)
        assert provider.validate_model_name("grok-4") is False

        # "grok-3" should NOT be allowed (not in restriction list)
        assert provider.validate_model_name("grok-3") is False

        # "grok-3-fast" should be allowed (explicitly listed)
        assert provider.validate_model_name("grok-3-fast") is True

        # Shorthand "grokfast" should be allowed (resolves to grok-3-fast)
        assert provider.validate_model_name("grokfast") is True

    @patch.dict(os.environ, {"XAI_ALLOWED_MODELS": "grok,grok-3,grok-4"})
    def test_both_shorthand_and_full_name_allowed(self):
        """Test that both shorthand and full name can be allowed."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = XAIModelProvider("test-key")

        # Both shorthand and full name should be allowed
        assert provider.validate_model_name("grok") is True  # Resolves to grok-4
        assert provider.validate_model_name("grok-3") is True
        assert provider.validate_model_name("grok-4") is True

        # Other models should not be allowed
        assert provider.validate_model_name("grok-3-fast") is False
        assert provider.validate_model_name("grokfast") is False

    @patch.dict(os.environ, {"XAI_ALLOWED_MODELS": ""})
    def test_empty_restrictions_allows_all(self):
        """Test that empty restrictions allow all models."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = XAIModelProvider("test-key")

        assert provider.validate_model_name("grok-4") is True
        assert provider.validate_model_name("grok-3") is True
        assert provider.validate_model_name("grok-3-fast") is True
        assert provider.validate_model_name("grok") is True  # Points to grok-4-1-fast-reasoning now
        assert provider.validate_model_name("grokfast") is True

    def test_friendly_name(self):
        """Test friendly name constant."""
        provider = XAIModelProvider("test-key")
        assert provider.FRIENDLY_NAME == "X.AI"

        capabilities = provider.get_capabilities("grok-3")
        assert capabilities.friendly_name == "X.AI (Grok 3)"

    def test_supported_models_structure(self):
        """Test that MODEL_CAPABILITIES has the correct structure."""
        provider = XAIModelProvider("test-key")

        # Check that all expected base models are present
        assert "grok-4" in provider.MODEL_CAPABILITIES
        assert "grok-3" in provider.MODEL_CAPABILITIES
        assert "grok-3-fast" in provider.MODEL_CAPABILITIES

        # Check model configs have required fields
        from providers.shared import ModelCapabilities

        grok4_config = provider.MODEL_CAPABILITIES["grok-4"]
        assert isinstance(grok4_config, ModelCapabilities)
        assert hasattr(grok4_config, "context_window")
        assert hasattr(grok4_config, "supports_extended_thinking")
        assert hasattr(grok4_config, "aliases")
        assert grok4_config.context_window == 256_000
        assert grok4_config.supports_extended_thinking is True

        # Check that grok-4 aliases were removed (empty list)
        assert grok4_config.aliases == []

        grok3_config = provider.MODEL_CAPABILITIES["grok-3"]
        assert grok3_config.context_window == 131_072
        assert grok3_config.supports_extended_thinking is False
        # Check aliases are correctly structured
        assert "grok3" in grok3_config.aliases  # grok3 resolves to grok-3

        # Check grok-4-1-fast-reasoning has the "grok" alias (points to latest)
        grok41_config = provider.MODEL_CAPABILITIES["grok-4-1-fast-reasoning"]
        assert "grok" in grok41_config.aliases  # grok points to 4.1 now

        grok3fast_config = provider.MODEL_CAPABILITIES["grok-3-fast"]
        assert "grok3fast" in grok3fast_config.aliases
        assert "grokfast" in grok3fast_config.aliases

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_resolves_alias_before_api_call(self, mock_openai_class):
        """Test that generate_content resolves aliases before making API calls.

        This is the CRITICAL test that ensures aliases like 'grok' get resolved
        to 'grok-4-1-fast-reasoning' (latest) before being sent to X.AI API.
        """
        # Set up mock OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock the completion response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "grok-4-1-fast-reasoning"  # API returns the resolved model name
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIModelProvider("test-key")

        # Call generate_content with alias 'grok'
        result = provider.generate_content(
            prompt="Test prompt", model_name="grok", temperature=0.7  # Resolves to grok-4-1-fast-reasoning
        )

        # Verify the API was called with the RESOLVED model name
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # CRITICAL ASSERTION: The API should receive "grok-4-1-fast-reasoning", not "grok"
        assert (
            call_kwargs["model"] == "grok-4-1-fast-reasoning"
        ), f"Expected 'grok-4-1-fast-reasoning' but API received '{call_kwargs['model']}'"

        # Verify other parameters
        assert call_kwargs["temperature"] == 0.7
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert call_kwargs["messages"][0]["content"] == "Test prompt"

        # Verify response
        assert result.content == "Test response"
        assert result.model_name == "grok-4-1-fast-reasoning"  # Should be the resolved name

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_other_aliases(self, mock_openai_class):
        """Test other alias resolutions in generate_content."""
        from unittest.mock import MagicMock

        # Set up mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIModelProvider("test-key")

        # Test grok-4 -> grok-4 (full name passthrough)
        mock_response.model = "grok-4"
        provider.generate_content(prompt="Test", model_name="grok-4", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "grok-4"

        # Test grok3 -> grok-3
        mock_response.model = "grok-3"
        provider.generate_content(prompt="Test", model_name="grok3", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "grok-3"

        # Test grokfast -> grok-3-fast
        mock_response.model = "grok-3-fast"
        provider.generate_content(prompt="Test", model_name="grokfast", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "grok-3-fast"

        # Test grok3fast -> grok-3-fast
        provider.generate_content(prompt="Test", model_name="grok3fast", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "grok-3-fast"
