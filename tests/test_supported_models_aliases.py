"""Test the MODEL_CAPABILITIES aliases structure across all providers."""

import os
from unittest.mock import patch

from providers.dial import DIALModelProvider
from providers.gemini import GeminiModelProvider
from providers.openai import OpenAIModelProvider
from providers.registries.gemini import GeminiModelRegistry
from providers.xai import XAIModelProvider


class TestSupportedModelsAliases:
    """Test that all providers have correctly structured MODEL_CAPABILITIES with aliases."""

    def test_gemini_provider_aliases(self):
        """Test Gemini provider's alias structure."""
        provider = GeminiModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.MODEL_CAPABILITIES.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases (default behaviour: bare aliases stay on the upstream models)
        # Bare "flash" stays on gemini-2.5-flash; the newest gemini-3.8-flash carries the
        # "gemini-flash-latest" alias plus a dynamic_aliases entry for "flash". gemini-3.5-flash
        # keeps only its version-specific "flash3.5" alias.
        assert "flash" in provider.MODEL_CAPABILITIES["gemini-2.5-flash"].aliases
        assert "flash2.5" in provider.MODEL_CAPABILITIES["gemini-2.5-flash"].aliases
        assert "flash3.5" in provider.MODEL_CAPABILITIES["gemini-3.5-flash"].aliases
        assert "flash3.7" in provider.MODEL_CAPABILITIES["gemini-3.7-flash"].aliases
        assert "gemini-flash-latest" in provider.MODEL_CAPABILITIES["gemini-3.8-flash"].aliases
        assert "flash" in provider.MODEL_CAPABILITIES["gemini-3.8-flash"].dynamic_aliases
        # Bare "pro" stays on gemini-3-pro-preview; gemini-3.1-pro-preview carries distinct aliases
        # ("gemini-3.1-pro"/"gemini-pro-latest") plus a dynamic_aliases entry for "pro".
        assert "pro" in provider.MODEL_CAPABILITIES["gemini-3-pro-preview"].aliases
        assert "gemini-3.1-pro" in provider.MODEL_CAPABILITIES["gemini-3.1-pro-preview"].aliases
        assert "gemini-pro-latest" in provider.MODEL_CAPABILITIES["gemini-3.1-pro-preview"].aliases
        assert "pro" in provider.MODEL_CAPABILITIES["gemini-3.1-pro-preview"].dynamic_aliases
        assert "flash-2.0" in provider.MODEL_CAPABILITIES["gemini-2.0-flash"].aliases
        assert "flash2" in provider.MODEL_CAPABILITIES["gemini-2.0-flash"].aliases
        # Bare flash-lite/flashlite stay on gemini-2.0-flash-lite; the newest gemini-3.5-flash-lite
        # carries "gemini-flash-lite-latest" plus dynamic_aliases entries for "flash-lite"/"flashlite".
        assert "flash-lite" in provider.MODEL_CAPABILITIES["gemini-2.0-flash-lite"].aliases
        assert "flashlite" in provider.MODEL_CAPABILITIES["gemini-2.0-flash-lite"].aliases
        assert "gemini-flash-lite-latest" in provider.MODEL_CAPABILITIES["gemini-3.5-flash-lite"].aliases
        assert "flash-lite" in provider.MODEL_CAPABILITIES["gemini-3.5-flash-lite"].dynamic_aliases

        # Test alias resolution (default: upstream targets)
        assert provider._resolve_model_name("flash3.7") == "gemini-3.7-flash"
        assert provider._resolve_model_name("gemini-flash-latest") == "gemini-3.8-flash"
        assert provider._resolve_model_name("flash") == "gemini-2.5-flash"
        assert provider._resolve_model_name("pro") == "gemini-3-pro-preview"
        assert provider._resolve_model_name("flash-2.0") == "gemini-2.0-flash"
        assert provider._resolve_model_name("flash2") == "gemini-2.0-flash"
        assert provider._resolve_model_name("flashlite") == "gemini-2.0-flash-lite"

        # Test case insensitive resolution
        assert provider._resolve_model_name("Flash") == "gemini-2.5-flash"
        assert provider._resolve_model_name("PRO") == "gemini-3-pro-preview"

    def test_gemini_bare_alias_remaps_to_newest_under_flag(self):
        """Flag-on coverage: DYNAMIC_MODEL_SELECTION remaps bare aliases to the newest models.

        Alias remaps are applied when the registry is constructed, so the env var must be set
        before building a fresh registry instance under the patched environment.
        """
        with patch.dict(os.environ, {"DYNAMIC_MODEL_SELECTION": "1"}, clear=False):
            registry = GeminiModelRegistry()

            # Bare aliases now point at the newest models instead of the upstream targets.
            assert registry.alias_map["flash"] == "gemini-3.8-flash"
            assert registry.alias_map["pro"] == "gemini-3.1-pro-preview"
            assert registry.alias_map["flash-lite"] == "gemini-3.5-flash-lite"
            assert registry.resolve("flash").model_name == "gemini-3.8-flash"
            assert registry.resolve("pro").model_name == "gemini-3.1-pro-preview"

    def test_openai_provider_aliases(self):
        """Test OpenAI provider's alias structure."""
        provider = OpenAIModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.MODEL_CAPABILITIES.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        # "mini" is now an alias for gpt-5-mini, not o4-mini
        assert "mini" in provider.MODEL_CAPABILITIES["gpt-5-mini"].aliases
        assert "o4mini" in provider.MODEL_CAPABILITIES["o4-mini"].aliases
        # o4-mini is no longer in its own aliases (removed self-reference)
        assert "o3mini" in provider.MODEL_CAPABILITIES["o3-mini"].aliases
        assert "o3pro" in provider.MODEL_CAPABILITIES["o3-pro"].aliases
        assert "gpt4.1" in provider.MODEL_CAPABILITIES["gpt-4.1"].aliases
        assert "gpt5.2" in provider.MODEL_CAPABILITIES["gpt-5.2"].aliases
        assert "gpt5.1-codex" in provider.MODEL_CAPABILITIES["gpt-5.1-codex"].aliases
        assert "codex-mini" in provider.MODEL_CAPABILITIES["gpt-5.1-codex-mini"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("mini") == "gpt-5-mini"  # mini -> gpt-5-mini now
        assert provider._resolve_model_name("o3mini") == "o3-mini"
        assert provider._resolve_model_name("o3pro") == "o3-pro"  # o3pro resolves to o3-pro
        assert provider._resolve_model_name("o4mini") == "o4-mini"
        assert provider._resolve_model_name("gpt4.1") == "gpt-4.1"  # gpt4.1 resolves to gpt-4.1
        assert provider._resolve_model_name("gpt5.2") == "gpt-5.2"
        assert provider._resolve_model_name("gpt5.1") == "gpt-5.1"  # gpt-5.1 is now its own model
        assert provider._resolve_model_name("gpt5.1-codex") == "gpt-5.1-codex"
        assert provider._resolve_model_name("codex-mini") == "gpt-5.1-codex-mini"

        # Test case insensitive resolution
        assert provider._resolve_model_name("Mini") == "gpt-5-mini"  # mini -> gpt-5-mini now
        assert provider._resolve_model_name("O3MINI") == "o3-mini"
        assert provider._resolve_model_name("Gpt5.1") == "gpt-5.1"  # gpt-5.1 is now its own model

    def test_xai_provider_aliases(self):
        """Test XAI provider's alias structure."""
        provider = XAIModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.MODEL_CAPABILITIES.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        assert "grok" in provider.MODEL_CAPABILITIES["grok-4"].aliases
        assert "grok4" in provider.MODEL_CAPABILITIES["grok-4"].aliases
        assert "grok-4.1-fast-reasoning" in provider.MODEL_CAPABILITIES["grok-4-1-fast-reasoning"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("grok") == "grok-4"
        assert provider._resolve_model_name("grok4") == "grok-4"
        assert provider._resolve_model_name("grok-4.1-fast-reasoning") == "grok-4-1-fast-reasoning"
        assert provider._resolve_model_name("grok-4.1-fast-reasoning-latest") == "grok-4-1-fast-reasoning"

        # Test case insensitive resolution
        assert provider._resolve_model_name("Grok") == "grok-4"
        assert provider._resolve_model_name("GROK-4.1-FAST-REASONING") == "grok-4-1-fast-reasoning"

    def test_dial_provider_aliases(self):
        """Test DIAL provider's alias structure."""
        provider = DIALModelProvider("test-key")

        # Check that all models have ModelCapabilities with aliases
        for model_name, config in provider.MODEL_CAPABILITIES.items():
            assert hasattr(config, "aliases"), f"{model_name} must have aliases attribute"
            assert isinstance(config.aliases, list), f"{model_name} aliases must be a list"

        # Test specific aliases
        assert "o3" in provider.MODEL_CAPABILITIES["o3-2025-04-16"].aliases
        assert "o4-mini" in provider.MODEL_CAPABILITIES["o4-mini-2025-04-16"].aliases
        assert "sonnet-4.1" in provider.MODEL_CAPABILITIES["anthropic.claude-sonnet-4.1-20250805-v1:0"].aliases
        assert "opus-4.1" in provider.MODEL_CAPABILITIES["anthropic.claude-opus-4.1-20250805-v1:0"].aliases
        assert "gemini-2.5-pro" in provider.MODEL_CAPABILITIES["gemini-2.5-pro-preview-05-06"].aliases

        # Test alias resolution
        assert provider._resolve_model_name("o3") == "o3-2025-04-16"
        assert provider._resolve_model_name("o4-mini") == "o4-mini-2025-04-16"
        assert provider._resolve_model_name("sonnet-4.1") == "anthropic.claude-sonnet-4.1-20250805-v1:0"
        assert provider._resolve_model_name("opus-4.1") == "anthropic.claude-opus-4.1-20250805-v1:0"

        # Test case insensitive resolution
        assert provider._resolve_model_name("O3") == "o3-2025-04-16"
        assert provider._resolve_model_name("SONNET-4.1") == "anthropic.claude-sonnet-4.1-20250805-v1:0"

    def test_list_models_includes_aliases(self):
        """Test that list_models returns both base models and aliases."""
        # Test Gemini
        gemini_provider = GeminiModelProvider("test-key")
        gemini_models = gemini_provider.list_models(respect_restrictions=False)
        assert "gemini-2.5-flash" in gemini_models
        assert "flash" in gemini_models
        assert "gemini-3-pro-preview" in gemini_models
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
        assert "grok-4" in xai_models
        assert "grok" in xai_models
        assert "grok-4.1-fast" in xai_models
        assert "grok-4.1-fast-reasoning" in xai_models

        # Test DIAL
        dial_provider = DIALModelProvider("test-key")
        dial_models = dial_provider.list_models(respect_restrictions=False)
        assert "o3-2025-04-16" in dial_models
        assert "o3" in dial_models

    def test_list_models_all_known_variant_includes_aliases(self):
        """Unified list_models should support lowercase, alias-inclusive listings."""
        # Test Gemini
        gemini_provider = GeminiModelProvider("test-key")
        gemini_all = gemini_provider.list_models(
            respect_restrictions=False,
            include_aliases=True,
            lowercase=True,
            unique=True,
        )
        assert "gemini-2.5-flash" in gemini_all
        assert "flash" in gemini_all
        assert "gemini-3-pro-preview" in gemini_all
        assert "pro" in gemini_all
        # All should be lowercase
        assert all(model == model.lower() for model in gemini_all)

        # Test OpenAI
        openai_provider = OpenAIModelProvider("test-key")
        openai_all = openai_provider.list_models(
            respect_restrictions=False,
            include_aliases=True,
            lowercase=True,
            unique=True,
        )
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
            for model_name, config in provider.MODEL_CAPABILITIES.items():
                # All values must be ModelCapabilities objects, not strings or dicts
                from providers.shared import ModelCapabilities

                assert isinstance(config, ModelCapabilities), (
                    f"{provider.__class__.__name__}.MODEL_CAPABILITIES['{model_name}'] "
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
