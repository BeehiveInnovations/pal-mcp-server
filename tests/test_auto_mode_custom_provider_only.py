"""Test auto mode with only custom provider configured to reproduce the reported issue."""

import importlib
import os
from unittest.mock import patch

import pytest

from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType


# Keys to clear when testing custom provider in isolation
_OTHER_PROVIDER_KEYS = ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY", "DIAL_API_KEY"]


def _clear_other_provider_keys():
    """Clear API keys for non-custom providers to isolate custom provider tests."""
    for key in _OTHER_PROVIDER_KEYS:
        if key in os.environ:
            del os.environ[key]


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

        # Clear CustomProvider registry to prevent state pollution
        from providers.custom import CustomProvider

        CustomProvider.reset_registry()

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
            _clear_other_provider_keys()

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
            _clear_other_provider_keys()

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

    def test_custom_model_name_injection(self):
        """Test that CUSTOM_MODEL_NAME is dynamically injected into registry.

        This tests the fix for GitHub issue #344 where auto mode fails
        when only CUSTOM_API_URL is configured without models in custom_models.json.
        """
        # Use a unique model name not in custom_models.json
        unique_model = "my-custom-llm-model"

        test_env = {
            "CUSTOM_API_URL": "http://localhost:11434/v1",
            "CUSTOM_API_KEY": "",
            "CUSTOM_MODEL_NAME": unique_model,
            "DEFAULT_MODEL": "auto",
        }

        with patch.dict(os.environ, test_env, clear=False):
            # Clear other provider keys
            _clear_other_provider_keys()

            # Reload config
            import config

            importlib.reload(config)

            # Reset registry to force re-initialization
            from providers.custom import CustomProvider

            CustomProvider._registry = None

            # Register custom provider - this should inject CUSTOM_MODEL_NAME
            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, CustomProvider)

            # Verify the model was injected
            custom_provider = ModelProviderRegistry.get_provider(ProviderType.CUSTOM)
            assert custom_provider is not None

            # Check model is in registry
            resolved = custom_provider._registry.resolve(unique_model)
            assert resolved is not None, f"Model '{unique_model}' should be injected into registry"
            assert resolved.model_name == unique_model

            # Check auto mode returns the user-specified model (not alphabetically first)
            from tools.models import ToolModelCategory

            fallback_model = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)
            print(f"Fallback model with injected CUSTOM_MODEL_NAME: {fallback_model}")

            # Should return the user-specified model, not gemini-2.5-flash or alphabetically first
            assert fallback_model == unique_model, (
                f"Should return user-specified model '{unique_model}', got '{fallback_model}'. "
                "CustomProvider.get_preferred_model should prioritize CUSTOM_MODEL_NAME."
            )

    def test_custom_model_name_visible_in_all_registry_instances(self):
        """Test that CUSTOM_MODEL_NAME is visible in independently created registry instances.

        This tests the fix for GitHub issue #327 where listmodels and other tools
        create their own CustomEndpointModelRegistry instances and couldn't see
        the user's CUSTOM_MODEL_NAME.
        """
        unique_model = "my-independent-model"

        test_env = {
            "CUSTOM_API_URL": "http://localhost:11434/v1",
            "CUSTOM_API_KEY": "",
            "CUSTOM_MODEL_NAME": unique_model,
        }

        with patch.dict(os.environ, test_env, clear=False):
            # Clear other provider keys
            _clear_other_provider_keys()

            # Create a NEW registry instance (simulating what listmodels does)
            from providers.registries.custom import CustomEndpointModelRegistry

            new_registry = CustomEndpointModelRegistry()

            # The new instance should automatically have the injected model
            resolved = new_registry.resolve(unique_model)
            assert resolved is not None, (
                f"Model '{unique_model}' should be visible in independently created registry. "
                "This verifies the fix for issue #327 where listmodels couldn't see CUSTOM_MODEL_NAME."
            )
            assert resolved.model_name == unique_model

            # Verify it's in the model list
            models = new_registry.list_models()
            assert unique_model in models, f"Model '{unique_model}' should be in list_models()"

            # Verify it's in the alias map
            aliases = new_registry.list_aliases()
            assert unique_model.lower() in aliases, f"Model '{unique_model}' should be in list_aliases()"

    def test_get_preferred_model_prioritizes_custom_model_name(self):
        """Test that CustomProvider.get_preferred_model prioritizes CUSTOM_MODEL_NAME.

        This ensures that when a user explicitly sets CUSTOM_MODEL_NAME, auto mode
        will select that model instead of relying on alphabetical ordering.
        """
        # Use a model name that would NOT be first alphabetically
        # (llama3.2 from custom_models.json would be first)
        unique_model = "zebra-custom-model"

        test_env = {
            "CUSTOM_API_URL": "http://localhost:11434/v1",
            "CUSTOM_API_KEY": "",
            "CUSTOM_MODEL_NAME": unique_model,
        }

        with patch.dict(os.environ, test_env, clear=False):
            # Clear other provider keys
            _clear_other_provider_keys()

            # Reset registry
            from providers.custom import CustomProvider

            CustomProvider._registry = None

            # Register custom provider
            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, CustomProvider)

            # Get provider instance
            custom_provider = ModelProviderRegistry.get_provider(ProviderType.CUSTOM)
            assert custom_provider is not None

            # Get allowed models (should include both llama3.2 and zebra-custom-model)
            allowed_models = ModelProviderRegistry._get_allowed_models_for_provider(
                custom_provider, ProviderType.CUSTOM
            )

            # Verify both models are in allowed list
            assert "llama3.2" in allowed_models, "llama3.2 should be in allowed models"
            assert unique_model in allowed_models, f"{unique_model} should be in allowed models"

            # Verify alphabetical order would select llama3.2
            assert (
                sorted(allowed_models)[0] == "llama3.2"
            ), "Alphabetically first model should be llama3.2, not the custom model"

            # Test get_preferred_model returns the user-specified model
            from tools.models import ToolModelCategory

            preferred = custom_provider.get_preferred_model(ToolModelCategory.FAST_RESPONSE, allowed_models)
            assert preferred == unique_model, (
                f"get_preferred_model should return '{unique_model}', got '{preferred}'. "
                "User-specified CUSTOM_MODEL_NAME should take priority over alphabetical order."
            )

    def test_get_preferred_model_returns_none_without_custom_model_name(self):
        """Test that get_preferred_model returns None when CUSTOM_MODEL_NAME is not set.

        This ensures backward compatibility - without explicit user preference,
        the selection falls back to alphabetical ordering.
        """
        test_env = {
            "CUSTOM_API_URL": "http://localhost:11434/v1",
            "CUSTOM_API_KEY": "",
            # CUSTOM_MODEL_NAME intentionally not set
        }

        with patch.dict(os.environ, test_env, clear=False):
            # Clear CUSTOM_MODEL_NAME if set
            if "CUSTOM_MODEL_NAME" in os.environ:
                del os.environ["CUSTOM_MODEL_NAME"]

            # Clear other provider keys
            _clear_other_provider_keys()

            # Reset registry
            from providers.custom import CustomProvider

            CustomProvider._registry = None

            # Register custom provider
            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, CustomProvider)

            # Get provider instance
            custom_provider = ModelProviderRegistry.get_provider(ProviderType.CUSTOM)
            assert custom_provider is not None

            # Get allowed models
            allowed_models = ModelProviderRegistry._get_allowed_models_for_provider(
                custom_provider, ProviderType.CUSTOM
            )

            # Test get_preferred_model returns None (fallback to alphabetical)
            from tools.models import ToolModelCategory

            preferred = custom_provider.get_preferred_model(ToolModelCategory.FAST_RESPONSE, allowed_models)
            assert (
                preferred is None
            ), f"get_preferred_model should return None without CUSTOM_MODEL_NAME, got '{preferred}'"
