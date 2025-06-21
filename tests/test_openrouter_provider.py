"""Tests for OpenRouter provider."""

import os
from unittest.mock import Mock, patch

import pytest

from providers.base import ProviderType
from providers.openrouter import OpenRouterProvider
from providers.registry import ModelProviderRegistry


class TestOpenRouterProvider:
    """Test cases for OpenRouter provider."""

    def test_provider_initialization(self):
        """Test OpenRouter provider initialization."""
        provider = OpenRouterProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://openrouter.ai/api/v1"
        assert provider.FRIENDLY_NAME == "OpenRouter"

    def test_custom_headers(self):
        """Test OpenRouter custom headers."""
        # Test default headers
        assert "HTTP-Referer" in OpenRouterProvider.DEFAULT_HEADERS
        assert "X-Title" in OpenRouterProvider.DEFAULT_HEADERS

        # Test with environment variables
        with patch.dict(os.environ, {"OPENROUTER_REFERER": "https://myapp.com", "OPENROUTER_TITLE": "My App"}):
            from importlib import reload

            import providers.openrouter

            reload(providers.openrouter)

            provider = providers.openrouter.OpenRouterProvider(api_key="test-key")
            assert provider.DEFAULT_HEADERS["HTTP-Referer"] == "https://myapp.com"
            assert provider.DEFAULT_HEADERS["X-Title"] == "My App"

    def test_model_validation(self):
        """Test model validation."""
        provider = OpenRouterProvider(api_key="test-key")

        # Should accept any model - OpenRouter handles validation
        assert provider.validate_model_name("gpt-4") is True
        assert provider.validate_model_name("claude-3-opus") is True
        assert provider.validate_model_name("any-model-name") is True
        assert provider.validate_model_name("GPT-4") is True
        assert provider.validate_model_name("unknown-model") is True

    def test_get_capabilities(self):
        """Test capability generation."""
        provider = OpenRouterProvider(api_key="test-key")

        # Test with a model in the registry (using alias)
        caps = provider.get_capabilities("o3")
        assert caps.provider == ProviderType.OPENROUTER
        assert caps.model_name == "openai/o3"  # Resolved name
        assert caps.friendly_name == "OpenRouter"

        # Test with a model not in registry - should get generic capabilities
        caps = provider.get_capabilities("unknown-model")
        assert caps.provider == ProviderType.OPENROUTER
        assert caps.model_name == "unknown-model"
        assert caps.context_window == 32_768  # Safe default
        assert hasattr(caps, "_is_generic") and caps._is_generic is True

    def test_model_alias_resolution(self):
        """Test model alias resolution."""
        provider = OpenRouterProvider(api_key="test-key")

        # Test alias resolution
        assert provider._resolve_model_name("opus") == "anthropic/claude-3-opus"
        assert provider._resolve_model_name("sonnet") == "anthropic/claude-3-sonnet"
        assert provider._resolve_model_name("o3") == "openai/o3"
        assert provider._resolve_model_name("o3-mini") == "openai/o3-mini"
        assert provider._resolve_model_name("o3mini") == "openai/o3-mini"
        assert provider._resolve_model_name("o4-mini") == "openai/o4-mini"
        assert provider._resolve_model_name("o4-mini-high") == "openai/o4-mini-high"
        assert provider._resolve_model_name("claude") == "anthropic/claude-3-sonnet"
        assert provider._resolve_model_name("mistral") == "mistral/mistral-large"
        assert provider._resolve_model_name("deepseek") == "deepseek/deepseek-r1-0528"
        assert provider._resolve_model_name("r1") == "deepseek/deepseek-r1-0528"

        # Test case-insensitive
        assert provider._resolve_model_name("OPUS") == "anthropic/claude-3-opus"
        assert provider._resolve_model_name("O3") == "openai/o3"
        assert provider._resolve_model_name("Mistral") == "mistral/mistral-large"
        assert provider._resolve_model_name("CLAUDE") == "anthropic/claude-3-sonnet"

        # Test direct model names (should pass through unchanged)
        assert provider._resolve_model_name("anthropic/claude-3-opus") == "anthropic/claude-3-opus"
        assert provider._resolve_model_name("openai/o3") == "openai/o3"

        # Test unknown models pass through
        assert provider._resolve_model_name("unknown-model") == "unknown-model"
        assert provider._resolve_model_name("custom/model-v2") == "custom/model-v2"

    def test_openrouter_registration(self):
        """Test OpenRouter can be registered and retrieved."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            # Clean up any existing registration
            ModelProviderRegistry.unregister_provider(ProviderType.OPENROUTER)

            # Register the provider
            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

            # Retrieve and verify
            provider = ModelProviderRegistry.get_provider(ProviderType.OPENROUTER)
            assert provider is not None
            assert isinstance(provider, OpenRouterProvider)


class TestOpenRouterAutoMode:
    """Test auto mode functionality when only OpenRouter is configured."""

    def setup_method(self):
        """Store original state before each test."""
        self.registry = ModelProviderRegistry()
        self._original_providers = self.registry._providers.copy()
        self._original_initialized = self.registry._initialized_providers.copy()

        self.registry._providers.clear()
        self.registry._initialized_providers.clear()

        self._original_env = {}
        for key in ["OPENROUTER_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "DEFAULT_MODEL"]:
            self._original_env[key] = os.environ.get(key)

    def teardown_method(self):
        """Restore original state after each test."""
        self.registry._providers.clear()
        self.registry._initialized_providers.clear()
        self.registry._providers.update(self._original_providers)
        self.registry._initialized_providers.update(self._original_initialized)

        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    @pytest.mark.no_mock_provider
    def test_openrouter_only_auto_mode(self):
        """Test that auto mode works when only OpenRouter is configured."""
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"
        os.environ["DEFAULT_MODEL"] = "auto"

        mock_registry = Mock()
        mock_registry.list_models.return_value = [
            "google/gemini-2.5-flash",
            "google/gemini-2.5-pro",
            "openai/o3",
            "openai/o3-mini",
            "anthropic/claude-3-opus",
            "anthropic/claude-3-sonnet",
        ]

        ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

        provider = ModelProviderRegistry.get_provider(ProviderType.OPENROUTER)
        assert provider is not None, "OpenRouter provider should be available with API key"
        provider._registry = mock_registry

        available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

        assert len(available_models) > 0, "Should find OpenRouter models in auto mode"
        assert all(provider_type == ProviderType.OPENROUTER for provider_type in available_models.values())

        expected_models = mock_registry.list_models.return_value
        for model in expected_models:
            assert model in available_models, f"Model {model} should be available"

    @pytest.mark.no_mock_provider
    def test_openrouter_with_restrictions(self):
        """Test that OpenRouter respects model restrictions."""
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"
        os.environ.pop("OPENROUTER_ALLOWED_MODELS", None)
        os.environ["OPENROUTER_ALLOWED_MODELS"] = "anthropic/claude-3-opus,google/gemini-2.5-flash"
        os.environ["DEFAULT_MODEL"] = "auto"

        # Force reload to pick up new environment variable
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        mock_registry = Mock()
        mock_models = [
            "google/gemini-2.5-flash",
            "google/gemini-2.5-pro",
            "anthropic/claude-3-opus",
            "anthropic/claude-3-sonnet",
        ]
        mock_registry.list_models.return_value = mock_models

        # Mock the resolve method to return model configs with aliases
        mock_model_config = Mock()
        mock_model_config.aliases = []  # Empty aliases for simplicity
        mock_registry.resolve.return_value = mock_model_config

        ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

        provider = ModelProviderRegistry.get_provider(ProviderType.OPENROUTER)
        provider._registry = mock_registry

        available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

        assert len(available_models) > 0, "Should have some allowed models"

        expected_allowed = {"google/gemini-2.5-flash", "anthropic/claude-3-opus"}

        assert (
            set(available_models.keys()) == expected_allowed
        ), f"Expected {expected_allowed}, but got {set(available_models.keys())}"

    @pytest.mark.no_mock_provider
    def test_no_providers_fails_auto_mode(self):
        """Test that auto mode fails gracefully when no providers are available."""
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ["DEFAULT_MODEL"] = "auto"

        available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

        assert len(available_models) == 0, "Should have no models when no providers are configured"

    @pytest.mark.no_mock_provider
    def test_openrouter_without_registry(self):
        """Test that OpenRouter without _registry attribute doesn't crash."""
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"
        os.environ["DEFAULT_MODEL"] = "auto"

        mock_provider_class = Mock()
        mock_provider_instance = Mock(spec=["get_provider_type", "list_models"])
        mock_provider_instance.get_provider_type.return_value = ProviderType.OPENROUTER
        mock_provider_instance.list_models.return_value = []
        mock_provider_class.return_value = mock_provider_instance

        ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, mock_provider_class)

        available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

        assert len(available_models) == 0, "Should have no models when OpenRouter has no registry"


