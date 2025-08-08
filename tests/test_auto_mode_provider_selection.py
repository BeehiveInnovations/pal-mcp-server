"""Test auto mode provider selection logic specifically"""

import os

import pytest

from providers.base import ProviderType
from providers.registry import ModelProviderRegistry
from tools.models import ToolModelCategory


@pytest.mark.no_mock_provider
class TestAutoModeProviderSelection:
    """Test the core auto mode provider selection logic"""

    def setup_method(self):
        """Set up clean state before each test."""
        # Clear restriction service cache
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # Clear provider registry
        registry = ModelProviderRegistry()
        registry._providers.clear()
        registry._initialized_providers.clear()

    def teardown_method(self):
        """Clean up after each test."""
        # Clear restriction service cache
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def test_gemini_only_fallback_selection(self):
        """Test auto mode fallback when only Gemini is available."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up environment - only Gemini available
            os.environ["GEMINI_API_KEY"] = "test-key"
            for key in ["OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Register only Gemini provider
            from providers.gemini import GeminiModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            # Test fallback selection for different categories
            extended_reasoning = ModelProviderRegistry.get_preferred_fallback_model(
                ToolModelCategory.EXTENDED_REASONING
            )
            fast_response = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)
            balanced = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.BALANCED)

            # Should select appropriate Gemini models
            assert extended_reasoning in ["gemini-2.5-pro", "pro"]
            assert fast_response in ["gemini-2.5-flash", "flash"]
            assert balanced in ["gemini-2.5-flash", "flash"]

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_openai_only_fallback_selection(self):
        """Test auto mode fallback when only OpenAI is available."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up environment - only OpenAI available
            os.environ["OPENAI_API_KEY"] = "test-key"
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Register only OpenAI provider
            from providers.openai_provider import OpenAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

            # Test fallback selection for different categories
            extended_reasoning = ModelProviderRegistry.get_preferred_fallback_model(
                ToolModelCategory.EXTENDED_REASONING
            )
            fast_response = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)
            balanced = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.BALANCED)

            # Should select appropriate OpenAI models based on new preference order
            assert extended_reasoning == "o3"  # O3 for extended reasoning
            assert fast_response == "gpt-5"  # gpt-5 comes first in fast response preference
            assert balanced == "gpt-5"  # gpt-5 for balanced

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_both_gemini_and_openai_priority(self):
        """Test auto mode when both Gemini and OpenAI are available."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up environment - both Gemini and OpenAI available
            os.environ["GEMINI_API_KEY"] = "test-key"
            os.environ["OPENAI_API_KEY"] = "test-key"
            for key in ["XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Register both providers
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

            # Test fallback selection for different categories
            extended_reasoning = ModelProviderRegistry.get_preferred_fallback_model(
                ToolModelCategory.EXTENDED_REASONING
            )
            fast_response = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)

            # Should prefer Gemini now (based on new provider priority: Gemini before OpenAI)
            assert extended_reasoning == "gemini-2.5-pro"  # Gemini has higher priority now

            # Should prefer Gemini for fast response
            assert fast_response == "gemini-2.5-flash"  # Gemini has higher priority now

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_xai_only_fallback_selection(self):
        """Test auto mode fallback when only XAI is available."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up environment - only XAI available
            os.environ["XAI_API_KEY"] = "test-key"
            for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Register only XAI provider
            from providers.xai import XAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)

            # Test fallback selection for different categories
            extended_reasoning = ModelProviderRegistry.get_preferred_fallback_model(
                ToolModelCategory.EXTENDED_REASONING
            )
            fast_response = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)

            # Should fallback to available models or default fallbacks
            # Since XAI models are not explicitly handled in fallback logic,
            # it should fall back to the hardcoded defaults
            assert extended_reasoning is not None
            assert fast_response is not None

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_available_models_respects_restrictions(self):
        """Test that get_available_models respects model restrictions."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "OPENAI_ALLOWED_MODELS"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up environment with restrictions
            os.environ["GEMINI_API_KEY"] = "test-key"
            os.environ["OPENAI_API_KEY"] = "test-key"
            os.environ["OPENAI_ALLOWED_MODELS"] = "o4-mini"  # Only allow o4-mini

            # Clear restriction service to pick up new restrictions
            import utils.model_restrictions

            utils.model_restrictions._restriction_service = None

            # Register both providers
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

            # Get available models with restrictions
            available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

            # Should include allowed OpenAI model
            assert "o4-mini" in available_models
            assert available_models["o4-mini"] == ProviderType.OPENAI

            # Should NOT include restricted OpenAI models
            assert "o3" not in available_models
            assert "o3-mini" not in available_models

            # Should include all Gemini models (no restrictions)
            assert "gemini-2.5-flash" in available_models
            assert available_models["gemini-2.5-flash"] == ProviderType.GOOGLE

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_model_validation_across_providers(self):
        """Test that model validation works correctly across different providers."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up all providers
            os.environ["GEMINI_API_KEY"] = "test-key"
            os.environ["OPENAI_API_KEY"] = "test-key"
            os.environ["XAI_API_KEY"] = "test-key"

            # Register all providers
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider
            from providers.xai import XAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)

            # Test model validation - each provider should handle its own models
            # Gemini models
            gemini_provider = ModelProviderRegistry.get_provider_for_model("flash")
            assert gemini_provider is not None
            assert gemini_provider.get_provider_type() == ProviderType.GOOGLE

            # OpenAI models
            openai_provider = ModelProviderRegistry.get_provider_for_model("o3")
            assert openai_provider is not None
            assert openai_provider.get_provider_type() == ProviderType.OPENAI

            # XAI models
            xai_provider = ModelProviderRegistry.get_provider_for_model("grok")
            assert xai_provider is not None
            assert xai_provider.get_provider_type() == ProviderType.XAI

            # Invalid model should return None
            invalid_provider = ModelProviderRegistry.get_provider_for_model("invalid-model-name")
            assert invalid_provider is None

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_alias_resolution_before_api_calls(self):
        """Test that model aliases are resolved before being passed to providers."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up all providers
            os.environ["GEMINI_API_KEY"] = "test-key"
            os.environ["OPENAI_API_KEY"] = "test-key"
            os.environ["XAI_API_KEY"] = "test-key"

            # Register all providers
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider
            from providers.xai import XAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)

            # Test that providers resolve aliases correctly
            test_cases = [
                ("flash", ProviderType.GOOGLE, "gemini-2.5-flash"),
                ("pro", ProviderType.GOOGLE, "gemini-2.5-pro"),
                ("mini", ProviderType.OPENAI, "gpt-5-mini"),  # "mini" now resolves to gpt-5-mini
                ("o3mini", ProviderType.OPENAI, "o3-mini"),
                ("grok", ProviderType.XAI, "grok-4"),
                ("grokfast", ProviderType.XAI, "grok-3-fast"),
            ]

            for alias, expected_provider_type, expected_resolved_name in test_cases:
                provider = ModelProviderRegistry.get_provider_for_model(alias)
                assert provider is not None, f"No provider found for alias '{alias}'"
                assert provider.get_provider_type() == expected_provider_type, f"Wrong provider for '{alias}'"

                # Test alias resolution
                resolved_name = provider._resolve_model_name(alias)
                assert (
                    resolved_name == expected_resolved_name
                ), f"Alias '{alias}' should resolve to '{expected_resolved_name}', got '{resolved_name}'"

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
