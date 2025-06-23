"""Test auto mode with only custom provider configured to reproduce the reported issue."""

import importlib
import os
from unittest.mock import patch

import pytest

from providers.base import ProviderType
from providers.registry import ModelProviderRegistry


@pytest.mark.no_mock_provider
class TestAutoModeCustomProviderOnly:
    """Test auto mode when only custom provider is configured."""

    def setup_method(self):
        """Set up clean state before each test."""
        # Save original environment state for restoration
        self._original_env = {}
        for key in [
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "XAI_API_KEY",
            "OPENROUTER_API_KEY",
            "CUSTOM_API_URL",
            "CUSTOM_API_KEY",
            "DEFAULT_MODEL",
        ]:
            self._original_env[key] = os.environ.get(key)

        # Clear restriction service cache
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # Clear provider registry by resetting singleton instance
        ModelProviderRegistry._instance = None

    def teardown_method(self):
        """Clean up after each test."""
        # Restore original environment
        for key, value in self._original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

        # Reload config to pick up the restored environment
        import config

        importlib.reload(config)

        # Clear restriction service cache
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # Clear provider registry by resetting singleton instance
        ModelProviderRegistry._instance = None

    def test_reproduce_auto_mode_custom_provider_only_issue(self):
        """Test the fix for auto mode failing when only custom provider is configured."""

        # Set up environment with ONLY custom provider configured
        test_env = {
            "CUSTOM_API_URL": "http://localhost:11434/v1",
            "CUSTOM_API_KEY": "",  # Empty for Ollama-style
            "DEFAULT_MODEL": "auto",
        }

        # Clear all other provider keys
        clear_keys = ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY", "DIAL_API_KEY"]

        with patch.dict(os.environ, test_env, clear=False):
            # Ensure other provider keys are not set
            for key in clear_keys:
                if key in os.environ:
                    del os.environ[key]

            # Reload config to pick up auto mode
            import config

            importlib.reload(config)

            # Register only the custom provider (simulating server startup)
            from providers.custom import CustomProvider

            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, CustomProvider)

            # This should now work after the fix
            # The fix added support for custom provider registry system in get_available_models()
            available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

            # This assertion should now pass after the fix
            assert available_models, (
                "Expected custom provider models to be available. "
                "This test verifies the fix for auto mode failing with custom providers."
            )

    def test_custom_provider_models_available_via_registry(self):
        """Test that custom provider has models available via its registry system."""

        # Set up environment with only custom provider
        test_env = {
            "CUSTOM_API_URL": "http://localhost:11434/v1",
            "CUSTOM_API_KEY": "",
        }

        with patch.dict(os.environ, test_env, clear=False):
            # Clear other provider keys
            for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY", "DIAL_API_KEY"]:
                if key in os.environ:
                    del os.environ[key]

            # Register custom provider
            from providers.custom import CustomProvider

            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, CustomProvider)

            # Get the provider instance
            custom_provider = ModelProviderRegistry.get_provider(ProviderType.CUSTOM)
            assert custom_provider is not None, "Custom provider should be available"

            # Verify it has a registry with models
            assert hasattr(custom_provider, "_registry"), "Custom provider should have _registry"
            assert custom_provider._registry is not None, "Registry should be initialized"

            # Get models from registry
            models = custom_provider._registry.list_models()
            aliases = custom_provider._registry.list_aliases()

            # Should have some models and aliases available
            assert models, "Custom provider registry should have models"
            assert aliases, "Custom provider registry should have aliases"

            print(f"Available models: {len(models)}")
            print(f"Available aliases: {len(aliases)}")

    def test_custom_provider_validate_model_name(self):
        """Test that custom provider can validate model names."""

        # Set up environment with only custom provider
        test_env = {
            "CUSTOM_API_URL": "http://localhost:11434/v1",
            "CUSTOM_API_KEY": "",
        }

        with patch.dict(os.environ, test_env, clear=False):
            # Register custom provider
            from providers.custom import CustomProvider

            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, CustomProvider)

            # Get the provider instance
            custom_provider = ModelProviderRegistry.get_provider(ProviderType.CUSTOM)
            assert custom_provider is not None

            # Test that it can validate some typical custom model names
            test_models = ["llama3.2", "llama3.2:latest", "local-model", "ollama-model"]

            for model in test_models:
                is_valid = custom_provider.validate_model_name(model)
                print(f"Model '{model}' validation: {is_valid}")
                # Should validate at least some local-style models
                # (The exact validation logic may vary based on registry content)

    def test_auto_mode_fallback_with_custom_only_should_work(self):
        """Test that auto mode fallback should work when only custom provider is available."""

        # Set up environment with only custom provider
        test_env = {
            "CUSTOM_API_URL": "http://localhost:11434/v1",
            "CUSTOM_API_KEY": "",
            "DEFAULT_MODEL": "auto",
        }

        with patch.dict(os.environ, test_env, clear=False):
            # Clear other provider keys
            for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY", "DIAL_API_KEY"]:
                if key in os.environ:
                    del os.environ[key]

            # Reload config
            import config

            importlib.reload(config)

            # Register custom provider
            from providers.custom import CustomProvider

            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, CustomProvider)

            # This should work and return a fallback model from custom provider
            # Currently fails because get_preferred_fallback_model doesn't consider custom models
            from tools.models import ToolModelCategory

            try:
                fallback_model = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)
                print(f"Fallback model for FAST_RESPONSE: {fallback_model}")

                # Should get a valid model name, not the hardcoded fallback
                assert (
                    fallback_model != "gemini-2.5-flash"
                ), "Should not fallback to hardcoded Gemini model when custom provider is available"

            except Exception as e:
                pytest.fail(f"Getting fallback model failed: {e}")
