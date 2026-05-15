"""Tests for Z.AI provider implementation."""

import os
from unittest.mock import MagicMock, patch

import openai
import pytest

from providers.shared import ProviderType
from providers.zai import ZAIModelProvider

ZAI_PLACEHOLDER_KEYS = {
    "dummy-key-for-tests",
    "dummy-key-for-replay",
    "your-zai-api-key",
    "your-zai-api-key-here",
    "your_api_key",
    "zai_api_key",
    "your_zai_api_key_here",
}


def _has_real_zai_api_key(api_key: str | None) -> bool:
    if not api_key:
        return False

    return api_key.strip().lower() not in ZAI_PLACEHOLDER_KEYS


# ---------------------------------------------------------------------------
# Integration smoke tests (require ZAI_API_KEY or exercise auth-failure path)
# ---------------------------------------------------------------------------


class TestZAIIntegration:
    """Integration tests for Z.AI provider -- real API calls."""

    @pytest.mark.integration
    def test_zai_auth_failure(self):
        """An invalid API key should raise on generate_content."""
        provider = ZAIModelProvider("invalid-test-key-00000")
        with pytest.raises((RuntimeError, openai.AuthenticationError)):
            provider.generate_content(
                prompt="Say hello.",
                model_name="glm-4.6",
                temperature=0.3,
            )

    @pytest.mark.integration
    def test_zai_basic_completion(self):
        """Basic completion smoke test -- skipped when ZAI_API_KEY is absent."""
        api_key = os.getenv("ZAI_API_KEY")
        if not _has_real_zai_api_key(api_key):
            pytest.skip("ZAI_API_KEY not set to a real credential")

        provider = ZAIModelProvider(api_key)
        result = provider.generate_content(
            prompt="Respond with exactly the word 'hello'.",
            model_name="glm-4.6",
            temperature=0.0,
        )
        assert result is not None
        assert result.content is not None
        assert len(result.content.strip()) > 0


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestZAIProvider:
    """Test Z.AI provider functionality."""

    def setup_method(self):
        """Clear restriction service cache before each test."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def teardown_method(self):
        """Clear restriction service cache after each test."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    @pytest.mark.parametrize(
        "api_key",
        [
            None,
            "",
            "dummy-key-for-tests",
            "dummy-key-for-replay",
            "YOUR-ZAI-API-KEY",
            "your-zai-api-key-here",
            "your_zai_api_key_here",
            "ZAI_API_KEY",
        ],
    )
    def test_placeholder_api_keys_are_not_treated_as_real_credentials(self, api_key):
        """Integration smoke tests should skip when only placeholders are configured."""
        assert _has_real_zai_api_key(api_key) is False

    def test_non_placeholder_api_key_is_treated_as_real_credential(self):
        """A non-placeholder key should allow the integration smoke test to run."""
        assert _has_real_zai_api_key("zai-real-looking-key") is True

    def test_initialization(self):
        """Test provider initialization."""
        provider = ZAIModelProvider("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.ZAI
        assert provider.base_url == "https://api.z.ai/api/paas/v4"

    def test_initialization_with_custom_url(self):
        """Test provider initialization with custom base URL."""
        provider = ZAIModelProvider("test-key", base_url="https://custom.z.ai/v4")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.z.ai/v4"

    def test_model_validation(self):
        """Test model validation and aliases."""
        provider = ZAIModelProvider("test-key")

        # Valid models
        assert provider.validate_model_name("glm-4.6") is True
        assert provider.validate_model_name("glm") is True
        assert provider.validate_model_name("glm-4") is True
        assert provider.validate_model_name("glm4.6") is True

        # Invalid models
        assert provider.validate_model_name("invalid-model") is False
        assert provider.validate_model_name("grok-4") is False
        assert provider.validate_model_name("gpt-4") is False
        assert provider.validate_model_name("gemini-pro") is False

    def test_resolve_model_name(self):
        """Test alias resolution."""
        provider = ZAIModelProvider("test-key")

        assert provider._resolve_model_name("glm") == "glm-4.6"
        assert provider._resolve_model_name("glm-4") == "glm-4.6"
        assert provider._resolve_model_name("glm4.6") == "glm-4.6"
        assert provider._resolve_model_name("glm-4.6") == "glm-4.6"

    def test_get_capabilities(self):
        """Test capabilities for GLM-4.6."""
        provider = ZAIModelProvider("test-key")

        capabilities = provider.get_capabilities("glm-4.6")
        assert capabilities.model_name == "glm-4.6"
        assert capabilities.friendly_name == "Z.AI (GLM-4.6)"
        assert capabilities.provider == ProviderType.ZAI
        assert capabilities.context_window == 200_000
        assert capabilities.max_output_tokens == 128_000
        assert capabilities.supports_extended_thinking is True
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_json_mode is True
        assert capabilities.supports_images is False
        assert capabilities.supports_temperature is True
        assert capabilities.temperature_constraint.min_temp == 0.0
        assert capabilities.temperature_constraint.max_temp == 1.0
        assert capabilities.temperature_constraint.default_temp == 1.0

    def test_get_capabilities_with_shorthand(self):
        """Test getting model capabilities with shorthand aliases."""
        provider = ZAIModelProvider("test-key")

        for alias in ["glm", "glm-4", "glm4.6"]:
            capabilities = provider.get_capabilities(alias)
            assert capabilities.model_name == "glm-4.6"
            assert capabilities.context_window == 200_000

    def test_invalid_model_capabilities(self):
        """Unsupported models should raise."""
        provider = ZAIModelProvider("test-key")

        with pytest.raises(ValueError, match="Unsupported model 'invalid-model' for provider zai"):
            provider.get_capabilities("invalid-model")

    def test_extended_thinking_flags(self):
        """Z.AI capabilities should expose extended thinking support correctly."""
        provider = ZAIModelProvider("test-key")

        thinking_aliases = ["glm-4.6", "glm", "glm-4", "glm4.6"]
        for alias in thinking_aliases:
            assert provider.get_capabilities(alias).supports_extended_thinking is True

    def test_provider_type(self):
        """Test provider type identification."""
        provider = ZAIModelProvider("test-key")
        assert provider.get_provider_type() == ProviderType.ZAI

    def test_friendly_name(self):
        """Test friendly name constant."""
        provider = ZAIModelProvider("test-key")
        assert provider.FRIENDLY_NAME == "Z.AI"

        capabilities = provider.get_capabilities("glm-4.6")
        assert capabilities.friendly_name == "Z.AI (GLM-4.6)"

    def test_supported_models_structure(self):
        """Test that MODEL_CAPABILITIES has the correct structure."""
        provider = ZAIModelProvider("test-key")

        # Check that the expected base model is present
        assert "glm-4.6" in provider.MODEL_CAPABILITIES

        # Check model config has required fields
        from providers.shared import ModelCapabilities

        glm_config = provider.MODEL_CAPABILITIES["glm-4.6"]
        assert isinstance(glm_config, ModelCapabilities)
        assert hasattr(glm_config, "context_window")
        assert hasattr(glm_config, "supports_extended_thinking")
        assert hasattr(glm_config, "aliases")
        assert glm_config.context_window == 200_000
        assert glm_config.supports_extended_thinking is True

        # Check aliases are correctly structured
        assert "glm" in glm_config.aliases
        assert "glm-4" in glm_config.aliases
        assert "glm4.6" in glm_config.aliases
        assert "glm-4.6" in glm_config.aliases

    def test_get_preferred_model_respects_allowed_models(self):
        """Preferred model selection must respect allow-list input."""
        from tools.models import ToolModelCategory

        provider = ZAIModelProvider("test-key")

        assert provider.get_preferred_model(ToolModelCategory.BALANCED, ["glm-4.6"]) == "glm-4.6"
        assert provider.get_preferred_model(ToolModelCategory.EXTENDED_REASONING, ["glm-4.6"]) == "glm-4.6"
        assert provider.get_preferred_model(ToolModelCategory.FAST_RESPONSE, ["glm-4.6"]) == "glm-4.6"
        assert provider.get_preferred_model(ToolModelCategory.BALANCED, []) is None

    @patch.dict(os.environ, {"ZAI_ALLOWED_MODELS": "glm-4.6"})
    def test_model_restrictions(self):
        """Test Z.AI allow-list restrictions."""
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()

        provider = ZAIModelProvider("test-key")

        assert provider.validate_model_name("glm-4.6") is True
        assert provider.validate_model_name("glm") is True
        assert provider.validate_model_name("glm4.6") is True

    @patch.dict(os.environ, {"ZAI_ALLOWED_MODELS": "glm"})
    def test_alias_allowlist_resolution(self):
        """Alias allow-list entries should resolve to canonical model."""
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry
        from providers.shared import ProviderType

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()
        # Re-register so the alias-aware lookup in ``is_allowed`` can resolve
        # the allowed alias (``glm``) back to its canonical target (``glm-4.6``).
        ModelProviderRegistry.register_provider(ProviderType.ZAI, ZAIModelProvider)

        provider = ZAIModelProvider("test-key")
        assert provider.validate_model_name("glm-4.6") is True
        assert provider.validate_model_name("glm") is True

    @patch.dict(os.environ, {"ZAI_ALLOWED_MODELS": "glm,glm-4,glm-4.6,glm4.6"})
    def test_both_shorthand_and_full_name_allowed(self):
        """Test that aliases and canonical names can be allowed together."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = ZAIModelProvider("test-key")

        assert provider.validate_model_name("glm") is True
        assert provider.validate_model_name("glm-4") is True
        assert provider.validate_model_name("glm-4.6") is True
        assert provider.validate_model_name("glm4.6") is True

    @patch.dict(os.environ, {"ZAI_ALLOWED_MODELS": ""})
    def test_empty_restrictions_allows_all(self):
        """Test that empty restrictions allow all models."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = ZAIModelProvider("test-key")

        assert provider.validate_model_name("glm-4.6") is True
        assert provider.validate_model_name("glm") is True
        assert provider.validate_model_name("glm-4") is True
        assert provider.validate_model_name("glm4.6") is True

    @patch("providers.openai_compatible.OpenAI")
    @pytest.mark.parametrize(
        ("thinking_mode", "expected_type"),
        [
            ("minimal", "disabled"),
            ("high", "enabled"),
        ],
    )
    def test_generate_content_forwards_thinking_mode(self, mock_openai_class, thinking_mode, expected_type):
        """Z.AI thinking modes must be forwarded through the OpenAI SDK body."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "glm-4.6"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = ZAIModelProvider("test-key")

        provider.generate_content(
            prompt="Test prompt",
            model_name="glm-4.6",
            thinking_mode=thinking_mode,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"thinking": {"type": expected_type}}

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_preserves_custom_extra_body(self, mock_openai_class):
        """Caller-provided Z.AI extra body fields should be preserved."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "glm-4.6"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = ZAIModelProvider("test-key")

        provider.generate_content(
            prompt="Test prompt",
            model_name="glm-4.6",
            thinking_mode="high",
            extra_body={"custom": True},
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"custom": True, "thinking": {"type": "enabled"}}

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_clamps_temperature_to_zai_api_range(self, mock_openai_class):
        """Z.AI API rejects temperatures above 1.0, so clamp before sending."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "glm-4.6"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = ZAIModelProvider("test-key")

        provider.generate_content(
            prompt="Test prompt",
            model_name="glm-4.6",
            temperature=1.5,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 1.0

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_resolves_alias_before_api_call(self, mock_openai_class):
        """Test that generate_content resolves aliases before making API calls.

        This is the CRITICAL test that ensures aliases like 'glm' get resolved
        to 'glm-4.6' before being sent to Z.AI API.
        """
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "glm-4.6"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        provider = ZAIModelProvider("test-key")

        result = provider.generate_content(
            prompt="Test prompt",
            model_name="glm",  # This should be resolved to "glm-4.6"
            temperature=0.7,
        )

        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # CRITICAL ASSERTION: The API should receive "glm-4.6", not "glm"
        assert call_kwargs["model"] == "glm-4.6", f"Expected 'glm-4.6' but API received '{call_kwargs['model']}'"

        assert call_kwargs["temperature"] == 0.7
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert call_kwargs["messages"][0]["content"] == "Test prompt"

        assert result.content == "Test response"
        assert result.model_name == "glm-4.6"

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_other_aliases(self, mock_openai_class):
        """Test other alias resolutions in generate_content."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "glm-4.6"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = ZAIModelProvider("test-key")

        # Test glm-4 -> glm-4.6
        provider.generate_content(prompt="Test", model_name="glm-4", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "glm-4.6"

        # Test glm4.6 -> glm-4.6
        provider.generate_content(prompt="Test", model_name="glm4.6", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "glm-4.6"

        # Test glm-4.6 -> glm-4.6 (passthrough)
        provider.generate_content(prompt="Test", model_name="glm-4.6", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "glm-4.6"
