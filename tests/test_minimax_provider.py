"""Tests for MiniMax provider implementation."""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers.minimax import MiniMaxModelProvider
from providers.shared import ProviderType


class TestMiniMaxProvider:
    """Test MiniMax provider functionality."""

    def setup_method(self):
        """Set up clean state before each test."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def teardown_method(self):
        """Clean up after each test to avoid singleton issues."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    @patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        provider = MiniMaxModelProvider("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.MINIMAX
        assert provider.base_url == "https://api.minimax.io/v1"

    def test_initialization_with_custom_url(self):
        """Test provider initialization with custom base URL."""
        provider = MiniMaxModelProvider("test-key", base_url="https://custom.minimax.io/v1")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.minimax.io/v1"

    def test_model_validation(self):
        """Test model name validation."""
        provider = MiniMaxModelProvider("test-key")

        # Test valid models (canonical names)
        assert provider.validate_model_name("MiniMax-M2.5") is True
        assert provider.validate_model_name("MiniMax-M2.5-highspeed") is True
        assert provider.validate_model_name("MiniMax-M2.1") is True
        assert provider.validate_model_name("MiniMax-M2.1-highspeed") is True
        assert provider.validate_model_name("MiniMax-M2") is True

        # Test valid aliases
        assert provider.validate_model_name("m2.5") is True
        assert provider.validate_model_name("m2.5-fast") is True
        assert provider.validate_model_name("m2.1") is True
        assert provider.validate_model_name("m2.1-fast") is True
        assert provider.validate_model_name("m2") is True
        assert provider.validate_model_name("minimax") is True

        # Test invalid models
        assert provider.validate_model_name("invalid-model") is False
        assert provider.validate_model_name("gpt-4") is False
        assert provider.validate_model_name("gemini-pro") is False
        assert provider.validate_model_name("grok-4") is False

    def test_resolve_model_name(self):
        """Test model name resolution."""
        provider = MiniMaxModelProvider("test-key")

        # Test alias resolution
        assert provider._resolve_model_name("m2.5") == "MiniMax-M2.5"
        assert provider._resolve_model_name("minimax") == "MiniMax-M2.5"
        assert provider._resolve_model_name("m2.5-fast") == "MiniMax-M2.5-highspeed"
        assert provider._resolve_model_name("m2.1") == "MiniMax-M2.1"
        assert provider._resolve_model_name("m2.1-fast") == "MiniMax-M2.1-highspeed"
        assert provider._resolve_model_name("m2") == "MiniMax-M2"

        # Test canonical name passthrough
        assert provider._resolve_model_name("MiniMax-M2.5") == "MiniMax-M2.5"
        assert provider._resolve_model_name("MiniMax-M2.5-highspeed") == "MiniMax-M2.5-highspeed"
        assert provider._resolve_model_name("MiniMax-M2.1") == "MiniMax-M2.1"
        assert provider._resolve_model_name("MiniMax-M2") == "MiniMax-M2"

    def test_get_capabilities_m25(self):
        """Test getting model capabilities for MiniMax-M2.5."""
        provider = MiniMaxModelProvider("test-key")

        capabilities = provider.get_capabilities("MiniMax-M2.5")
        assert capabilities.model_name == "MiniMax-M2.5"
        assert capabilities.friendly_name == "MiniMax (M2.5)"
        assert capabilities.context_window == 196_608
        assert capabilities.max_output_tokens == 196_608
        assert capabilities.provider == ProviderType.MINIMAX
        assert capabilities.supports_extended_thinking is False
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_json_mode is True
        assert capabilities.supports_images is False

    def test_get_capabilities_m25_highspeed(self):
        """Test getting model capabilities for MiniMax-M2.5-highspeed."""
        provider = MiniMaxModelProvider("test-key")

        capabilities = provider.get_capabilities("m2.5-fast")
        assert capabilities.model_name == "MiniMax-M2.5-highspeed"
        assert capabilities.friendly_name == "MiniMax (M2.5 Highspeed)"
        assert capabilities.context_window == 204_800
        assert capabilities.max_output_tokens == 100_000
        assert capabilities.provider == ProviderType.MINIMAX
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_images is False

    def test_get_capabilities_m21(self):
        """Test getting model capabilities for MiniMax-M2.1."""
        provider = MiniMaxModelProvider("test-key")

        capabilities = provider.get_capabilities("m2.1")
        assert capabilities.model_name == "MiniMax-M2.1"
        assert capabilities.friendly_name == "MiniMax (M2.1)"
        assert capabilities.context_window == 204_800
        assert capabilities.provider == ProviderType.MINIMAX

    def test_get_capabilities_m2(self):
        """Test getting model capabilities for MiniMax-M2."""
        provider = MiniMaxModelProvider("test-key")

        capabilities = provider.get_capabilities("m2")
        assert capabilities.model_name == "MiniMax-M2"
        assert capabilities.friendly_name == "MiniMax (M2)"
        assert capabilities.context_window == 204_800
        assert capabilities.provider == ProviderType.MINIMAX

    def test_get_capabilities_with_shorthand(self):
        """Test getting model capabilities with shorthand."""
        provider = MiniMaxModelProvider("test-key")

        capabilities = provider.get_capabilities("minimax")
        assert capabilities.model_name == "MiniMax-M2.5"
        assert capabilities.context_window == 196_608

        capabilities_fast = provider.get_capabilities("m2.5-fast")
        assert capabilities_fast.model_name == "MiniMax-M2.5-highspeed"

    def test_unsupported_model_capabilities(self):
        """Test error handling for unsupported models."""
        provider = MiniMaxModelProvider("test-key")

        with pytest.raises(ValueError, match="Unsupported model 'invalid-model' for provider minimax"):
            provider.get_capabilities("invalid-model")

    def test_no_extended_thinking(self):
        """MiniMax models should not expose extended thinking support."""
        provider = MiniMaxModelProvider("test-key")

        all_models = [
            "MiniMax-M2.5",
            "m2.5-fast",
            "m2.1",
            "m2.1-fast",
            "m2",
        ]
        for model in all_models:
            assert provider.get_capabilities(model).supports_extended_thinking is False

    def test_no_image_support(self):
        """MiniMax models should not support images."""
        provider = MiniMaxModelProvider("test-key")

        all_models = [
            "MiniMax-M2.5",
            "m2.5-fast",
            "m2.1",
            "m2.1-fast",
            "m2",
        ]
        for model in all_models:
            assert provider.get_capabilities(model).supports_images is False

    def test_provider_type(self):
        """Test provider type identification."""
        provider = MiniMaxModelProvider("test-key")
        assert provider.get_provider_type() == ProviderType.MINIMAX

    @patch.dict(os.environ, {"MINIMAX_ALLOWED_MODELS": "MiniMax-M2.5"})
    def test_model_restrictions(self):
        """Test model restrictions functionality."""
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()

        provider = MiniMaxModelProvider("test-key")

        # MiniMax-M2.5 should be allowed (including alias)
        assert provider.validate_model_name("MiniMax-M2.5") is True
        assert provider.validate_model_name("m2.5") is True

        # Other models should be blocked by restrictions
        assert provider.validate_model_name("MiniMax-M2.5-highspeed") is False
        assert provider.validate_model_name("m2.5-fast") is False
        assert provider.validate_model_name("MiniMax-M2") is False

    @patch.dict(os.environ, {"MINIMAX_ALLOWED_MODELS": ""})
    def test_empty_restrictions_allows_all(self):
        """Test that empty restrictions allow all models."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = MiniMaxModelProvider("test-key")

        assert provider.validate_model_name("MiniMax-M2.5") is True
        assert provider.validate_model_name("MiniMax-M2.5-highspeed") is True
        assert provider.validate_model_name("MiniMax-M2.1") is True
        assert provider.validate_model_name("MiniMax-M2.1-highspeed") is True
        assert provider.validate_model_name("MiniMax-M2") is True
        assert provider.validate_model_name("m2.5") is True
        assert provider.validate_model_name("minimax") is True

    def test_friendly_name(self):
        """Test friendly name constant."""
        provider = MiniMaxModelProvider("test-key")
        assert provider.FRIENDLY_NAME == "MiniMax"

        capabilities = provider.get_capabilities("MiniMax-M2.5")
        assert capabilities.friendly_name == "MiniMax (M2.5)"

    def test_supported_models_structure(self):
        """Test that MODEL_CAPABILITIES has the correct structure."""
        provider = MiniMaxModelProvider("test-key")

        # Check that all expected models are present
        assert "MiniMax-M2.5" in provider.MODEL_CAPABILITIES
        assert "MiniMax-M2.5-highspeed" in provider.MODEL_CAPABILITIES
        assert "MiniMax-M2.1" in provider.MODEL_CAPABILITIES
        assert "MiniMax-M2.1-highspeed" in provider.MODEL_CAPABILITIES
        assert "MiniMax-M2" in provider.MODEL_CAPABILITIES

        # Check model configs have required fields
        from providers.shared import ModelCapabilities

        m25_config = provider.MODEL_CAPABILITIES["MiniMax-M2.5"]
        assert isinstance(m25_config, ModelCapabilities)
        assert hasattr(m25_config, "context_window")
        assert hasattr(m25_config, "supports_extended_thinking")
        assert hasattr(m25_config, "aliases")
        assert m25_config.context_window == 196_608
        assert m25_config.supports_extended_thinking is False
        assert m25_config.supports_images is False

        # Check aliases are correctly structured
        assert "m2.5" in m25_config.aliases
        assert "minimax" in m25_config.aliases

        m25hs_config = provider.MODEL_CAPABILITIES["MiniMax-M2.5-highspeed"]
        assert m25hs_config.context_window == 204_800
        assert "m2.5-fast" in m25hs_config.aliases

    def test_preferred_model_extended_reasoning(self):
        """Test preferred model for extended reasoning category."""
        from tools.models import ToolModelCategory

        provider = MiniMaxModelProvider("test-key")
        all_models = list(provider.MODEL_CAPABILITIES.keys())

        preferred = provider.get_preferred_model(ToolModelCategory.EXTENDED_REASONING, all_models)
        assert preferred == "MiniMax-M2.5"

    def test_preferred_model_fast_response(self):
        """Test preferred model for fast response category."""
        from tools.models import ToolModelCategory

        provider = MiniMaxModelProvider("test-key")
        all_models = list(provider.MODEL_CAPABILITIES.keys())

        preferred = provider.get_preferred_model(ToolModelCategory.FAST_RESPONSE, all_models)
        assert preferred == "MiniMax-M2.5-highspeed"

    def test_preferred_model_balanced(self):
        """Test preferred model for balanced category."""
        from tools.models import ToolModelCategory

        provider = MiniMaxModelProvider("test-key")
        all_models = list(provider.MODEL_CAPABILITIES.keys())

        preferred = provider.get_preferred_model(ToolModelCategory.BALANCED, all_models)
        assert preferred == "MiniMax-M2.5"

    def test_preferred_model_empty_list(self):
        """Test preferred model with empty allowed models list."""
        from tools.models import ToolModelCategory

        provider = MiniMaxModelProvider("test-key")

        preferred = provider.get_preferred_model(ToolModelCategory.BALANCED, [])
        assert preferred is None

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_resolves_alias_before_api_call(self, mock_openai_class):
        """Test that generate_content resolves aliases before making API calls.

        This is the CRITICAL test that ensures aliases like 'minimax' get resolved
        to 'MiniMax-M2.5' before being sent to the MiniMax API.
        """
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "MiniMax-M2.5"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        provider = MiniMaxModelProvider("test-key")

        result = provider.generate_content(
            prompt="Test prompt",
            model_name="minimax",
            temperature=0.7,
        )

        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # CRITICAL: The API should receive "MiniMax-M2.5", not "minimax"
        assert (
            call_kwargs["model"] == "MiniMax-M2.5"
        ), f"Expected 'MiniMax-M2.5' but API received '{call_kwargs['model']}'"

        assert call_kwargs["temperature"] == 0.7
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert call_kwargs["messages"][0]["content"] == "Test prompt"

        assert result.content == "Test response"
        assert result.model_name == "MiniMax-M2.5"

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_other_aliases(self, mock_openai_class):
        """Test other alias resolutions in generate_content."""
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

        provider = MiniMaxModelProvider("test-key")

        # Test m2.5 -> MiniMax-M2.5
        mock_response.model = "MiniMax-M2.5"
        provider.generate_content(prompt="Test", model_name="m2.5", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "MiniMax-M2.5"

        # Test m2.5-fast -> MiniMax-M2.5-highspeed
        mock_response.model = "MiniMax-M2.5-highspeed"
        provider.generate_content(prompt="Test", model_name="m2.5-fast", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "MiniMax-M2.5-highspeed"

        # Test m2 -> MiniMax-M2
        mock_response.model = "MiniMax-M2"
        provider.generate_content(prompt="Test", model_name="m2", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "MiniMax-M2"

    def test_list_models(self):
        """Test that list_models returns all MiniMax models and aliases."""
        provider = MiniMaxModelProvider("test-key")
        models = provider.list_models(respect_restrictions=False)

        # Canonical names should be present
        assert "MiniMax-M2.5" in models
        assert "MiniMax-M2.5-highspeed" in models
        assert "MiniMax-M2.1" in models
        assert "MiniMax-M2.1-highspeed" in models
        assert "MiniMax-M2" in models

        # Aliases should also be present
        assert "m2.5" in models
        assert "m2.5-fast" in models
        assert "m2.1" in models
        assert "m2.1-fast" in models
        assert "m2" in models
        assert "minimax" in models
