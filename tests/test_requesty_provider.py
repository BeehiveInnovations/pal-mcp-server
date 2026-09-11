"""Tests for Requesty provider."""

import os
from unittest.mock import Mock, patch

import pytest

from providers.registry import ModelProviderRegistry
from providers.requesty import RequestyProvider
from providers.shared import ProviderType


class TestRequestyProvider:
    """Test cases for Requesty provider."""

    def test_provider_initialization(self):
        """Test Requesty provider initialization."""
        provider = RequestyProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://router.requesty.ai/v1"
        assert provider.FRIENDLY_NAME == "Requesty"

    def test_base_url_override(self):
        """Test REQUESTY_BASE_URL overrides the default endpoint (e.g. EU region)."""
        with patch.dict(os.environ, {"REQUESTY_BASE_URL": "https://router.eu.requesty.ai/v1"}):
            provider = RequestyProvider(api_key="test-key")
            assert provider.base_url == "https://router.eu.requesty.ai/v1"

    def test_custom_headers(self):
        """Test Requesty attribution headers."""
        # Test default headers
        assert "HTTP-Referer" in RequestyProvider.DEFAULT_HEADERS
        assert "X-Title" in RequestyProvider.DEFAULT_HEADERS

        # Test with environment variables
        with patch.dict(os.environ, {"REQUESTY_REFERER": "https://myapp.com", "REQUESTY_TITLE": "My App"}):
            from importlib import reload

            import providers.requesty

            reload(providers.requesty)

            provider = providers.requesty.RequestyProvider(api_key="test-key")
            assert provider.DEFAULT_HEADERS["HTTP-Referer"] == "https://myapp.com"
            assert provider.DEFAULT_HEADERS["X-Title"] == "My App"

    def test_model_validation(self):
        """Test model validation."""
        provider = RequestyProvider(api_key="test-key")

        # Requesty accepts models with provider prefixes or known models
        assert provider.validate_model_name("openai/gpt-4o-mini") is True
        assert provider.validate_model_name("anthropic/claude-3-opus") is True
        assert provider.validate_model_name("google/any-model-name") is True
        assert provider.validate_model_name("groq/llama-3.1-8b") is True
        assert provider.validate_model_name("grok-4") is True

        # Unknown models without provider prefix are rejected
        assert provider.validate_model_name("gpt-4") is False
        assert provider.validate_model_name("unknown-model") is False

    def test_get_capabilities(self):
        """Test capability generation."""
        provider = RequestyProvider(api_key="test-key")

        # Test with a model in the registry (using alias)
        caps = provider.get_capabilities("o3")
        assert caps.provider == ProviderType.REQUESTY
        assert caps.model_name == "openai/o3"  # Resolved name
        assert caps.friendly_name == "Requesty (openai/o3)"

        # Test with a model not in registry - should raise error
        with pytest.raises(ValueError, match="Unsupported model 'unknown-model' for provider requesty"):
            provider.get_capabilities("unknown-model")

        # Test with model that has provider prefix - should get generic capabilities
        caps = provider.get_capabilities("provider/unknown-model")
        assert caps.provider == ProviderType.REQUESTY
        assert caps.model_name == "provider/unknown-model"
        assert caps.context_window == 32_768  # Safe default
        assert hasattr(caps, "_is_generic") and caps._is_generic is True

    def test_model_alias_resolution(self):
        """Test model alias resolution."""
        provider = RequestyProvider(api_key="test-key")

        # Test alias resolution
        assert provider._resolve_model_name("opus") == "anthropic/claude-opus-4-1-20250805"
        assert provider._resolve_model_name("opus4.1") == "anthropic/claude-opus-4-1-20250805"
        assert provider._resolve_model_name("sonnet") == "anthropic/claude-sonnet-4-5-20250929"
        assert provider._resolve_model_name("sonnet4") == "anthropic/claude-sonnet-4-20250514"
        assert provider._resolve_model_name("o3") == "openai/o3"
        assert provider._resolve_model_name("o4-mini") == "openai/o4-mini"
        assert provider._resolve_model_name("o4mini") == "openai/o4-mini"
        assert provider._resolve_model_name("haiku") == "anthropic/claude-3-5-haiku-20241022"
        assert provider._resolve_model_name("gpt4o-mini") == "openai/gpt-4o-mini"
        assert provider._resolve_model_name("grok-4") == "xai/grok-4"
        assert provider._resolve_model_name("grok4") == "xai/grok-4"
        assert provider._resolve_model_name("grok") == "xai/grok-4"
        assert provider._resolve_model_name("deepseek") == "deepseek/deepseek-chat"
        assert provider._resolve_model_name("r1") == "deepseek/deepseek-reasoner"

        # Test case-insensitive
        assert provider._resolve_model_name("OPUS") == "anthropic/claude-opus-4-1-20250805"
        assert provider._resolve_model_name("SONNET") == "anthropic/claude-sonnet-4-5-20250929"
        assert provider._resolve_model_name("O3") == "openai/o3"

        # Test direct model names (should pass through unchanged)
        assert (
            provider._resolve_model_name("anthropic/claude-opus-4-1-20250805") == "anthropic/claude-opus-4-1-20250805"
        )
        assert provider._resolve_model_name("openai/o3") == "openai/o3"

        # Test unknown models pass through
        assert provider._resolve_model_name("unknown-model") == "unknown-model"
        assert provider._resolve_model_name("custom/model-v2") == "custom/model-v2"

    def test_requesty_registration(self):
        """Test Requesty can be registered and retrieved."""
        with patch.dict(os.environ, {"REQUESTY_API_KEY": "test-key"}):
            # Clean up any existing registration
            ModelProviderRegistry.unregister_provider(ProviderType.REQUESTY)

            # Register the provider
            ModelProviderRegistry.register_provider(ProviderType.REQUESTY, RequestyProvider)

            # Retrieve and verify
            provider = ModelProviderRegistry.get_provider(ProviderType.REQUESTY)
            assert provider is not None
            assert isinstance(provider, RequestyProvider)


