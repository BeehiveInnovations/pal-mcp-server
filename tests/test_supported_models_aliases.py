"""Test the SUPPORTED_MODELS aliases structure across all providers."""

from providers.dial import DIALModelProvider
from providers.gemini import GeminiModelProvider
from providers.openai_provider import OpenAIModelProvider
from providers.xai import XAIModelProvider


class TestSupportedModelsAliases:
    """Test that all providers have correctly structured SUPPORTED_MODELS with aliases."""

    def test_gemini_provider_aliases(self):
        """Test Gemini provider's alias structure."""
        provider = GeminiModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.SUPPORTED_MODELS.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        assert "flash" in provider.SUPPORTED_MODELS["gemini-2.5-flash"].aliases
        assert "pro" in provider.SUPPORTED_MODELS["gemini-2.5-pro"].aliases
        assert "flash-2.0" in provider.SUPPORTED_MODELS["gemini-2.0-flash"].aliases
        assert "flash2" in provider.SUPPORTED_MODELS["gemini-2.0-flash"].aliases
        assert "flashlite" in provider.SUPPORTED_MODELS["gemini-2.0-flash-lite"].aliases
        assert "flash-lite" in provider.SUPPORTED_MODELS["gemini-2.0-flash-lite"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("flash") == "gemini-2.5-flash"
        assert provider._resolve_model_name("pro") == "gemini-2.5-pro"
        assert provider._resolve_model_name("flash-2.0") == "gemini-2.0-flash"
        assert provider._resolve_model_name("flash2") == "gemini-2.0-flash"
        assert provider._resolve_model_name("flashlite") == "gemini-2.0-flash-lite"

        # Test case insensitive resolution
        assert provider._resolve_model_name("Flash") == "gemini-2.5-flash"
        assert provider._resolve_model_name("PRO") == "gemini-2.5-pro"

    def test_openai_provider_aliases(self):
        """Test OpenAI provider's alias structure."""
        provider = OpenAIModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.SUPPORTED_MODELS.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        assert "mini" in provider.SUPPORTED_MODELS["o4-mini"].aliases
        assert "o4mini" in provider.SUPPORTED_MODELS["o4-mini"].aliases
        assert "o3mini" in provider.SUPPORTED_MODELS["o3-mini"].aliases
        assert "o3-pro" in provider.SUPPORTED_MODELS["o3-pro-2025-06-10"].aliases
        assert "o4minihigh" in provider.SUPPORTED_MODELS["o4-mini-high"].aliases
        assert "o4minihi" in provider.SUPPORTED_MODELS["o4-mini-high"].aliases
        assert "gpt4.1" in provider.SUPPORTED_MODELS["gpt-4.1-2025-04-14"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("mini") == "o4-mini"
        assert provider._resolve_model_name("o3mini") == "o3-mini"
        assert provider._resolve_model_name("o3-pro") == "o3-pro-2025-06-10"
        assert provider._resolve_model_name("o4minihigh") == "o4-mini-high"
        assert provider._resolve_model_name("gpt4.1") == "gpt-4.1-2025-04-14"

        # Test case insensitive resolution
        assert provider._resolve_model_name("Mini") == "o4-mini"
        assert provider._resolve_model_name("O3MINI") == "o3-mini"

    def test_xai_provider_aliases(self):
        """Test XAI provider's alias structure."""
        provider = XAIModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.SUPPORTED_MODELS.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        assert "grok" in provider.SUPPORTED_MODELS["grok-3"].aliases
        assert "grok3" in provider.SUPPORTED_MODELS["grok-3"].aliases
        assert "grok3fast" in provider.SUPPORTED_MODELS["grok-3-fast"].aliases
        assert "grokfast" in provider.SUPPORTED_MODELS["grok-3-fast"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("grok") == "grok-3"
        assert provider._resolve_model_name("grok3") == "grok-3"
        assert provider._resolve_model_name("grok3fast") == "grok-3-fast"
        assert provider._resolve_model_name("grokfast") == "grok-3-fast"

        # Test case insensitive resolution
        assert provider._resolve_model_name("Grok") == "grok-3"
        assert provider._resolve_model_name("GROKFAST") == "grok-3-fast"

    def test_dial_provider_aliases(self):
        """Test DIAL provider's alias structure."""
        provider = DIALModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.SUPPORTED_MODELS.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        assert "o3" in provider.SUPPORTED_MODELS["o3-2025-04-16"].aliases
        assert "o4-mini" in provider.SUPPORTED_MODELS["o4-mini-2025-04-16"].aliases
        assert "sonnet-4" in provider.SUPPORTED_MODELS["anthropic.claude-sonnet-4-20250514-v1:0"].aliases
        assert "opus-4" in provider.SUPPORTED_MODELS["anthropic.claude-opus-4-20250514-v1:0"].aliases
        assert "gemini-2.5-pro" in provider.SUPPORTED_MODELS["gemini-2.5-pro-preview-05-06"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("o3") == "o3-2025-04-16"
        assert provider._resolve_model_name("o4-mini") == "o4-mini-2025-04-16"
        assert provider._resolve_model_name("sonnet-4") == "anthropic.claude-sonnet-4-20250514-v1:0"
        assert provider._resolve_model_name("opus-4") == "anthropic.claude-opus-4-20250514-v1:0"

        # Test case insensitive resolution
        assert provider._resolve_model_name("O3") == "o3-2025-04-16"
        assert provider._resolve_model_name("SONNET-4") == "anthropic.claude-sonnet-4-20250514-v1:0"

    def test_list_models_includes_aliases(self):
        """Test that list_models returns both base models and aliases."""
        # Test Gemini
        gemini_provider = GeminiModelProvider("test-key")
        gemini_models = gemini_provider.list_models(respect_restrictions=False)
        assert "gemini-2.5-flash" in gemini_models
        assert "flash" in gemini_models
        assert "gemini-2.5-pro" in gemini_models
        assert "pro" in gemini_models

        # Test OpenAI
        openai_provider = OpenAIModelProvider("test-key")
        openai_models = openai_provider.list_models(respect_restrictions=False)
        assert "o4-mini" in openai_models
        assert "mini" in openai_models
        assert "o3-mini" in openai_models
        assert "o3mini" in openai_models

        # Test XAI
        xai_provider = XAIModelProvider("test-key")
        xai_models = xai_provider.list_models(respect_restrictions=False)
        assert "grok-3" in xai_models
        assert "grok" in xai_models
        assert "grok-3-fast" in xai_models
        assert "grokfast" in xai_models

        # Test DIAL
        dial_provider = DIALModelProvider("test-key")
        dial_models = dial_provider.list_models(respect_restrictions=False)
        assert "o3-2025-04-16" in dial_models
        assert "o3" in dial_models

    def test_list_all_known_models_includes_aliases(self):
        """Test that list_all_known_models returns all models and aliases in lowercase."""
        # Test Gemini
        gemini_provider = GeminiModelProvider("test-key")
        gemini_all = gemini_provider.list_all_known_models()
        assert "gemini-2.5-flash" in gemini_all
        assert "flash" in gemini_all
        assert "gemini-2.5-pro" in gemini_all
        assert "pro" in gemini_all
        # All should be lowercase
        assert all(model == model.lower() for model in gemini_all)

        # Test OpenAI
        openai_provider = OpenAIModelProvider("test-key")
        openai_all = openai_provider.list_all_known_models()
        assert "o4-mini" in openai_all
        assert "mini" in openai_all
        assert "o3-mini" in openai_all
        assert "o3mini" in openai_all
        # All should be lowercase
        assert all(model == model.lower() for model in openai_all)

    def test_no_string_shorthand_in_supported_models(self):
        """Test that no provider has string-based shorthands anymore."""
        providers = [
            GeminiModelProvider("test-key"),
            OpenAIModelProvider("test-key"),
            XAIModelProvider("test-key"),
            DIALModelProvider("test-key"),
        ]

        for provider in providers:
            for model_name, config in provider.SUPPORTED_MODELS.items():
                # All values must be ModelCapabilities objects, not strings or dicts
                from providers.base import ModelCapabilities

                assert isinstance(config, ModelCapabilities), (
                    f"{provider.__class__.__name__}.SUPPORTED_MODELS['{model_name}'] "
                    f"must be a ModelCapabilities object, not {type(config).__name__}"
                )

    def test_resolve_returns_original_if_not_found(self):
        """Test that _resolve_model_name returns original name if alias not found."""
        providers = [
            GeminiModelProvider("test-key"),
            OpenAIModelProvider("test-key"),
            XAIModelProvider("test-key"),
            DIALModelProvider("test-key"),
        ]

        for provider in providers:
            # Test with unknown model name
            assert provider._resolve_model_name("unknown-model") == "unknown-model"
            assert provider._resolve_model_name("gpt-4") == "gpt-4"
            assert provider._resolve_model_name("claude-3") == "claude-3"