class TestOpenRouterRegistry:
    """Test cases for OpenRouter model registry."""

    def test_registry_loading(self):
        """Test registry loads models from config."""
        from providers.openrouter_registry import OpenRouterModelRegistry

        registry = OpenRouterModelRegistry()

        # Should have loaded models
        models = registry.list_models()
        assert len(models) > 0
        assert "anthropic/claude-3-opus" in models
        assert "openai/o3" in models

        # Should have loaded aliases
        aliases = registry.list_aliases()
        assert len(aliases) > 0
        assert "opus" in aliases
        assert "o3" in aliases
        assert "claude" in aliases

    def test_registry_capabilities(self):
        """Test registry provides correct capabilities."""
        from providers.openrouter_registry import OpenRouterModelRegistry

        registry = OpenRouterModelRegistry()

        # Test known model
        caps = registry.get_capabilities("opus")
        assert caps is not None
        assert caps.model_name == "anthropic/claude-3-opus"
        assert caps.context_window == 200000  # Claude's context window

        # Test using full model name
        caps = registry.get_capabilities("anthropic/claude-3-opus")
        assert caps is not None
        assert caps.model_name == "anthropic/claude-3-opus"

        # Test unknown model
        caps = registry.get_capabilities("non-existent-model")
        assert caps is None

    def test_multiple_aliases_same_model(self):
        """Test multiple aliases pointing to same model."""
        from providers.openrouter_registry import OpenRouterModelRegistry

        registry = OpenRouterModelRegistry()

        # All these should resolve to Claude Sonnet
        sonnet_aliases = ["sonnet", "claude", "claude-sonnet", "claude3-sonnet"]
        for alias in sonnet_aliases:
            config = registry.resolve(alias)
            assert config is not None
            assert config.model_name == "anthropic/claude-3-sonnet"


