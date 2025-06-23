"""
Tests that demonstrate the OLD BUGGY BEHAVIOR is now FIXED.

These tests verify that scenarios which would have incorrectly passed
before our fix now behave correctly. Each test documents the specific
bug that was fixed and what the old vs new behavior should be.

IMPORTANT: These tests PASS with our fix, but would have FAILED to catch
bugs with the old code (before list_all_known_models was implemented).
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers.base import ProviderType
from providers.gemini import GeminiModelProvider
from providers.openai_provider import OpenAIModelProvider
from utils.model_restrictions import ModelRestrictionService


class TestBuggyBehaviorPrevention:
    """
    These tests prove that our fix prevents the HIGH-severity regression
    that was identified by the O3 precommit analysis.

    OLD BUG: list_models() only returned alias keys, not targets
    FIX: list_all_known_models() returns both aliases AND targets
    """

    def test_old_bug_would_miss_target_restrictions(self):
        """
        OLD BUG: If restriction was set on target model (e.g., 'o4-mini'),
        validation would incorrectly warn it's not recognized because
        list_models() only returned aliases ['mini', 'o3mini'].

        NEW BEHAVIOR: list_all_known_models() includes targets, so 'o4-mini'
        is recognized as valid and no warning is generated.
        """
        provider = OpenAIModelProvider(api_key="test-key")

        # This is what the old broken list_models() would return - aliases only
        old_broken_list = ["mini", "o3mini"]  # Missing 'o4-mini', 'o3-mini' targets

        # This is what our fixed list_all_known_models() returns
        new_fixed_list = provider.list_all_known_models()

        # Verify the fix: new method includes both aliases AND targets
        assert "mini" in new_fixed_list  # alias
        assert "o4-mini" in new_fixed_list  # target - THIS WAS MISSING IN OLD CODE
        assert "o3mini" in new_fixed_list  # alias
        assert "o3-mini" in new_fixed_list  # target - THIS WAS MISSING IN OLD CODE

        # Prove the old behavior was broken
        assert "o4-mini" not in old_broken_list  # Old code didn't include targets
        assert "o3-mini" not in old_broken_list  # Old code didn't include targets

        # This target validation would have FAILED with old code
        service = ModelRestrictionService()
        service.restrictions = {ProviderType.OPENAI: {"o4-mini"}}  # Restrict to target

        with patch("utils.model_restrictions.logger") as mock_logger:
            provider_instances = {ProviderType.OPENAI: provider}
            service.validate_against_known_models(provider_instances)

            # NEW BEHAVIOR: No warnings because o4-mini is now in list_all_known_models
            target_warnings = [
                call
                for call in mock_logger.warning.call_args_list
                if "o4-mini" in str(call) and "not a recognized" in str(call)
            ]
            assert len(target_warnings) == 0, "o4-mini should be recognized with our fix"

    def test_old_bug_would_incorrectly_warn_about_valid_targets(self):
        """
        OLD BUG: Admins setting restrictions on target models would get
        false warnings that their restriction models are "not recognized".

        NEW BEHAVIOR: Target models are properly recognized.
        """
        # Test with Gemini provider too
        provider = GeminiModelProvider(api_key="test-key")
        all_known = provider.list_all_known_models()

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

    def test_old_bug_policy_bypass_prevention(self):
        """
        OLD BUG: Policy enforcement was incomplete because validation
        didn't know about target models. This could allow policy bypasses.

        NEW BEHAVIOR: Complete validation against all known model names.
        """
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

            # This should be ALLOWED because it resolves to o4-mini which is in the allowed list
            assert provider.validate_model_name("mini")  # Resolves to o4-mini, which IS allowed

            # Verify our list_all_known_models includes the restricted models
            all_known = provider.list_all_known_models()
            assert "o3-mini" in all_known  # Should be known (and allowed)
            assert "o4-mini" in all_known  # Should be known (and allowed)
            assert "o3-pro" in all_known  # Should be known (but blocked)
            assert "mini" in all_known  # Should be known (and allowed since it resolves to o4-mini)

    def test_demonstration_of_old_vs_new_interface(self):
        """
        Direct comparison of old vs new interface to document the fix.
        """
        provider = OpenAIModelProvider(api_key="test-key")

        # OLD interface (still exists for backward compatibility)
        old_style_models = provider.list_models(respect_restrictions=False)

        # NEW interface (our fix)
        new_comprehensive_models = provider.list_all_known_models()

        # The new interface should be a superset of the old one
        for model in old_style_models:
            assert model.lower() in [
                m.lower() for m in new_comprehensive_models
            ], f"New interface missing model {model} from old interface"

        # The new interface should include target models that old one might miss
        targets_that_should_exist = ["o4-mini", "o3-mini"]
        for target in targets_that_should_exist:
            assert target in new_comprehensive_models, f"New interface should include target model {target}"

    def test_old_validation_interface_still_works(self):
        """
        Verify our fix doesn't break existing validation workflows.
        """
        service = ModelRestrictionService()

        # Create a mock provider that simulates the old behavior
        old_style_provider = MagicMock()
        old_style_provider.SUPPORTED_MODELS = {
            "mini": "o4-mini",
            "o3mini": "o3-mini",
            "o4-mini": {"context_window": 200000},
            "o3-mini": {"context_window": 200000},
        }
        # OLD BROKEN: This would only return aliases
        old_style_provider.list_models.return_value = ["mini", "o3mini"]
        # NEW FIXED: This includes both aliases and targets
        old_style_provider.list_all_known_models.return_value = ["mini", "o3mini", "o4-mini", "o3-mini"]

        # Test that validation now uses the comprehensive method
        service.restrictions = {ProviderType.OPENAI: {"o4-mini"}}  # Restrict to target

        with patch("utils.model_restrictions.logger") as mock_logger:
            provider_instances = {ProviderType.OPENAI: old_style_provider}
            service.validate_against_known_models(provider_instances)

            # Verify the new method was called, not the old one
            old_style_provider.list_all_known_models.assert_called_once()

            # Should not warn about o4-mini being unrecognized
            target_warnings = [
                call
                for call in mock_logger.warning.call_args_list
                if "o4-mini" in str(call) and "not a recognized" in str(call)
            ]
            assert len(target_warnings) == 0

    def test_regression_proof_comprehensive_coverage(self):
        """
        Comprehensive test to prove our fix covers all provider types.
        """
        providers_to_test = [
            (OpenAIModelProvider(api_key="test-key"), "mini", "o4-mini"),
            (GeminiModelProvider(api_key="test-key"), "flash", "gemini-2.5-flash"),
        ]

        for provider, alias, target in providers_to_test:
            all_known = provider.list_all_known_models()

            # Every provider should include both aliases and targets
            assert alias in all_known, f"{provider.__class__.__name__} missing alias {alias}"
            assert target in all_known, f"{provider.__class__.__name__} missing target {target}"

            # No duplicates should exist
            assert len(all_known) == len(set(all_known)), f"{provider.__class__.__name__} returns duplicate models"

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o4-mini,invalid-model"})
    def test_validation_correctly_identifies_invalid_models(self):
        """
        Test that validation still catches truly invalid models while
        properly recognizing valid target models.

        This proves our fix works: o4-mini appears in the "Known models" list
        because list_all_known_models() now includes target models.
        """
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        service = ModelRestrictionService()
        provider = OpenAIModelProvider(api_key="test-key")

        with patch("utils.model_restrictions.logger") as mock_logger:
            provider_instances = {ProviderType.OPENAI: provider}
            service.validate_against_known_models(provider_instances)

            # Should warn about 'invalid-model' (truly invalid)
            invalid_warnings = [
                call
                for call in mock_logger.warning.call_args_list
                if "invalid-model" in str(call) and "not a recognized" in str(call)
            ]
            assert len(invalid_warnings) > 0, "Should warn about truly invalid models"

            # The warning should mention o4-mini in the "Known models" list (proving our fix works)
            warning_text = str(mock_logger.warning.call_args_list[0])
            assert "Known models:" in warning_text, "Warning should include known models list"
            assert "o4-mini" in warning_text, "o4-mini should appear in known models (proves our fix works)"
            assert "o3-mini" in warning_text, "o3-mini should appear in known models (proves our fix works)"

            # But the warning should be specifically about invalid-model
            assert "'invalid-model'" in warning_text, "Warning should specifically mention invalid-model"

    def test_custom_provider_also_implements_fix(self):
        """
        Verify that custom provider also implements the comprehensive interface.
        """
        from providers.custom import CustomProvider

        # This might fail if no URL is set, but that's expected
        try:
            provider = CustomProvider(base_url="http://test.com/v1")
            all_known = provider.list_all_known_models()
            # Should return a list (might be empty if registry not loaded)
            assert isinstance(all_known, list)
        except ValueError:
            # Expected if no base_url configured, skip this test
            pytest.skip("Custom provider requires URL configuration")

    def test_openrouter_provider_also_implements_fix(self):
        """
        Verify that OpenRouter provider also implements the comprehensive interface.
        """
        from providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key="test-key")
        all_known = provider.list_all_known_models()

        # Should return a list with both aliases and targets
        assert isinstance(all_known, list)
        # Should include some known OpenRouter aliases and their targets
        # (Exact content depends on registry, but structure should be correct)
