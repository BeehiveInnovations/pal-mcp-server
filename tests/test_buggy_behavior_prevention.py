"""
Regression scenarios ensuring alias-aware model listings stay correct.

Each test captures behavior that previously regressed so we can guard it
permanently. The focus is confirming aliases and their canonical targets
remain visible to the restriction service and related validation logic.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers.gemini import GeminiModelProvider
from providers.openai import OpenAIModelProvider
from providers.shared import ProviderType
from utils.model_restrictions import ModelRestrictionService


class TestBuggyBehaviorPrevention:
    """Regression tests for alias-aware restriction validation."""

    def test_alias_listing_includes_targets_for_restriction_validation(self):
        """Alias-aware lists expose both aliases and canonical targets."""
        provider = OpenAIModelProvider(api_key="test-key")

        # Baseline alias-only list captured for regression documentation
        alias_only_snapshot = ["mini", "o3mini"]  # Missing 'o4-mini', 'o3-mini' targets

        # Canonical listing with aliases and targets
        comprehensive_list = provider.list_models(
            respect_restrictions=False,
            include_aliases=True,
            lowercase=True,
            unique=True,
        )

        # Comprehensive listing should contain aliases and their targets
        assert "mini" in comprehensive_list
        assert "o4-mini" in comprehensive_list
        assert "o3mini" in comprehensive_list
        assert "o3-mini" in comprehensive_list

        # Legacy alias-only snapshots exclude targets
        assert "o4-mini" not in alias_only_snapshot
        assert "o3-mini" not in alias_only_snapshot

        # This scenario previously failed when targets were omitted
        service = ModelRestrictionService()
        service.restrictions = {ProviderType.OPENAI: {"o4-mini"}}  # Restrict to target

        with patch("utils.model_restrictions.logger") as mock_logger:
            provider_instances = {ProviderType.OPENAI: provider}
            service.validate_against_known_models(provider_instances)

            # No warnings expected because alias-aware list includes the target
            target_warnings = [
                call
                for call in mock_logger.warning.call_args_list
                if "o4-mini" in str(call) and "not a recognized" in str(call)
            ]
            assert len(target_warnings) == 0, "o4-mini should be recognized as a valid target"

    def test_target_models_are_recognized_during_validation(self):
        """Target model restrictions should not trigger false warnings."""
        # Test with Gemini provider too
        provider = GeminiModelProvider(api_key="test-key")
        all_known = provider.list_models(respect_restrictions=False, include_aliases=True, lowercase=True, unique=True)

        # Verify both aliases and targets are included
        assert "flash" in all_known  # alias
        assert "gemini-2.5-flash" in all_known  # target
        assert "pro" in all_known  # alias
        assert "gemini-2.5-pro" in all_known  # target

        # Simulate admin restricting to target model names
        service = ModelRestrictionService()
        service.restrictions = {
            ProviderType.GOOGLE: {
                "gemini-2.5-flash",  # Target name restriction
                "gemini-2.5-pro",  # Target name restriction
            }
        }

        with patch("utils.model_restrictions.logger") as mock_logger:
            provider_instances = {ProviderType.GOOGLE: provider}
            service.validate_against_known_models(provider_instances)

            # Should NOT warn about these valid target models
            all_warnings = [str(call) for call in mock_logger.warning.call_args_list]
            for warning in all_warnings:
                assert "gemini-2.5-flash" not in warning or "not a recognized" not in warning
                assert "gemini-2.5-pro" not in warning or "not a recognized" not in warning

    def test_policy_enforcement_remains_comprehensive(self):
        """Policy validation must account for both aliases and targets."""
        provider = OpenAIModelProvider(api_key="test-key")

        # Simulate a scenario where admin wants to restrict specific targets
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o3-mini,o4-mini"}):
            # Clear cached restriction service
            import utils.model_restrictions

            utils.model_restrictions._restriction_service = None

            # These should work because they're explicitly allowed
            assert provider.validate_model_name("o3-mini")
            assert provider.validate_model_name("o4-mini")

            # These should be blocked
            assert not provider.validate_model_name("o3-pro")  # Not in allowed list
            assert not provider.validate_model_name("o3")  # Not in allowed list

            # "mini" now resolves to gpt-5-mini, not o4-mini, so it should be blocked
            assert not provider.validate_model_name("mini")  # Resolves to gpt-5-mini, which is NOT allowed

            # But o4mini (the actual alias for o4-mini) should work
            assert provider.validate_model_name("o4mini")  # Resolves to o4-mini, which IS allowed

            # Verify our alias-aware list includes the restricted models
            all_known = provider.list_models(
                respect_restrictions=False,
                include_aliases=True,
                lowercase=True,
                unique=True,
            )
            assert "o3-mini" in all_known  # Should be known (and allowed)
            assert "o4-mini" in all_known  # Should be known (and allowed)
            assert "o3-pro" in all_known  # Should be known (but blocked)
            assert "mini" in all_known  # Should be known (and allowed since it resolves to o4-mini)

    def test_alias_aware_listing_extends_canonical_view(self):
        """Alias-aware list should be a superset of restriction-filtered names."""
        provider = OpenAIModelProvider(api_key="test-key")

        baseline_models = provider.list_models(respect_restrictions=False)

        alias_aware_models = provider.list_models(
            respect_restrictions=False,
            include_aliases=True,
            lowercase=True,
            unique=True,
        )

        # Alias-aware variant should contain everything from the baseline
        for model in baseline_models:
            assert model.lower() in [m.lower() for m in alias_aware_models], (
                f"Alias-aware listing missing baseline model {model}"
            )

        # Alias-aware variant should include canonical targets as well
        for target in ("o4-mini", "o3-mini"):
            assert target in alias_aware_models, f"Alias-aware listing should include target model {target}"

    def test_restriction_validation_uses_alias_aware_variant(self):
        """Validation should request the alias-aware lowercased, deduped list."""
        service = ModelRestrictionService()

        # Simulate a provider that only returns aliases when asked for models
        alias_only_provider = MagicMock()
        alias_only_provider.MODEL_CAPABILITIES = {
            "mini": "o4-mini",
            "o3mini": "o3-mini",
            "o4-mini": {"context_window": 200000},
            "o3-mini": {"context_window": 200000},
        }

        # Simulate alias-only vs. alias-aware behavior using a side effect
        def list_models_side_effect(**kwargs):
            respect_restrictions = kwargs.get("respect_restrictions", True)
            include_aliases = kwargs.get("include_aliases", True)
            lowercase = kwargs.get("lowercase", False)
            unique = kwargs.get("unique", False)

            if respect_restrictions and include_aliases and not lowercase and not unique:
                return ["mini", "o3mini"]

            if not respect_restrictions and include_aliases and lowercase and unique:
                return ["mini", "o3mini", "o4-mini", "o3-mini"]

            raise AssertionError(f"Unexpected list_models call: {kwargs}")

        alias_only_provider.list_models.side_effect = list_models_side_effect

        # Test that validation now uses the comprehensive method
        service.restrictions = {ProviderType.OPENAI: {"o4-mini"}}  # Restrict to target

        with patch("utils.model_restrictions.logger") as mock_logger:
            provider_instances = {ProviderType.OPENAI: alias_only_provider}
            service.validate_against_known_models(provider_instances)

            # Verify the alias-aware variant was used
            alias_only_provider.list_models.assert_called_with(
                respect_restrictions=False,
                include_aliases=True,
                lowercase=True,
                unique=True,
            )

            # Should not warn about o4-mini being unrecognized
            target_warnings = [
                call
                for call in mock_logger.warning.call_args_list
                if "o4-mini" in str(call) and "not a recognized" in str(call)
            ]
            assert len(target_warnings) == 0

    def test_alias_listing_covers_targets_for_all_providers(self):
        """Alias-aware listings should expose targets across providers."""
        providers_to_test = [
            (OpenAIModelProvider(api_key="test-key"), "mini", "o4-mini"),
            (GeminiModelProvider(api_key="test-key"), "flash", "gemini-2.5-flash"),
        ]

        for provider, alias, target in providers_to_test:
            all_known = provider.list_models(
                respect_restrictions=False, include_aliases=True, lowercase=True, unique=True
            )

            # Every provider should include both aliases and targets
            assert alias in all_known, f"{provider.__class__.__name__} missing alias {alias}"
            assert target in all_known, f"{provider.__class__.__name__} missing target {target}"

            # No duplicates should exist
            assert len(all_known) == len(set(all_known)), f"{provider.__class__.__name__} returns duplicate models"

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o4-mini,invalid-model"})
    def test_validation_correctly_identifies_invalid_models(self):
        """Validation should flag invalid models while listing valid targets."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        service = ModelRestrictionService()
        provider = OpenAIModelProvider(api_key="test-key")

        with patch("utils.model_restrictions.logger") as mock_logger:
            provider_instances = {ProviderType.OPENAI: provider}
            service.validate_against_known_models(provider_instances)

            invalid_warnings = [
                call
                for call in mock_logger.warning.call_args_list
                if "invalid-model" in str(call) and "not a recognized" in str(call)
            ]
            assert len(invalid_warnings) > 0, "Should warn about truly invalid models"

            # The warning should mention o4-mini in the known models list
            warning_text = str(mock_logger.warning.call_args_list[0])
            assert "Known models:" in warning_text, "Warning should include known models list"
            assert "o4-mini" in warning_text, "o4-mini should appear in known models"
            assert "o3-mini" in warning_text, "o3-mini should appear in known models"

            # But the warning should be specifically about invalid-model
            assert "'invalid-model'" in warning_text, "Warning should specifically mention invalid-model"

    def test_custom_provider_alias_listing(self):
        """Custom provider should expose alias-aware listings as well."""
        from providers.custom import CustomProvider

        # This might fail if no URL is set, but that's expected
        try:
            provider = CustomProvider(base_url="http://test.com/v1")
            all_known = provider.list_models(
                respect_restrictions=False, include_aliases=True, lowercase=True, unique=True
            )
            # Should return a list (might be empty if registry not loaded)
            assert isinstance(all_known, list)
        except ValueError:
            # Expected if no base_url configured, skip this test
            pytest.skip("Custom provider requires URL configuration")

    def test_openrouter_provider_alias_listing(self):
        """OpenRouter provider should expose alias-aware listings."""
        from providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key="test-key")
        all_known = provider.list_models(respect_restrictions=False, include_aliases=True, lowercase=True, unique=True)

        # Should return a list with both aliases and targets
        assert isinstance(all_known, list)
        # Should include some known OpenRouter aliases and their targets
        # (Exact content depends on registry, but structure should be correct)
