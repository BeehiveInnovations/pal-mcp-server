"""
Integration tests for model enumeration across all provider combinations.

These tests ensure that the _get_available_models() method correctly returns
all expected models based on which providers are configured via environment variables.
"""

import importlib
import json
import os

import pytest

from providers.registry import ModelProviderRegistry
from tools.analyze import AnalyzeTool


@pytest.mark.no_mock_provider
class TestModelEnumeration:
    """Test model enumeration with various provider configurations"""

    def setup_method(self):
        """Set up clean state before each test."""
        # Save original environment state
        self._original_env = {
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL", ""),
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "XAI_API_KEY": os.environ.get("XAI_API_KEY", ""),
            "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
            "CUSTOM_API_URL": os.environ.get("CUSTOM_API_URL", ""),
        }

        # Clear provider registry
        ModelProviderRegistry._instance = None

    def teardown_method(self):
        """Clean up after each test."""
        # Restore original environment
        for key, value in self._original_env.items():
            if value:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

        # Reload config
        import config

        importlib.reload(config)

        # Clear provider registry
        ModelProviderRegistry._instance = None

    def _setup_environment(self, provider_config):
        """Helper to set up environment variables for testing."""
        # Clear all provider-related env vars first
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY", "CUSTOM_API_URL"]:
            if key in os.environ:
                del os.environ[key]

        # Set new values
        for key, value in provider_config.items():
            if value is not None:
                os.environ[key] = value

        # Set auto mode only if not explicitly set in provider_config
        if "DEFAULT_MODEL" not in provider_config:
            os.environ["DEFAULT_MODEL"] = "auto"

        # Reload config to pick up changes
        import config

        importlib.reload(config)

        # Note: tools.base has been refactored to tools.shared.base_tool and tools.simple.base
        # No longer need to reload as configuration is handled at provider level

    def test_no_models_when_no_providers_configured(self):
        """Test that no native models are included when no providers are configured."""
        self._setup_environment({})  # No providers configured

        tool = AnalyzeTool()
        models = tool._get_available_models()

        # After the fix, models should only be shown from enabled providers
        # With no API keys configured, no providers should be enabled
        # Only OpenRouter aliases might still appear if they're in the registry

        # Filter out OpenRouter aliases that might still appear
        non_openrouter_models = [
            m for m in models if "/" not in m and m not in ["gemini", "pro", "flash", "opus", "sonnet", "haiku"]
        ]

        # No native provider models should be present without API keys
        assert (
            len(non_openrouter_models) == 0
        ), f"No native models should be available without API keys, but found: {non_openrouter_models}"

    def test_openrouter_models_without_api_key(self):
        """Test that OpenRouter models are NOT included when API key is not configured."""
        self._setup_environment({})  # No OpenRouter key

        tool = AnalyzeTool()
        models = tool._get_available_models()

        # OpenRouter-specific models should NOT be present
        openrouter_only_models = ["opus", "sonnet", "haiku"]
        found_count = sum(1 for m in openrouter_only_models if m in models)

        assert found_count == 0, "OpenRouter models should not be included without API key"

    def test_custom_models_without_custom_url(self):
        """Test that custom models are NOT included when CUSTOM_API_URL is not configured."""
        self._setup_environment({})  # No custom URL

        tool = AnalyzeTool()
        models = tool._get_available_models()

        # Custom-only models should NOT be present
        custom_only_models = ["local-llama", "llama3.2"]
        found_count = sum(1 for m in custom_only_models if m in models)

        assert found_count == 0, "Custom models should not be included without CUSTOM_API_URL"

    def test_custom_models_not_exposed_with_openrouter_only(self):
        """Ensure OpenRouter access alone does not surface custom-only endpoints."""
        self._setup_environment({"OPENROUTER_API_KEY": "test-openrouter-key"})

        tool = AnalyzeTool()
        models = tool._get_available_models()

        for alias in ("local-llama", "llama3.2"):
            assert alias not in models, f"Custom model alias '{alias}' should remain hidden without CUSTOM_API_URL"

    def test_no_duplicates_with_overlapping_providers(self):
        """Test that models aren't duplicated when multiple providers offer the same model."""
        self._setup_environment(
            {
                "OPENAI_API_KEY": "test",
                "OPENROUTER_API_KEY": "test",  # OpenRouter also offers OpenAI models
            }
        )

        tool = AnalyzeTool()
        models = tool._get_available_models()

        # Count occurrences of each model
        model_counts = {}
        for model in models:
            model_counts[model] = model_counts.get(model, 0) + 1

        # Check no duplicates
        duplicates = {m: count for m, count in model_counts.items() if count > 1}
        assert len(duplicates) == 0, f"Found duplicate models: {duplicates}"

    @pytest.mark.parametrize(
        "model_name,should_exist",
        [
            ("flash", False),  # Gemini - not available without API key
            ("o3", False),  # OpenAI - not available without API key
            ("grok", False),  # X.AI - not available without API key
            ("gemini-2.5-flash", False),  # Full Gemini name - not available without API key
            ("o4-mini", False),  # OpenAI variant - not available without API key
            ("grok-4.1-fast", False),  # X.AI variant - not available without API key
        ],
    )
    def test_specific_native_models_only_with_api_keys(self, model_name, should_exist):
        """Test that native models are only present when their provider has API keys configured."""
        self._setup_environment({})  # No providers

        tool = AnalyzeTool()
        models = tool._get_available_models()

        if should_exist:
            assert model_name in models, f"Model {model_name} should be present"
        else:
            assert model_name not in models, f"Native model {model_name} should not be present without API key"

    def test_openrouter_free_model_aliases_available(self, tmp_path, monkeypatch):
        """Free OpenRouter variants should expose both canonical names and aliases."""
        # Configure environment with OpenRouter access only
        self._setup_environment({"OPENROUTER_API_KEY": "test-openrouter-key"})

        # Create a temporary OpenRouter model config with a free variant
        custom_config = {
            "models": [
                {
                    "model_name": "deepseek/deepseek-r1:free",
                    "aliases": ["deepseek-free", "r1-free"],
                    "context_window": 163840,
                    "max_output_tokens": 8192,
                    "supports_extended_thinking": False,
                    "supports_json_mode": True,
                    "supports_function_calling": False,
                    "supports_images": False,
                    "max_image_size_mb": 0.0,
                    "description": "DeepSeek R1 free tier variant",
                }
            ]
        }

        config_path = tmp_path / "openrouter_models.json"
        config_path.write_text(json.dumps(custom_config), encoding="utf-8")
        monkeypatch.setenv("OPENROUTER_MODELS_CONFIG_PATH", str(config_path))

        # Reset cached registries so the temporary config is loaded
        from tools.shared.base_tool import BaseTool

        monkeypatch.setattr(BaseTool, "_openrouter_registry_cache", None, raising=False)

        from providers.openrouter import OpenRouterProvider

        monkeypatch.setattr(OpenRouterProvider, "_registry", None, raising=False)

        # Rebuild the provider registry with OpenRouter registered
        ModelProviderRegistry._instance = None
        from providers.shared import ProviderType

        ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

        tool = AnalyzeTool()
        models = tool._get_available_models()

        assert "deepseek/deepseek-r1:free" in models, "Canonical free model name should be available"
        assert "deepseek-free" in models, "Free model alias should be included for MCP validation"


# DELETED: test_auto_mode_behavior_with_environment_variables
# This test was fundamentally broken due to registry corruption.
# It cleared ModelProviderRegistry._instance without re-registering providers,
# causing impossible test conditions (expecting models when no providers exist).
# Functionality is already covered by test_auto_mode_comprehensive.py

# DELETED: test_auto_mode_model_selection_validation
# DELETED: test_environment_variable_precedence
# Both tests suffered from the same registry corruption issue as the deleted test above.
# They cleared ModelProviderRegistry._instance without re-registering providers,
# causing empty model lists and impossible test conditions.
# Auto mode functionality is already comprehensively tested in test_auto_mode_comprehensive.py
