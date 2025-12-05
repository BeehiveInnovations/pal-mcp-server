"""Test that all Gemini aliases route correctly through Vertex Precedence logic.

This test verifies the fix for the bug where aliases like 'flash2', 'flash-2.0',
'flash2.5', 'gemini-pro', and 'gemini-pro-2.5' were not recognized by the
GEMINI_ALIASES hardcoded set and failed to route to Gemini/Vertex AI providers.

The refactored implementation removes the hardcoded list and lets providers
validate their own model names, making it impossible for aliases to get out of sync.
"""

import os
from unittest.mock import patch

import pytest

from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType


class TestGeminiAliasRouting:
    """Test that all Gemini aliases route correctly."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Clear registry cache before each test."""
        registry = ModelProviderRegistry()
        registry._initialized_providers.clear()
        yield
        registry._initialized_providers.clear()

    def test_all_gemini_aliases_route_to_gemini_provider(self):
        """Test that all aliases defined in gemini_models.json work."""
        # All aliases from conf/gemini_models.json
        gemini_aliases = [
            # gemini-3-pro-preview aliases
            "pro",
            "gemini3",
            "gemini-pro",
            # gemini-2.5-pro aliases
            "gemini-pro-2.5",
            # gemini-2.0-flash aliases
            "flash-2.0",
            "flash2",
            # gemini-2.0-flash-lite aliases
            "flashlite",
            "flash-lite",
            # gemini-2.5-flash aliases
            "flash",
            "flash2.5",
        ]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            for alias in gemini_aliases:
                provider = ModelProviderRegistry.get_provider_for_model(alias)
                assert provider is not None, f"Alias '{alias}' should route to Gemini provider"
                assert provider.get_provider_type() == ProviderType.GOOGLE
                # Verify the provider actually validates this alias
                assert provider.validate_model_name(alias), f"Provider should validate alias '{alias}'"

    def test_gemini_canonical_names_still_work(self):
        """Test that canonical model names (gemini-*) still work."""
        canonical_names = [
            "gemini-3-pro-preview",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash",
        ]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            for model_name in canonical_names:
                provider = ModelProviderRegistry.get_provider_for_model(model_name)
                assert provider is not None, f"Model '{model_name}' should route to Gemini provider"
                assert provider.get_provider_type() == ProviderType.GOOGLE

    def test_previously_broken_aliases_now_work(self):
        """Test that aliases which were broken by the hardcoded GEMINI_ALIASES now work.

        Before the refactor, these aliases were not in the GEMINI_ALIASES set and would
        return None even though the Gemini provider supported them.
        """
        # These aliases were in gemini_models.json but NOT in GEMINI_ALIASES
        previously_broken_aliases = [
            "flash2",  # gemini-2.0-flash alias
            "flash-2.0",  # gemini-2.0-flash alias
            "flash2.5",  # gemini-2.5-flash alias
            "gemini-pro",  # gemini-3-pro-preview alias
            "gemini-pro-2.5",  # gemini-2.5-pro alias
        ]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            for alias in previously_broken_aliases:
                provider = ModelProviderRegistry.get_provider_for_model(alias)
                assert provider is not None, (
                    f"Alias '{alias}' should route to Gemini provider. "
                    f"This was BROKEN before the refactor due to hardcoded GEMINI_ALIASES."
                )
                assert provider.get_provider_type() == ProviderType.GOOGLE
                assert provider.validate_model_name(alias)

    def test_invalid_alias_returns_none(self):
        """Test that invalid/unknown aliases return None."""
        invalid_aliases = ["not-a-model", "fake-flash", "gemini-fake"]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            for alias in invalid_aliases:
                provider = ModelProviderRegistry.get_provider_for_model(alias)
                # Should return None because no provider validates these
                # (they might fall through to OpenRouter or return None)
                if provider:
                    # If a provider is returned, it should not be Gemini
                    assert (
                        provider.validate_model_name(alias) is False
                        or provider.get_provider_type() != ProviderType.GOOGLE
                    )
