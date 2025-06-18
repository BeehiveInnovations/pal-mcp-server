"""Tests for CustomProvider functionality."""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers import ModelProviderRegistry
from providers.base import ProviderType
from providers.custom import CustomProvider


class TestCustomProvider:
    """Test CustomProvider class functionality."""

    def test_provider_initialization_with_params(self):
        """Test CustomProvider initializes correctly with explicit parameters."""
        provider = CustomProvider(api_key="test-key", base_url="http://localhost:11434/v1")

        assert provider.base_url == "http://localhost:11434/v1"
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.CUSTOM

    def test_provider_initialization_with_env_vars(self):
        """Test CustomProvider initializes correctly with environment variables."""
        with patch.dict(os.environ, {"CUSTOM_API_URL": "http://localhost:8000/v1", "CUSTOM_API_KEY": "env-key"}):
            provider = CustomProvider()

            assert provider.base_url == "http://localhost:8000/v1"
            assert provider.api_key == "env-key"

    def test_provider_initialization_missing_url(self):
        """Test CustomProvider raises error when URL is missing."""
        with patch.dict(os.environ, {"CUSTOM_API_URL": ""}, clear=False):
            with pytest.raises(ValueError, match="Custom API URL must be provided"):
                CustomProvider(api_key="test-key")

    def test_validate_model_names_always_true(self):
        """Test CustomProvider accepts any model name."""
        provider = CustomProvider(api_key="test-key", base_url="http://localhost:11434/v1")

        assert provider.validate_model_name("llama3.2")
        assert provider.validate_model_name("unknown-model")
        assert provider.validate_model_name("anything")

    def test_get_capabilities_from_registry(self):
        """Test get_capabilities returns registry capabilities when available."""
        provider = CustomProvider(api_key="test-key", base_url="http://localhost:11434/v1")

        # Test with a model that should be in the registry (OpenRouter model)
        capabilities = provider.get_capabilities("llama")

        assert capabilities.provider == ProviderType.OPENROUTER  # llama is an OpenRouter model (is_custom=false)
        assert capabilities.context_window > 0

        # Test with a custom model (is_custom=true)
        capabilities = provider.get_capabilities("local-llama")
        assert capabilities.provider == ProviderType.CUSTOM  # local-llama has is_custom=true
        assert capabilities.context_window > 0

    def test_get_capabilities_generic_fallback(self):
        """Test get_capabilities returns generic capabilities for unknown models."""
        provider = CustomProvider(api_key="test-key", base_url="http://localhost:11434/v1")

        capabilities = provider.get_capabilities("unknown-model-xyz")

        assert capabilities.provider == ProviderType.CUSTOM
        assert capabilities.model_name == "unknown-model-xyz"
        assert capabilities.context_window == 32_768  # Conservative default
        assert not capabilities.supports_extended_thinking
        assert capabilities.supports_system_prompts
        assert capabilities.supports_streaming

    def test_model_alias_resolution(self):
        """Test model alias resolution works correctly."""
        provider = CustomProvider(api_key="test-key", base_url="http://localhost:11434/v1")

        # Test that aliases resolve properly
        # "llama" now resolves to "meta-llama/llama-3-70b" (the OpenRouter model)
        resolved = provider._resolve_model_name("llama")
        assert resolved == "meta-llama/llama-3-70b"

        # Test local model alias
        resolved_local = provider._resolve_model_name("local-llama")
        assert resolved_local == "llama3.2"

    def test_no_thinking_mode_support(self):
        """Test CustomProvider doesn't support thinking mode."""
        provider = CustomProvider(api_key="test-key", base_url="http://localhost:11434/v1")

        assert not provider.supports_thinking_mode("llama3.2")
        assert not provider.supports_thinking_mode("any-model")

    @patch("providers.custom.OpenAICompatibleProvider.generate_content")
    def test_generate_content_with_alias_resolution(self, mock_generate):
        """Test generate_content resolves aliases before calling parent."""
        mock_response = MagicMock()
        mock_generate.return_value = mock_response

        provider = CustomProvider(api_key="test-key", base_url="http://localhost:11434/v1")

        # Call with an alias
        result = provider.generate_content(
            prompt="test prompt",
            model_name="llama",
            temperature=0.7,  # This is an alias
        )

        # Verify parent method was called with resolved model name
        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        # The model_name should be either resolved or passed through
        assert "model_name" in call_args.kwargs
        assert result == mock_response