class TestOpenRouterFunctionality:
    """Test OpenRouter-specific functionality."""

    def test_openrouter_always_uses_correct_url(self):
        """Test that OpenRouter always uses the correct base URL."""
        provider = OpenRouterProvider(api_key="test-key")
        assert provider.base_url == "https://openrouter.ai/api/v1"

        # Even if we try to change it, it should remain the OpenRouter URL
        # (This is a characteristic of the OpenRouter provider)
        provider.base_url = "http://example.com"  # Try to change it
        # But new instances should always use the correct URL
        provider2 = OpenRouterProvider(api_key="test-key")
        assert provider2.base_url == "https://openrouter.ai/api/v1"

    def test_openrouter_headers_set_correctly(self):
        """Test that OpenRouter specific headers are set."""
        provider = OpenRouterProvider(api_key="test-key")

        # Check default headers
        assert "HTTP-Referer" in provider.DEFAULT_HEADERS
        assert "X-Title" in provider.DEFAULT_HEADERS
        assert provider.DEFAULT_HEADERS["X-Title"] == "Zen MCP Server"

    def test_openrouter_model_registry_initialized(self):
        """Test that model registry is properly initialized."""
        provider = OpenRouterProvider(api_key="test-key")

        # Registry should be initialized
        assert hasattr(provider, "_registry")
        assert provider._registry is not None
