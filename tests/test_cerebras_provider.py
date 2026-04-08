"""Tests for Cerebras provider implementation."""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers.cerebras import CerebrasModelProvider
from providers.shared import ProviderType


class TestCerebrasProvider:
    """Test Cerebras provider functionality."""

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

    @patch.dict(os.environ, {"CEREBRAS_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        provider = CerebrasModelProvider("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.CEREBRAS
        assert provider.base_url == "https://api.cerebras.ai/v1"

    def test_initialization_with_custom_url(self):
        """Test provider initialization with custom base URL."""
        provider = CerebrasModelProvider("test-key", base_url="https://custom.cerebras.ai/v1")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.cerebras.ai/v1"

    def test_model_validation(self):
        """Test model name validation."""
        provider = CerebrasModelProvider("test-key")

        # Test valid models
        assert provider.validate_model_name("zai-glm-4.7") is True
        assert provider.validate_model_name("cerebras") is True
        assert provider.validate_model_name("glm") is True
        assert provider.validate_model_name("glm-4.7") is True
        assert provider.validate_model_name("zai") is True
        assert provider.validate_model_name("zai-glm") is True

        # Test invalid model
        assert provider.validate_model_name("invalid-model") is False
        assert provider.validate_model_name("gpt-4") is False
        assert provider.validate_model_name("gemini-pro") is False
        assert provider.validate_model_name("grok-4") is False

    def test_resolve_model_name(self):
        """Test model name resolution."""
        provider = CerebrasModelProvider("test-key")

        # Test shorthand resolution
        assert provider._resolve_model_name("cerebras") == "zai-glm-4.7"
        assert provider._resolve_model_name("glm") == "zai-glm-4.7"
        assert provider._resolve_model_name("glm-4.7") == "zai-glm-4.7"
        assert provider._resolve_model_name("zai") == "zai-glm-4.7"
        assert provider._resolve_model_name("zai-glm") == "zai-glm-4.7"

        # Test full name passthrough
        assert provider._resolve_model_name("zai-glm-4.7") == "zai-glm-4.7"

    def test_get_capabilities(self):
        """Test getting model capabilities for zai-glm-4.7."""
        provider = CerebrasModelProvider("test-key")

        capabilities = provider.get_capabilities("zai-glm-4.7")
        assert capabilities.model_name == "zai-glm-4.7"
        assert capabilities.friendly_name == "Cerebras (zai-glm-4.7)"
        assert capabilities.context_window == 131072
        assert capabilities.max_output_tokens == 40000
        assert capabilities.provider == ProviderType.CEREBRAS
        assert capabilities.supports_extended_thinking is False
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_json_mode is True
        assert capabilities.supports_images is False
        assert capabilities.supports_temperature is True

        # Test temperature range (default range constraint from registry)
        assert capabilities.temperature_constraint.min_temp == 0.0
        assert capabilities.temperature_constraint.max_temp == 2.0
        assert capabilities.temperature_constraint.default_temp == 0.3

    def test_get_capabilities_with_shorthand(self):
        """Test getting model capabilities with shorthand."""
        provider = CerebrasModelProvider("test-key")

        capabilities = provider.get_capabilities("cerebras")
        assert capabilities.model_name == "zai-glm-4.7"  # Should resolve to full name
        assert capabilities.context_window == 131072

        capabilities_glm = provider.get_capabilities("glm")
        assert capabilities_glm.model_name == "zai-glm-4.7"

    def test_unsupported_model_capabilities(self):
        """Test error handling for unsupported models."""
        provider = CerebrasModelProvider("test-key")

        with pytest.raises(ValueError, match="Unsupported model 'invalid-model' for provider cerebras"):
            provider.get_capabilities("invalid-model")

    def test_extended_thinking_flags(self):
        """Cerebras does not support extended thinking (no reasoning-token protocol)."""
        provider = CerebrasModelProvider("test-key")

        all_aliases = [
            "zai-glm-4.7",
            "cerebras",
            "glm",
            "glm-4.7",
            "zai",
            "zai-glm",
        ]
        for alias in all_aliases:
            assert provider.get_capabilities(alias).supports_extended_thinking is False

    def test_provider_type(self):
        """Test provider type identification."""
        provider = CerebrasModelProvider("test-key")
        assert provider.get_provider_type() == ProviderType.CEREBRAS

    @patch.dict(os.environ, {"CEREBRAS_ALLOWED_MODELS": "zai-glm-4.7"})
    def test_model_restrictions(self):
        """Test that CEREBRAS_ALLOWED_MODELS env var is wired into the restriction service."""
        # Clear cached restriction service
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()

        provider = CerebrasModelProvider("test-key")

        # zai-glm-4.7 should be allowed (including alias)
        assert provider.validate_model_name("zai-glm-4.7") is True
        assert provider.validate_model_name("cerebras") is True

        # Paid-tier models must be REJECTED when only zai-glm-4.7 is allowed.
        # This catches the bug where CEREBRAS was missing from
        # ModelRestrictionService.ENV_VARS and the env var was silently ignored.
        assert provider.validate_model_name("gpt-oss-120b") is False
        assert provider.validate_model_name("gpt-oss") is False
        assert provider.validate_model_name("qwen-3-235b-a22b-instruct-2507") is False
        assert provider.validate_model_name("qwen3") is False
        assert provider.validate_model_name("llama3.1-8b") is False
        assert provider.validate_model_name("llama8b") is False

    @patch.dict(os.environ, {"CEREBRAS_API_KEY": "test-key", "CEREBRAS_ALLOWED_MODELS": "zai-glm-4.7"})
    def test_restrictions_filter_auto_mode_routing(self):
        """Auto-mode routing must respect CEREBRAS_ALLOWED_MODELS via the registry filter.

        Regression test for the missing ENV_VARS wiring: the provider's
        get_preferred_model() expects the registry to pre-filter allowed_models,
        so the centralized restriction service must know about CEREBRAS.
        """
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()
        ModelProviderRegistry.register_provider(ProviderType.CEREBRAS, CerebrasModelProvider)

        provider = ModelProviderRegistry.get_provider(ProviderType.CEREBRAS)
        assert provider is not None

        # The registry's allowlist filter must return only zai-glm-4.7.
        allowed = ModelProviderRegistry._get_allowed_models_for_provider(provider, ProviderType.CEREBRAS)
        assert allowed == ["zai-glm-4.7"], f"Expected only zai-glm-4.7, got {allowed}"

        # And category routing must therefore always return zai-glm-4.7,
        # not gpt-oss-120b or llama3.1-8b — even for EXTENDED_REASONING/FAST_RESPONSE
        # whose preference lists would otherwise pick those paid-tier models first.
        from tools.models import ToolModelCategory

        for cat in (
            ToolModelCategory.BALANCED,
            ToolModelCategory.EXTENDED_REASONING,
            ToolModelCategory.FAST_RESPONSE,
        ):
            assert provider.get_preferred_model(cat, allowed) == "zai-glm-4.7"

    @patch.dict(os.environ, {"CEREBRAS_API_KEY": "test-key", "CEREBRAS_ALLOWED_MODELS": "cerebras"})
    def test_multiple_model_restrictions(self):
        """Restrictions specified via alias must accept the canonical name too."""
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry

        utils.model_restrictions._restriction_service = None
        ModelProviderRegistry.reset_for_testing()
        # Provider must be registered so the restriction service can resolve
        # the "cerebras" alias to its canonical name during validation.
        ModelProviderRegistry.register_provider(ProviderType.CEREBRAS, CerebrasModelProvider)
        provider = ModelProviderRegistry.get_provider(ProviderType.CEREBRAS)

        # Alias should be allowed (resolves to zai-glm-4.7)
        assert provider.validate_model_name("cerebras") is True
        assert provider.validate_model_name("zai-glm-4.7") is True
        # And paid-tier models must still be rejected
        assert provider.validate_model_name("gpt-oss-120b") is False
        assert provider.validate_model_name("llama3.1-8b") is False

    @patch.dict(os.environ, {"CEREBRAS_ALLOWED_MODELS": "zai-glm-4.7,cerebras,glm"})
    def test_both_shorthand_and_full_name_allowed(self):
        """Test that aliases and canonical names can be allowed together."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = CerebrasModelProvider("test-key")

        # Both shorthand and full name should be allowed when explicitly listed
        assert provider.validate_model_name("zai-glm-4.7") is True
        assert provider.validate_model_name("cerebras") is True
        assert provider.validate_model_name("glm") is True

    @patch.dict(os.environ, {"CEREBRAS_ALLOWED_MODELS": ""})
    def test_empty_restrictions_allows_all(self):
        """Test that empty restrictions allow all models."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = CerebrasModelProvider("test-key")

        assert provider.validate_model_name("zai-glm-4.7") is True
        assert provider.validate_model_name("cerebras") is True
        assert provider.validate_model_name("glm") is True

    def test_friendly_name(self):
        """Test friendly name constant."""
        provider = CerebrasModelProvider("test-key")
        assert provider.FRIENDLY_NAME == "Cerebras"

        capabilities = provider.get_capabilities("zai-glm-4.7")
        assert capabilities.friendly_name == "Cerebras (zai-glm-4.7)"

    def test_supported_models_structure(self):
        """Test that MODEL_CAPABILITIES has all four models with correct structure."""
        provider = CerebrasModelProvider("test-key")

        from providers.shared import ModelCapabilities

        expected_models = {
            "gpt-oss-120b": {"context_window": 131072, "max_output_tokens": 40000, "intelligence_score": 17},
            "qwen-3-235b-a22b-instruct-2507": {
                "context_window": 131072,
                "max_output_tokens": 40000,
                "intelligence_score": 16,
            },
            "zai-glm-4.7": {"context_window": 131072, "max_output_tokens": 40000, "intelligence_score": 14},
            "llama3.1-8b": {"context_window": 32768, "max_output_tokens": 8192, "intelligence_score": 9},
        }
        for model_name, expected in expected_models.items():
            assert model_name in provider.MODEL_CAPABILITIES, f"{model_name} missing from MODEL_CAPABILITIES"
            config = provider.MODEL_CAPABILITIES[model_name]
            assert isinstance(config, ModelCapabilities)
            assert config.context_window == expected["context_window"], f"{model_name} context_window mismatch"
            assert config.max_output_tokens == expected["max_output_tokens"], f"{model_name} max_output_tokens mismatch"
            assert config.supports_extended_thinking is False, f"{model_name} should not claim extended thinking"

        # Spot-check aliases
        assert "cerebras" in provider.MODEL_CAPABILITIES["zai-glm-4.7"].aliases
        assert "gpt-oss" in provider.MODEL_CAPABILITIES["gpt-oss-120b"].aliases
        assert "qwen3" in provider.MODEL_CAPABILITIES["qwen-3-235b-a22b-instruct-2507"].aliases
        assert "llama8b" in provider.MODEL_CAPABILITIES["llama3.1-8b"].aliases

    def test_new_model_capabilities_gpt_oss(self):
        """Test gpt-oss-120b capabilities and alias resolution."""
        provider = CerebrasModelProvider("test-key")

        for alias in ("gpt-oss-120b", "gpt-oss", "oss-120b", "openai-oss"):
            caps = provider.get_capabilities(alias)
            assert caps.model_name == "gpt-oss-120b"
            assert caps.context_window == 131072
            assert caps.max_output_tokens == 40000
            assert caps.supports_function_calling is True
            assert caps.supports_extended_thinking is False

    def test_new_model_capabilities_qwen3(self):
        """Test qwen-3-235b capabilities and alias resolution."""
        provider = CerebrasModelProvider("test-key")

        for alias in ("qwen-3-235b-a22b-instruct-2507", "qwen3", "qwen-3", "qwen235b", "qwen3-235b"):
            caps = provider.get_capabilities(alias)
            assert caps.model_name == "qwen-3-235b-a22b-instruct-2507"
            assert caps.context_window == 131072
            assert caps.max_output_tokens == 40000
            assert caps.supports_function_calling is True
            assert caps.supports_extended_thinking is False

    def test_new_model_capabilities_llama(self):
        """Test llama3.1-8b capabilities and alias resolution."""
        provider = CerebrasModelProvider("test-key")

        for alias in ("llama3.1-8b", "llama8b", "llama-8b", "llama3.1", "llama3-8b"):
            caps = provider.get_capabilities(alias)
            assert caps.model_name == "llama3.1-8b"
            assert caps.context_window == 32768
            assert caps.max_output_tokens == 8192
            assert caps.supports_function_calling is True
            assert caps.supports_extended_thinking is False

    def test_get_preferred_model_routing(self):
        """Test category-based model routing across all four models."""
        from tools.models import ToolModelCategory

        provider = CerebrasModelProvider("test-key")
        all_models = ["gpt-oss-120b", "qwen-3-235b-a22b-instruct-2507", "zai-glm-4.7", "llama3.1-8b"]

        # BALANCED → zai-glm-4.7 (default; only model on Cerebras Code plan)
        assert provider.get_preferred_model(ToolModelCategory.BALANCED, all_models) == "zai-glm-4.7"

        # EXTENDED_REASONING → gpt-oss-120b (strongest reasoner; paid tier)
        assert provider.get_preferred_model(ToolModelCategory.EXTENDED_REASONING, all_models) == "gpt-oss-120b"

        # FAST_RESPONSE → llama3.1-8b (fastest small model; paid tier)
        assert provider.get_preferred_model(ToolModelCategory.FAST_RESPONSE, all_models) == "llama3.1-8b"

    def test_get_preferred_model_fallback(self):
        """Test category routing falls back gracefully when top choice unavailable."""
        from tools.models import ToolModelCategory

        provider = CerebrasModelProvider("test-key")

        # Code plan (zai-glm-4.7 only) → always returns zai-glm-4.7 for any category
        for cat in [ToolModelCategory.BALANCED, ToolModelCategory.EXTENDED_REASONING, ToolModelCategory.FAST_RESPONSE]:
            assert provider.get_preferred_model(cat, ["zai-glm-4.7"]) == "zai-glm-4.7"

        # Without gpt-oss-120b, EXTENDED_REASONING falls back to qwen3
        assert (
            provider.get_preferred_model(
                ToolModelCategory.EXTENDED_REASONING,
                ["qwen-3-235b-a22b-instruct-2507", "zai-glm-4.7"],
            )
            == "qwen-3-235b-a22b-instruct-2507"
        )

        # Without llama3.1-8b, FAST_RESPONSE falls back to zai-glm-4.7
        assert (
            provider.get_preferred_model(
                ToolModelCategory.FAST_RESPONSE,
                ["zai-glm-4.7", "gpt-oss-120b"],
            )
            == "zai-glm-4.7"
        )

        # Empty list → None
        assert provider.get_preferred_model(ToolModelCategory.BALANCED, []) is None

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_resolves_alias_before_api_call(self, mock_openai_class):
        """Test that generate_content resolves aliases before making API calls.

        This is the CRITICAL test that ensures aliases like 'cerebras' get resolved
        to 'zai-glm-4.7' before being sent to Cerebras API.
        """
        # Set up mock OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock the completion response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "zai-glm-4.7"  # API returns the resolved model name
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        provider = CerebrasModelProvider("test-key")

        # Call generate_content with alias 'cerebras'
        result = provider.generate_content(
            prompt="Test prompt",
            model_name="cerebras",
            temperature=0.7,  # This should be resolved to "zai-glm-4.7"
        )

        # Verify the API was called with the RESOLVED model name
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # CRITICAL ASSERTION: The API should receive "zai-glm-4.7", not "cerebras"
        assert (
            call_kwargs["model"] == "zai-glm-4.7"
        ), f"Expected 'zai-glm-4.7' but API received '{call_kwargs['model']}'"

        # Verify other parameters
        assert call_kwargs["temperature"] == 0.7
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert call_kwargs["messages"][0]["content"] == "Test prompt"

        # Verify response
        assert result.content == "Test response"
        assert result.model_name == "zai-glm-4.7"  # Should be the resolved name

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_other_aliases(self, mock_openai_class):
        """Test other alias resolutions in generate_content."""
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

        provider = CerebrasModelProvider("test-key")

        # Test glm -> zai-glm-4.7
        mock_response.model = "zai-glm-4.7"
        provider.generate_content(prompt="Test", model_name="glm", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "zai-glm-4.7"

        # Test glm-4.7 -> zai-glm-4.7
        provider.generate_content(prompt="Test", model_name="glm-4.7", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "zai-glm-4.7"

        # Test zai -> zai-glm-4.7
        provider.generate_content(prompt="Test", model_name="zai", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "zai-glm-4.7"

        # Test zai-glm -> zai-glm-4.7
        provider.generate_content(prompt="Test", model_name="zai-glm", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "zai-glm-4.7"

        # Test zai-glm-4.7 -> zai-glm-4.7 (passthrough)
        provider.generate_content(prompt="Test", model_name="zai-glm-4.7", temperature=0.7)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "zai-glm-4.7"
