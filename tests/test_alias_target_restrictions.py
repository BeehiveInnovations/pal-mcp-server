"""
Tests for alias and target model restriction validation.

This test suite ensures that the restriction service properly validates
both alias names and their target models, preventing policy bypass vulnerabilities.
"""

import os
from unittest.mock import patch

from providers.base import ProviderType
from providers.gemini import GeminiModelProvider
from providers.openai_provider import OpenAIModelProvider
from utils.model_restrictions import ModelRestrictionService


class TestAliasTargetRestrictions:
    """Test that restriction validation works for both aliases and their targets."""

    def test_openai_alias_target_validation_comprehensive(self):
        """Test OpenAI provider includes both aliases and targets in validation."""
        provider = OpenAIModelProvider(api_key="test-key")

        # Get all known models including aliases and targets
        all_known = provider.list_all_known_models()

        # Should include both aliases and their targets
        assert "mini" in all_known  # alias
        assert "o4-mini" in all_known  # target of 'mini'
        assert "o3mini" in all_known  # alias
        assert "o3-mini" in all_known  # target of 'o3mini'

    def test_gemini_alias_target_validation_comprehensive(self):
        """Test Gemini provider includes both aliases and targets in validation."""
        provider = GeminiModelProvider(api_key="test-key")

        # Get all known models including aliases and targets
        all_known = provider.list_all_known_models()

        # Should include both aliases and their targets
        assert "flash" in all_known  # alias
        assert "gemini-2.5-flash" in all_known  # target of 'flash'
        assert "pro" in all_known  # alias
        assert "gemini-2.5-pro" in all_known  # target of 'pro'

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o4-mini"})  # Allow target
    def test_restriction_policy_allows_alias_when_target_allowed(self):
        """Test that restriction policy allows alias when target model is allowed.

        This is the correct user-friendly behavior - if you allow 'o4-mini',
        you should be able to use its aliases 'o4mini' and 'o4-mini'.
        Note: 'mini' is now an alias for 'gpt-5-mini', not 'o4-mini'.
        """
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = OpenAIModelProvider(api_key="test-key")

        # Both target and its actual aliases should be allowed
        assert provider.validate_model_name("o4-mini")
        assert provider.validate_model_name("o4mini")

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "mini"})  # Allow alias only
    def test_restriction_policy_allows_only_alias_when_alias_specified(self):
        """Test that restriction policy allows only the alias when just alias is specified.

        If you restrict to 'mini' (which is an alias for gpt-5-mini),
        only the alias should work, not other models.
        This is the correct restrictive behavior.
        """
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = OpenAIModelProvider(api_key="test-key")

        # Only the alias should be allowed
        assert provider.validate_model_name("mini")
        # Direct target for this alias should NOT be allowed (mini -> gpt-5-mini)
        assert not provider.validate_model_name("gpt-5-mini")
        # Other models should NOT be allowed
        assert not provider.validate_model_name("o4-mini")

    @patch.dict(os.environ, {"GOOGLE_ALLOWED_MODELS": "gemini-2.5-flash"})  # Allow target
    def test_gemini_restriction_policy_allows_alias_when_target_allowed(self):
        """Test Gemini restriction policy allows alias when target is allowed."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = GeminiModelProvider(api_key="test-key")

        # Both target and alias should be allowed
        assert provider.validate_model_name("gemini-2.5-flash")
        assert provider.validate_model_name("flash")

    @patch.dict(os.environ, {"GOOGLE_ALLOWED_MODELS": "flash"})  # Allow alias only
    def test_gemini_restriction_policy_allows_only_alias_when_alias_specified(self):
        """Test Gemini restriction policy allows only alias when just alias is specified."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = GeminiModelProvider(api_key="test-key")

        # Only the alias should be allowed
        assert provider.validate_model_name("flash")
        # Direct target should NOT be allowed
        assert not provider.validate_model_name("gemini-2.5-flash")

    def test_restriction_service_validation_includes_all_targets(self):
        """Test that restriction service validation knows about all aliases and targets."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o4-mini,invalid-model"}):
            service = ModelRestrictionService()

            # Create real provider instances
            provider_instances = {ProviderType.OPENAI: OpenAIModelProvider(api_key="test-key")}

            # Capture warnings
            with patch("utils.model_restrictions.logger") as mock_logger:
                service.validate_against_known_models(provider_instances)

                # Should have warned about the invalid model
                warning_calls = [call for call in mock_logger.warning.call_args_list if "invalid-model" in str(call)]
                assert len(warning_calls) > 0, "Should have warned about invalid-model"

                # The warning should include both aliases and targets in known models
                warning_message = str(warning_calls[0])
                assert "o4mini" in warning_message or "o4-mini" in warning_message  # aliases should be in known models

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "mini,gpt-5-mini,o4-mini,o4mini"})  # Allow different models
    def test_both_alias_and_target_allowed_when_both_specified(self):
        """Test that both alias and target work when both are explicitly allowed.

        mini -> gpt-5-mini
        o4mini -> o4-mini
        """
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = OpenAIModelProvider(api_key="test-key")

        # All should be allowed since we explicitly allowed them
        assert provider.validate_model_name("mini")  # alias for gpt-5-mini
        assert provider.validate_model_name("gpt-5-mini")  # target
        assert provider.validate_model_name("o4-mini")  # target
        assert provider.validate_model_name("o4mini")  # alias for o4-mini

    def test_alias_target_policy_regression_prevention(self):
        """Regression test to ensure aliases and targets are both validated properly.

        This test specifically prevents the bug where list_models() only returned
        aliases but not their targets, causing restriction validation to miss
        deny-list entries for target models.
        """
        # Test OpenAI provider
        openai_provider = OpenAIModelProvider(api_key="test-key")
        openai_all_known = openai_provider.list_all_known_models()

        # Verify that for each alias, its target is also included
        for model_name, config in openai_provider.SUPPORTED_MODELS.items():
            assert model_name.lower() in openai_all_known
            if isinstance(config, str):  # This is an alias
                # The target should also be in the known models
                assert (
                    config.lower() in openai_all_known
                ), f"Target '{config}' for alias '{model_name}' not in known models"

        # Test Gemini provider
        gemini_provider = GeminiModelProvider(api_key="test-key")
        gemini_all_known = gemini_provider.list_all_known_models()

        # Verify that for each alias, its target is also included
        for model_name, config in gemini_provider.SUPPORTED_MODELS.items():
            assert model_name.lower() in gemini_all_known
            if isinstance(config, str):  # This is an alias
                # The target should also be in the known models
                assert (
                    config.lower() in gemini_all_known
                ), f"Target '{config}' for alias '{model_name}' not in known models"

    def test_no_duplicate_models_in_list_all_known_models(self):
        """Test that list_all_known_models doesn't return duplicates."""
        # Test all providers
        providers = [
            OpenAIModelProvider(api_key="test-key"),
            GeminiModelProvider(api_key="test-key"),
        ]

        for provider in providers:
            all_known = provider.list_all_known_models()
            # Should not have duplicates
            assert len(all_known) == len(set(all_known)), f"{provider.__class__.__name__} returns duplicate models"

    def test_restriction_validation_uses_polymorphic_interface(self):
        """Test that restriction validation uses the clean polymorphic interface."""
        service = ModelRestrictionService()

        # Create a mock provider
        from unittest.mock import MagicMock

        mock_provider = MagicMock()
        mock_provider.list_all_known_models.return_value = ["model1", "model2", "target-model"]

        # Set up a restriction that should trigger validation
        service.restrictions = {ProviderType.OPENAI: {"invalid-model"}}

        provider_instances = {ProviderType.OPENAI: mock_provider}

        # Should call the polymorphic method
        service.validate_against_known_models(provider_instances)

        # Verify the polymorphic method was called
        mock_provider.list_all_known_models.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o4-mini"})  # Restrict to specific model
    def test_complex_alias_chains_handled_correctly(self):
        """Test that complex alias chains are handled correctly in restrictions."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = OpenAIModelProvider(api_key="test-key")

        # Only o4-mini should be allowed
        assert provider.validate_model_name("o4-mini")

        # Other models should be blocked
        assert not provider.validate_model_name("o3")
        assert not provider.validate_model_name("o3-mini")

    def test_critical_regression_validation_sees_alias_targets(self):
        """CRITICAL REGRESSION TEST: Ensure validation can see alias target models.

        This test prevents the specific bug where list_models() only returned
        alias keys but not their targets, causing validate_against_known_models()
        to miss restrictions on target model names.

        Before the fix:
        - list_models() returned ["mini", "o3mini"] (aliases only)
        - validate_against_known_models() only checked against ["mini", "o3mini"]
        - A restriction on "o4-mini" (target) would not be recognized as valid

        After the fix:
        - list_all_known_models() returns ["mini", "o3mini", "o4-mini", "o3-mini"] (aliases + targets)
        - validate_against_known_models() checks against all names
        - A restriction on "o4-mini" is recognized as valid
        """
        # This test specifically validates the HIGH-severity bug that was found
        service = ModelRestrictionService()

        # Create provider instance
        provider = OpenAIModelProvider(api_key="test-key")
        provider_instances = {ProviderType.OPENAI: provider}

        # Get all known models - should include BOTH aliases AND targets
        all_known = provider.list_all_known_models()

        # Critical check: should contain both aliases and their targets
        assert "mini" in all_known  # alias
        assert "o4-mini" in all_known  # target of mini - THIS WAS MISSING BEFORE
        assert "o3mini" in all_known  # alias
        assert "o3-mini" in all_known  # target of o3mini - THIS WAS MISSING BEFORE

        # Simulate restriction validation with a target model name
        # This should NOT warn because "o4-mini" is a valid target
        with patch("utils.model_restrictions.logger") as mock_logger:
            # Set restriction to target model (not alias)
            service.restrictions = {ProviderType.OPENAI: {"o4-mini"}}

            # This should NOT generate warnings because o4-mini is known
            service.validate_against_known_models(provider_instances)

            # Should NOT have any warnings about o4-mini being unrecognized
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "o4-mini" in str(call) and "not a recognized" in str(call)
            ]
            assert len(warning_calls) == 0, "o4-mini should be recognized as valid target model"

        # Test the reverse: alias in restriction should also be recognized
        with patch("utils.model_restrictions.logger") as mock_logger:
            # Set restriction to alias name
            service.restrictions = {ProviderType.OPENAI: {"mini"}}

            # This should NOT generate warnings because mini is known
            service.validate_against_known_models(provider_instances)

            # Should NOT have any warnings about mini being unrecognized
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "mini" in str(call) and "not a recognized" in str(call)
            ]
            assert len(warning_calls) == 0, "mini should be recognized as valid alias"

    def test_critical_regression_prevents_policy_bypass(self):
        """CRITICAL REGRESSION TEST: Prevent policy bypass through missing target validation.

        This test ensures that if an admin restricts access to a target model name,
        the restriction is properly enforced and the target is recognized as a valid
        model to restrict.

        The bug: If list_all_known_models() doesn't include targets, then validation
        would incorrectly warn that target model names are "not recognized", making
        it appear that target-based restrictions don't work.
        """
        # Test with a made-up restriction scenario
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o4-mini,o3-mini"}):
            # Clear cached restriction service
            import utils.model_restrictions

            utils.model_restrictions._restriction_service = None

            service = ModelRestrictionService()
            provider = OpenAIModelProvider(api_key="test-key")

            # These specific target models should be recognized as valid
            all_known = provider.list_all_known_models()
            assert "o4-mini" in all_known, "Target model o4-mini should be known"
            assert "o3-mini" in all_known, "Target model o3-mini should be known"

            # Validation should not warn about these being unrecognized
            with patch("utils.model_restrictions.logger") as mock_logger:
                provider_instances = {ProviderType.OPENAI: provider}
                service.validate_against_known_models(provider_instances)

                # Should not warn about our allowed models being unrecognized
                all_warnings = [str(call) for call in mock_logger.warning.call_args_list]
                for warning in all_warnings:
                    assert "o4-mini" not in warning or "not a recognized" not in warning
                    assert "o3-mini" not in warning or "not a recognized" not in warning

            # The restriction should actually work
            assert provider.validate_model_name("o4-mini")
            assert provider.validate_model_name("o3-mini")
            assert not provider.validate_model_name("o3-pro")  # not in allowed list
            assert not provider.validate_model_name("o3")  # not in allowed list