class TestRequestyAutoMode:
    """Test auto mode functionality when only Requesty is configured."""

    def setup_method(self):
        """Store original state before each test."""
        self.registry = ModelProviderRegistry()
        self._original_providers = self.registry._providers.copy()
        self._original_initialized = self.registry._initialized_providers.copy()

        self.registry._providers.clear()
        self.registry._initialized_providers.clear()

        self._original_env = {}
        for key in ["REQUESTY_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "DEFAULT_MODEL"]:
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
    def test_requesty_only_auto_mode(self):
        """Test that auto mode works when only Requesty is configured."""
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ["REQUESTY_API_KEY"] = "test-requesty-key"
        os.environ["DEFAULT_MODEL"] = "auto"

        mock_registry = Mock()
        model_names = [
            "google/gemini-2.5-flash",
            "google/gemini-2.5-pro",
            "openai/o3",
            "openai/gpt-4o-mini",
            "anthropic/claude-opus-4-1-20250805",
            "anthropic/claude-sonnet-4-5-20250929",
        ]
        mock_registry.list_models.return_value = model_names

        # Mock resolve to return a ModelCapabilities-like object for each model
        def mock_resolve(model_name):
            if model_name in model_names:
                mock_config = Mock()
                mock_config.provider = ProviderType.REQUESTY
                mock_config.aliases = []  # Empty list of aliases
                mock_config.get_effective_capability_rank = Mock(return_value=50)  # Add ranking method
                return mock_config
            return None

        mock_registry.resolve.side_effect = mock_resolve

        ModelProviderRegistry.register_provider(ProviderType.REQUESTY, RequestyProvider)

        provider = ModelProviderRegistry.get_provider(ProviderType.REQUESTY)
        assert provider is not None, "Requesty provider should be available with API key"
        provider._registry = mock_registry

        available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

        assert len(available_models) > 0, "Should find Requesty models in auto mode"
        assert all(provider_type == ProviderType.REQUESTY for provider_type in available_models.values())

        for model in model_names:
            assert model in available_models, f"Model {model} should be available"

    @pytest.mark.no_mock_provider
    def test_requesty_with_restrictions(self):
        """Test that Requesty respects model restrictions."""
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ["REQUESTY_API_KEY"] = "test-requesty-key"
        os.environ.pop("REQUESTY_ALLOWED_MODELS", None)
        os.environ["REQUESTY_ALLOWED_MODELS"] = "anthropic/claude-opus-4-1-20250805,google/gemini-2.5-flash"
        os.environ["DEFAULT_MODEL"] = "auto"

        # Force reload to pick up new environment variable
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        try:
            mock_registry = Mock()
            mock_models = [
                "google/gemini-2.5-flash",
                "google/gemini-2.5-pro",
                "anthropic/claude-opus-4-1-20250805",
                "anthropic/claude-sonnet-4-5-20250929",
            ]
            mock_registry.list_models.return_value = mock_models

            # Mock the resolve method to return model configs with aliases
            mock_model_config = Mock()
            mock_model_config.aliases = []  # Empty aliases for simplicity
            mock_model_config.get_effective_capability_rank = Mock(return_value=50)  # Add ranking method
            mock_registry.resolve.return_value = mock_model_config

            ModelProviderRegistry.register_provider(ProviderType.REQUESTY, RequestyProvider)

            provider = ModelProviderRegistry.get_provider(ProviderType.REQUESTY)
            provider._registry = mock_registry

            available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

            assert len(available_models) > 0, "Should have some allowed models"

            expected_allowed = {"google/gemini-2.5-flash", "anthropic/claude-opus-4-1-20250805"}

            assert set(available_models.keys()) == expected_allowed, (
                f"Expected {expected_allowed}, but got {set(available_models.keys())}"
            )
        finally:
            os.environ.pop("REQUESTY_ALLOWED_MODELS", None)
            utils.model_restrictions._restriction_service = None

    @pytest.mark.no_mock_provider
    def test_requesty_without_registry(self):
        """Test that Requesty without _registry attribute doesn't crash."""
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ["REQUESTY_API_KEY"] = "test-requesty-key"
        os.environ["DEFAULT_MODEL"] = "auto"

        mock_provider_class = Mock()
        mock_provider_instance = Mock(spec=["get_provider_type", "list_models", "get_all_model_capabilities"])
        mock_provider_instance.get_provider_type.return_value = ProviderType.REQUESTY
        mock_provider_instance.list_models.return_value = []
        mock_provider_instance.get_all_model_capabilities.return_value = {}
        mock_provider_class.return_value = mock_provider_instance

        ModelProviderRegistry.register_provider(ProviderType.REQUESTY, mock_provider_class)

        available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

        assert len(available_models) == 0, "Should have no models when Requesty has no registry"


class TestRequestyRegistry:
    """Test cases for Requesty model registry."""

    def test_registry_loading(self):
        """Test registry loads models from config."""
        from providers.registries.requesty import RequestyModelRegistry

        registry = RequestyModelRegistry()

        # Should have loaded models
        models = registry.list_models()
        assert len(models) > 0
        assert "anthropic/claude-opus-4-1-20250805" in models
        assert "openai/o3" in models
        assert "openai/gpt-4o-mini" in models

        # Should have loaded aliases
        aliases = registry.list_aliases()
        assert len(aliases) > 0
        assert "opus" in aliases
        assert "o3" in aliases
        assert "sonnet" in aliases

    def test_registry_capabilities(self):
        """Test registry provides correct capabilities."""
        from providers.registries.requesty import RequestyModelRegistry

        registry = RequestyModelRegistry()

        # Test known model via alias
        caps = registry.get_capabilities("opus")
        assert caps is not None
        assert caps.model_name == "anthropic/claude-opus-4-1-20250805"
        assert caps.context_window == 200000  # Claude's context window

        # Test using full model name
        caps = registry.get_capabilities("anthropic/claude-opus-4-1-20250805")
        assert caps is not None
        assert caps.model_name == "anthropic/claude-opus-4-1-20250805"

        # Test opus4.1 alias
        caps = registry.get_capabilities("opus4.1")
        assert caps is not None
        assert caps.model_name == "anthropic/claude-opus-4-1-20250805"

        # Test unknown model
        caps = registry.get_capabilities("non-existent-model")
        assert caps is None

    def test_multiple_aliases_same_model(self):
        """Test multiple aliases pointing to same model."""
        from providers.registries.requesty import RequestyModelRegistry

        registry = RequestyModelRegistry()

        # All these should resolve to Claude Sonnet 4.5
        sonnet_45_aliases = ["sonnet", "sonnet4.5"]
        for alias in sonnet_45_aliases:
            config = registry.resolve(alias)
            assert config is not None
            assert config.model_name == "anthropic/claude-sonnet-4-5-20250929"

        # Test Sonnet 4 alias
        config = registry.resolve("sonnet4")
        assert config is not None
        assert config.model_name == "anthropic/claude-sonnet-4-20250514"


class TestRequestyFunctionality:
    """Test Requesty-specific functionality."""

    def test_requesty_uses_correct_default_url(self):
        """Test that Requesty uses the router endpoint by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REQUESTY_BASE_URL", None)
            provider = RequestyProvider(api_key="test-key")
            assert provider.base_url == "https://router.requesty.ai/v1"

            # Changing an instance must not affect new instances
            provider.base_url = "http://example.com"
            provider2 = RequestyProvider(api_key="test-key")
            assert provider2.base_url == "https://router.requesty.ai/v1"

    def test_requesty_headers_set_correctly(self):
        """Test that Requesty specific headers are set."""
        provider = RequestyProvider(api_key="test-key")

        # Check default headers
        assert "HTTP-Referer" in provider.DEFAULT_HEADERS
        assert "X-Title" in provider.DEFAULT_HEADERS
        assert provider.DEFAULT_HEADERS["X-Title"] == "PAL MCP Server"

    def test_requesty_model_registry_initialized(self):
        """Test that model registry is properly initialized."""
        provider = RequestyProvider(api_key="test-key")

        # Registry should be initialized
        assert hasattr(provider, "_registry")
        assert provider._registry is not None

    def test_requesty_provider_type(self):
        """Test provider type mapping used for restrictions and logging."""
        provider = RequestyProvider(api_key="test-key")
        assert provider.get_provider_type() == ProviderType.REQUESTY