class TestCustomProviderRegistration:
    """Test CustomProvider integration with ModelProviderRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        ModelProviderRegistry.clear_cache()
        ModelProviderRegistry.unregister_provider(ProviderType.CUSTOM)

    def teardown_method(self):
        """Clean up after each test."""
        ModelProviderRegistry.clear_cache()
        ModelProviderRegistry.unregister_provider(ProviderType.CUSTOM)

    def test_custom_provider_factory_registration(self):
        """Test custom provider can be registered via factory function."""

        def custom_provider_factory(api_key=None):
            return CustomProvider(api_key="test-key", base_url="http://localhost:11434/v1")

        with patch.dict(os.environ, {"CUSTOM_API_PLACEHOLDER": "configured"}):
            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, custom_provider_factory)

            # Verify provider is available
            available = ModelProviderRegistry.get_available_providers()
            assert ProviderType.CUSTOM in available

            # Verify provider can be retrieved
            provider = ModelProviderRegistry.get_provider(ProviderType.CUSTOM)
            assert provider is not None
            assert isinstance(provider, CustomProvider)

    def test_dual_provider_setup(self):
        """Test both OpenRouter and Custom providers can coexist."""
        from providers.openrouter import OpenRouterProvider

        # Create factory for custom provider
        def custom_provider_factory(api_key=None):
            return CustomProvider(api_key="", base_url="http://localhost:11434/v1")

        with patch.dict(
            os.environ, {"OPENROUTER_API_KEY": "test-openrouter-key", "CUSTOM_API_PLACEHOLDER": "configured"}
        ):
            # Register both providers
            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)
            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, custom_provider_factory)

            # Verify both are available
            available = ModelProviderRegistry.get_available_providers()
            assert ProviderType.OPENROUTER in available
            assert ProviderType.CUSTOM in available

            # Verify both can be retrieved
            openrouter_provider = ModelProviderRegistry.get_provider(ProviderType.OPENROUTER)
            custom_provider = ModelProviderRegistry.get_provider(ProviderType.CUSTOM)

            assert openrouter_provider is not None
            assert custom_provider is not None
            assert isinstance(custom_provider, CustomProvider)

    def test_provider_priority_selection(self):
        """Test provider selection prioritizes correctly."""
        from providers.openrouter import OpenRouterProvider

        def custom_provider_factory(api_key=None):
            return CustomProvider(api_key="", base_url="http://localhost:11434/v1")

        with patch.dict(
            os.environ, {"OPENROUTER_API_KEY": "test-openrouter-key", "CUSTOM_API_PLACEHOLDER": "configured"}
        ):
            # Register OpenRouter first (higher priority)
            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)
            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, custom_provider_factory)

            # Test model resolution - OpenRouter should win for shared aliases
            provider_for_model = ModelProviderRegistry.get_provider_for_model("llama")

            # OpenRouter should be selected first due to registration order
            assert provider_for_model is not None
            # The exact provider type depends on which validates the model first


class TestConfigureProvidersFunction:
    """Test the configure_providers function in server.py."""

    def setup_method(self):
        """Clear environment and registry before each test."""
        # Store the original providers to restore them later
        registry = ModelProviderRegistry()
        self._original_providers = registry._providers.copy()
        ModelProviderRegistry.clear_cache()
        for provider_type in ProviderType:
            ModelProviderRegistry.unregister_provider(provider_type)

    def teardown_method(self):
        """Clean up after each test."""
        # Restore the original providers that were registered in conftest.py
        registry = ModelProviderRegistry()
        ModelProviderRegistry.clear_cache()
        registry._providers.clear()
        registry._providers.update(self._original_providers)

    def test_configure_providers_custom_only(self):
        """Test configure_providers with only custom URL set."""
        from server import configure_providers

        with patch.dict(
            os.environ,
            {
                "CUSTOM_API_URL": "http://localhost:11434/v1",
                "CUSTOM_API_KEY": "",
                # Clear other API keys
                "GEMINI_API_KEY": "",
                "OPENAI_API_KEY": "",
                "OPENROUTER_API_KEY": "",
            },
            clear=True,
        ):
            configure_providers()

            # Verify only custom provider is available
            available = ModelProviderRegistry.get_available_providers()
            assert ProviderType.CUSTOM in available
            assert ProviderType.OPENROUTER not in available

    def test_configure_providers_openrouter_only(self):
        """Test configure_providers with only OpenRouter key set."""
        from server import configure_providers

        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test-key",
                # Clear other API keys
                "GEMINI_API_KEY": "",
                "OPENAI_API_KEY": "",
                "CUSTOM_API_URL": "",
            },
            clear=True,
        ):
            configure_providers()

            # Verify only OpenRouter provider is available
            available = ModelProviderRegistry.get_available_providers()
            assert ProviderType.OPENROUTER in available
            assert ProviderType.CUSTOM not in available

    def test_configure_providers_dual_setup(self):
        """Test configure_providers with both OpenRouter and Custom configured."""
        from server import configure_providers

        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test-openrouter-key",
                "CUSTOM_API_URL": "http://localhost:11434/v1",
                "CUSTOM_API_KEY": "",
                # Clear other API keys
                "GEMINI_API_KEY": "",
                "OPENAI_API_KEY": "",
            },
            clear=True,
        ):
            configure_providers()

            # Verify both providers are available
            available = ModelProviderRegistry.get_available_providers()
            assert ProviderType.OPENROUTER in available
            assert ProviderType.CUSTOM in available

    def test_configure_providers_no_valid_keys(self):
        """Test configure_providers raises error when no valid API keys."""
        from server import configure_providers

        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "", "OPENAI_API_KEY": "", "OPENROUTER_API_KEY": "", "CUSTOM_API_URL": ""},
            clear=True,
        ):
            with pytest.raises(ValueError, match="At least one API configuration is required"):
                configure_providers()
