"""Tests for model restriction functionality."""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers.base import ProviderType
from providers.gemini import GeminiModelProvider
from providers.openai_provider import OpenAIModelProvider
from utils.model_restrictions import ModelRestrictionService


class TestModelRestrictionService:
    """Test cases for ModelRestrictionService."""

    def test_no_restrictions_by_default(self):
        """Test that no restrictions exist when env vars are not set."""
        with patch.dict(os.environ, {}, clear=True):
            service = ModelRestrictionService()

            # Should allow all models
            assert service.is_allowed(ProviderType.OPENAI, "o3")
            assert service.is_allowed(ProviderType.OPENAI, "o3-mini")
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-pro")
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-flash")
            assert service.is_allowed(ProviderType.OPENROUTER, "anthropic/claude-opus-4")
            assert service.is_allowed(ProviderType.OPENROUTER, "openai/o3")

            # Should have no restrictions
            assert not service.has_restrictions(ProviderType.OPENAI)
            assert not service.has_restrictions(ProviderType.GOOGLE)
            assert not service.has_restrictions(ProviderType.OPENROUTER)

    def test_load_single_model_restriction(self):
        """Test loading a single allowed model."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o3-mini"}):
            service = ModelRestrictionService()

            # Should only allow o3-mini
            assert service.is_allowed(ProviderType.OPENAI, "o3-mini")
            assert not service.is_allowed(ProviderType.OPENAI, "o3")
            assert not service.is_allowed(ProviderType.OPENAI, "o4-mini")

            # Google and OpenRouter should have no restrictions
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-pro")
            assert service.is_allowed(ProviderType.OPENROUTER, "anthropic/claude-opus-4")

    def test_load_multiple_models_restriction(self):
        """Test loading multiple allowed models."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o3-mini,o4-mini", "GOOGLE_ALLOWED_MODELS": "flash,pro"}):
            service = ModelRestrictionService()

            # Check OpenAI models
            assert service.is_allowed(ProviderType.OPENAI, "o3-mini")
            assert service.is_allowed(ProviderType.OPENAI, "o4-mini")
            assert not service.is_allowed(ProviderType.OPENAI, "o3")

            # Check Google models
            assert service.is_allowed(ProviderType.GOOGLE, "flash")
            assert service.is_allowed(ProviderType.GOOGLE, "pro")
            assert not service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-pro")

    def test_case_insensitive_and_whitespace_handling(self):
        """Test that model names are case-insensitive and whitespace is trimmed."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": " O3-MINI , o4-Mini "}):
            service = ModelRestrictionService()

            # Should work with any case
            assert service.is_allowed(ProviderType.OPENAI, "o3-mini")
            assert service.is_allowed(ProviderType.OPENAI, "O3-MINI")
            assert service.is_allowed(ProviderType.OPENAI, "o4-mini")
            assert service.is_allowed(ProviderType.OPENAI, "O4-Mini")

    def test_empty_string_allows_all(self):
        """Test that empty string allows all models (same as unset)."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "", "GOOGLE_ALLOWED_MODELS": "flash"}):
            service = ModelRestrictionService()

            # OpenAI should allow all models (empty string = no restrictions)
            assert service.is_allowed(ProviderType.OPENAI, "o3")
            assert service.is_allowed(ProviderType.OPENAI, "o3-mini")
            assert service.is_allowed(ProviderType.OPENAI, "o4-mini")

            # Google should only allow flash (and its resolved name)
            assert service.is_allowed(ProviderType.GOOGLE, "flash")
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-flash", "flash")
            assert not service.is_allowed(ProviderType.GOOGLE, "pro")
            assert not service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-pro", "pro")

    def test_filter_models(self):
        """Test filtering a list of models based on restrictions."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o3-mini,o4-mini"}):
            service = ModelRestrictionService()

            models = ["o3", "o3-mini", "o4-mini", "o3-pro"]
            filtered = service.filter_models(ProviderType.OPENAI, models)

            assert filtered == ["o3-mini", "o4-mini"]

    def test_get_allowed_models(self):
        """Test getting the set of allowed models."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o3-mini,o4-mini"}):
            service = ModelRestrictionService()

            allowed = service.get_allowed_models(ProviderType.OPENAI)
            assert allowed == {"o3-mini", "o4-mini"}

            # No restrictions for Google
            assert service.get_allowed_models(ProviderType.GOOGLE) is None

    def test_shorthand_names_in_restrictions(self):
        """Test that shorthand names work in restrictions."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "mini,o3-mini", "GOOGLE_ALLOWED_MODELS": "flash,pro"}):
            service = ModelRestrictionService()

            # When providers check models, they pass both resolved and original names
            # OpenAI: 'mini' shorthand allows o4-mini
            assert service.is_allowed(ProviderType.OPENAI, "o4-mini", "mini")  # How providers actually call it
            assert not service.is_allowed(ProviderType.OPENAI, "o4-mini")  # Direct check without original (for testing)

            # OpenAI: o3-mini allowed directly
            assert service.is_allowed(ProviderType.OPENAI, "o3-mini")
            assert not service.is_allowed(ProviderType.OPENAI, "o3")

            # Google should allow both models via shorthands
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-flash", "flash")
            assert service.is_allowed(ProviderType.GOOGLE, "gemini-2.5-pro", "pro")

            # Also test that full names work when specified in restrictions
            assert service.is_allowed(ProviderType.OPENAI, "o3-mini", "o3mini")  # Even with shorthand

    def test_validation_against_known_models(self, caplog):
        """Test validation warnings for unknown models."""
        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o3-mini,o4-mimi"}):  # Note the typo: o4-mimi
            service = ModelRestrictionService()

            # Create mock provider with known models
            mock_provider = MagicMock()
            mock_provider.SUPPORTED_MODELS = {
                "o3": {"context_window": 200000},
                "o3-mini": {"context_window": 200000},
                "o4-mini": {"context_window": 200000},
            }
            mock_provider.list_all_known_models.return_value = ["o3", "o3-mini", "o4-mini"]

            provider_instances = {ProviderType.OPENAI: mock_provider}
            service.validate_against_known_models(provider_instances)

            # Should have logged a warning about the typo
            assert "o4-mimi" in caplog.text
            assert "not a recognized" in caplog.text

    def test_openrouter_model_restrictions(self):
        """Test OpenRouter model restrictions functionality."""
        with patch.dict(os.environ, {"OPENROUTER_ALLOWED_MODELS": "opus,sonnet"}):
            service = ModelRestrictionService()

            # Should only allow specified OpenRouter models
            assert service.is_allowed(ProviderType.OPENROUTER, "opus")
            assert service.is_allowed(ProviderType.OPENROUTER, "sonnet")
            assert service.is_allowed(ProviderType.OPENROUTER, "anthropic/claude-opus-4", "opus")  # With original name
            assert not service.is_allowed(ProviderType.OPENROUTER, "haiku")
            assert not service.is_allowed(ProviderType.OPENROUTER, "anthropic/claude-3-haiku")
            assert not service.is_allowed(ProviderType.OPENROUTER, "mistral-large")

            # Other providers should have no restrictions
            assert service.is_allowed(ProviderType.OPENAI, "o3")
            assert service.is_allowed(ProviderType.GOOGLE, "pro")

            # Should have restrictions for OpenRouter
            assert service.has_restrictions(ProviderType.OPENROUTER)
            assert not service.has_restrictions(ProviderType.OPENAI)
            assert not service.has_restrictions(ProviderType.GOOGLE)

    def test_openrouter_filter_models(self):
        """Test filtering OpenRouter models based on restrictions."""
        with patch.dict(os.environ, {"OPENROUTER_ALLOWED_MODELS": "opus,mistral"}):
            service = ModelRestrictionService()

            models = ["opus", "sonnet", "haiku", "mistral", "llama"]
            filtered = service.filter_models(ProviderType.OPENROUTER, models)

            assert filtered == ["opus", "mistral"]

    def test_combined_provider_restrictions(self):
        """Test that restrictions work correctly when set for multiple providers."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_ALLOWED_MODELS": "o3-mini",
                "GOOGLE_ALLOWED_MODELS": "flash",
                "OPENROUTER_ALLOWED_MODELS": "opus,sonnet",
            },
        ):
            service = ModelRestrictionService()

            # OpenAI restrictions
            assert service.is_allowed(ProviderType.OPENAI, "o3-mini")
            assert not service.is_allowed(ProviderType.OPENAI, "o3")

            # Google restrictions
            assert service.is_allowed(ProviderType.GOOGLE, "flash")
            assert not service.is_allowed(ProviderType.GOOGLE, "pro")

            # OpenRouter restrictions
            assert service.is_allowed(ProviderType.OPENROUTER, "opus")
            assert service.is_allowed(ProviderType.OPENROUTER, "sonnet")
            assert not service.is_allowed(ProviderType.OPENROUTER, "haiku")

            # All providers should have restrictions
            assert service.has_restrictions(ProviderType.OPENAI)
            assert service.has_restrictions(ProviderType.GOOGLE)
            assert service.has_restrictions(ProviderType.OPENROUTER)


class TestProviderIntegration:
    """Test integration with actual providers."""

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o3-mini"})
    def test_openai_provider_respects_restrictions(self):
        """Test that OpenAI provider respects restrictions."""
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = OpenAIModelProvider(api_key="test-key")

        # Should validate allowed model
        assert provider.validate_model_name("o3-mini")

        # Should not validate disallowed model
        assert not provider.validate_model_name("o3")

        # get_capabilities should raise for disallowed model
        with pytest.raises(ValueError) as exc_info:
            provider.get_capabilities("o3")
        assert "not allowed by restriction policy" in str(exc_info.value)

    @patch.dict(os.environ, {"GOOGLE_ALLOWED_MODELS": "gemini-2.5-flash,flash"})
    def test_gemini_provider_respects_restrictions(self):
        """Test that Gemini provider respects restrictions."""
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = GeminiModelProvider(api_key="test-key")

        # Should validate allowed models (both shorthand and full name allowed)
        assert provider.validate_model_name("flash")
        assert provider.validate_model_name("gemini-2.5-flash")

        # Should not validate disallowed model
        assert not provider.validate_model_name("pro")
        assert not provider.validate_model_name("gemini-2.5-pro")

        # get_capabilities should raise for disallowed model
        with pytest.raises(ValueError) as exc_info:
            provider.get_capabilities("pro")
        assert "not allowed by restriction policy" in str(exc_info.value)

    @patch.dict(os.environ, {"GOOGLE_ALLOWED_MODELS": "flash"})
    def test_gemini_parameter_order_regression_protection(self):
        """Test that prevents regression of parameter order bug in is_allowed calls.

        This test specifically catches the bug where parameters were incorrectly
        passed as (provider, user_input, resolved_name) instead of
        (provider, resolved_name, user_input).

        The bug was subtle because the is_allowed method uses OR logic, so it
        worked in most cases by accident. This test creates a scenario where
        the parameter order matters.
        """
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = GeminiModelProvider(api_key="test-key")

        # Test case: Only alias "flash" is allowed, not the full name
        # If parameters are in wrong order, this test will catch it

        # Should allow "flash" alias
        assert provider.validate_model_name("flash")

        # Should allow getting capabilities for "flash"
        capabilities = provider.get_capabilities("flash")
        assert capabilities.model_name == "gemini-2.5-flash"

        # Test the edge case: Try to use full model name when only alias is allowed
        # This should NOT be allowed - only the alias "flash" is in the restriction list
        assert not provider.validate_model_name("gemini-2.5-flash")

    @patch.dict(os.environ, {"GOOGLE_ALLOWED_MODELS": "gemini-2.5-flash"})
    def test_gemini_parameter_order_edge_case_full_name_only(self):
        """Test parameter order with only full name allowed, not alias.

        This is the reverse scenario - only the full canonical name is allowed,
        not the shorthand alias. This tests that the parameter order is correct
        when resolving aliases.
        """
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        provider = GeminiModelProvider(api_key="test-key")

        # Should allow full name
        assert provider.validate_model_name("gemini-2.5-flash")

        # Should also allow alias that resolves to allowed full name
        # This works because is_allowed checks both resolved_name and original_name
        assert provider.validate_model_name("flash")

        # Should not allow "pro" alias
        assert not provider.validate_model_name("pro")
        assert not provider.validate_model_name("gemini-2.5-pro")


class TestCustomProviderOpenRouterRestrictions:
    """Test custom provider integration with OpenRouter restrictions."""

    @patch.dict(os.environ, {"OPENROUTER_ALLOWED_MODELS": "opus,sonnet", "OPENROUTER_API_KEY": "test-key"})
    def test_custom_provider_respects_openrouter_restrictions(self):
        """Test that custom provider correctly defers OpenRouter models to OpenRouter provider."""
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.custom import CustomProvider

        provider = CustomProvider(base_url="http://test.com/v1")

        # CustomProvider should NOT validate OpenRouter models - they should be deferred to OpenRouter
        assert not provider.validate_model_name("opus")
        assert not provider.validate_model_name("sonnet")
        assert not provider.validate_model_name("haiku")

        # Should still validate custom models (is_custom=true) regardless of restrictions
        assert provider.validate_model_name("local-llama")  # This has is_custom=true

    @patch.dict(os.environ, {"OPENROUTER_ALLOWED_MODELS": "opus", "OPENROUTER_API_KEY": "test-key"})
    def test_custom_provider_openrouter_capabilities_restrictions(self):
        """Test that custom provider's get_capabilities correctly handles OpenRouter models."""
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.custom import CustomProvider

        provider = CustomProvider(base_url="http://test.com/v1")

        # For OpenRouter models, get_capabilities should still work but mark them as OPENROUTER
        # This tests the capabilities lookup, not validation
        capabilities = provider.get_capabilities("opus")
        assert capabilities.provider == ProviderType.OPENROUTER

        # Should raise for disallowed OpenRouter model
        with pytest.raises(ValueError) as exc_info:
            provider.get_capabilities("haiku")
        assert "not allowed by restriction policy" in str(exc_info.value)

        # Should still work for custom models (is_custom=true)
        capabilities = provider.get_capabilities("local-llama")
        assert capabilities.provider == ProviderType.CUSTOM

    @patch.dict(os.environ, {"OPENROUTER_ALLOWED_MODELS": "opus"}, clear=False)
    def test_custom_provider_no_openrouter_key_ignores_restrictions(self):
        """Test that when OpenRouter key is not set, cloud models are rejected regardless of restrictions."""
        # Make sure OPENROUTER_API_KEY is not set
        if "OPENROUTER_API_KEY" in os.environ:
            del os.environ["OPENROUTER_API_KEY"]
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.custom import CustomProvider

        provider = CustomProvider(base_url="http://test.com/v1")

        # Should not validate OpenRouter models when key is not available
        assert not provider.validate_model_name("opus")  # Even though it's in allowed list
        assert not provider.validate_model_name("haiku")

        # Should still validate custom models
        assert provider.validate_model_name("local-llama")

    @patch.dict(os.environ, {"OPENROUTER_ALLOWED_MODELS": "", "OPENROUTER_API_KEY": "test-key"})
    def test_custom_provider_empty_restrictions_allows_all_openrouter(self):
        """Test that custom provider correctly defers OpenRouter models regardless of restrictions."""
        # Clear any cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.custom import CustomProvider

        provider = CustomProvider(base_url="http://test.com/v1")

        # CustomProvider should NOT validate OpenRouter models - they should be deferred to OpenRouter
        assert not provider.validate_model_name("opus")
        assert not provider.validate_model_name("sonnet")
        assert not provider.validate_model_name("haiku")


class TestRegistryIntegration:
    """Test integration with ModelProviderRegistry."""

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "mini", "GOOGLE_ALLOWED_MODELS": "flash"})
    def test_registry_with_shorthand_restrictions(self):
        """Test that registry handles shorthand restrictions correctly."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.registry import ModelProviderRegistry

        # Clear registry cache
        ModelProviderRegistry.clear_cache()

        # Get available models with restrictions
        # This test documents current behavior - get_available_models doesn't handle aliases
        ModelProviderRegistry.get_available_models(respect_restrictions=True)

        # Currently, this will be empty because get_available_models doesn't
        # recognize that "mini" allows "o4-mini"
        # This is a known limitation that should be documented

    @patch("providers.registry.ModelProviderRegistry.get_provider")
    def test_get_available_models_respects_restrictions(self, mock_get_provider):
        """Test that registry filters models based on restrictions."""
        from providers.registry import ModelProviderRegistry

        # Mock providers
        mock_openai = MagicMock()
        mock_openai.SUPPORTED_MODELS = {
            "o3": {"context_window": 200000},
            "o3-mini": {"context_window": 200000},
        }
        mock_openai.get_provider_type.return_value = ProviderType.OPENAI

        def openai_list_models(respect_restrictions=True):
            from utils.model_restrictions import get_restriction_service

            restriction_service = get_restriction_service() if respect_restrictions else None
            models = []
            for model_name, config in mock_openai.SUPPORTED_MODELS.items():
                if isinstance(config, str):
                    target_model = config
                    if restriction_service and not restriction_service.is_allowed(ProviderType.OPENAI, target_model):
                        continue
                    models.append(model_name)
                else:
                    if restriction_service and not restriction_service.is_allowed(ProviderType.OPENAI, model_name):
                        continue
                    models.append(model_name)
            return models

        mock_openai.list_models = openai_list_models
        mock_openai.list_all_known_models.return_value = ["o3", "o3-mini"]

        mock_gemini = MagicMock()
        mock_gemini.SUPPORTED_MODELS = {
            "gemini-2.5-pro": {"context_window": 1048576},
            "gemini-2.5-flash": {"context_window": 1048576},
        }
        mock_gemini.get_provider_type.return_value = ProviderType.GOOGLE

        def gemini_list_models(respect_restrictions=True):
            from utils.model_restrictions import get_restriction_service

            restriction_service = get_restriction_service() if respect_restrictions else None
            models = []
            for model_name, config in mock_gemini.SUPPORTED_MODELS.items():
                if isinstance(config, str):
                    target_model = config
                    if restriction_service and not restriction_service.is_allowed(ProviderType.GOOGLE, target_model):
                        continue
                    models.append(model_name)
                else:
                    if restriction_service and not restriction_service.is_allowed(ProviderType.GOOGLE, model_name):
                        continue
                    models.append(model_name)
            return models

        mock_gemini.list_models = gemini_list_models
        mock_gemini.list_all_known_models.return_value = [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
        ]

        def get_provider_side_effect(provider_type):
            if provider_type == ProviderType.OPENAI:
                return mock_openai
            elif provider_type == ProviderType.GOOGLE:
                return mock_gemini
            return None

        mock_get_provider.side_effect = get_provider_side_effect

        # Set up registry with providers
        registry = ModelProviderRegistry()
        registry._providers = {
            ProviderType.OPENAI: type(mock_openai),
            ProviderType.GOOGLE: type(mock_gemini),
        }

        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o3-mini", "GOOGLE_ALLOWED_MODELS": "gemini-2.5-flash"}):
            # Clear cached restriction service
            import utils.model_restrictions

            utils.model_restrictions._restriction_service = None

            available = ModelProviderRegistry.get_available_models(respect_restrictions=True)

            # Should only include allowed models
            assert "o3-mini" in available
            assert "o3" not in available
            assert "gemini-2.5-flash" in available
            assert "gemini-2.5-pro" not in available


class TestShorthandRestrictions:
    """Test that shorthand model names work correctly in restrictions."""

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "mini", "GOOGLE_ALLOWED_MODELS": "flash"})
    def test_providers_validate_shorthands_correctly(self):
        """Test that providers correctly validate shorthand names."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # Test OpenAI provider
        openai_provider = OpenAIModelProvider(api_key="test-key")
        assert openai_provider.validate_model_name("mini")  # Should work with shorthand
        # When restricting to "mini", you can't use "o4-mini" directly - this is correct behavior
        assert not openai_provider.validate_model_name("o4-mini")  # Not allowed - only shorthand is allowed
        assert not openai_provider.validate_model_name("o3-mini")  # Not allowed

        # Test Gemini provider
        gemini_provider = GeminiModelProvider(api_key="test-key")
        assert gemini_provider.validate_model_name("flash")  # Should work with shorthand
        # Same for Gemini - if you restrict to "flash", you can't use the full name
        assert not gemini_provider.validate_model_name("gemini-2.5-flash")  # Not allowed
        assert not gemini_provider.validate_model_name("pro")  # Not allowed

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o3mini,mini,o4-mini"})
    def test_multiple_shorthands_for_same_model(self):
        """Test that multiple shorthands work correctly."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        openai_provider = OpenAIModelProvider(api_key="test-key")

        # Both shorthands should work
        assert openai_provider.validate_model_name("mini")  # mini -> o4-mini
        assert openai_provider.validate_model_name("o3mini")  # o3mini -> o3-mini

        # Resolved names work only if explicitly allowed
        assert openai_provider.validate_model_name("o4-mini")  # Explicitly allowed
        assert not openai_provider.validate_model_name("o3-mini")  # Not explicitly allowed, only shorthand

        # Other models should not work
        assert not openai_provider.validate_model_name("o3")
        assert not openai_provider.validate_model_name("o3-pro")

    @patch.dict(
        os.environ,
        {"OPENAI_ALLOWED_MODELS": "mini,o4-mini", "GOOGLE_ALLOWED_MODELS": "flash,gemini-2.5-flash"},
    )
    def test_both_shorthand_and_full_name_allowed(self):
        """Test that we can allow both shorthand and full names."""
        # Clear cached restriction service
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # OpenAI - both mini and o4-mini are allowed
        openai_provider = OpenAIModelProvider(api_key="test-key")
        assert openai_provider.validate_model_name("mini")
        assert openai_provider.validate_model_name("o4-mini")

        # Gemini - both flash and full name are allowed
        gemini_provider = GeminiModelProvider(api_key="test-key")
        assert gemini_provider.validate_model_name("flash")
        assert gemini_provider.validate_model_name("gemini-2.5-flash")


class TestAutoModeWithRestrictions:
    """Test auto mode behavior with restrictions."""

    @patch("providers.registry.ModelProviderRegistry.get_provider")
    def test_fallback_model_respects_restrictions(self, mock_get_provider):
        """Test that fallback model selection respects restrictions."""
        from providers.registry import ModelProviderRegistry
        from tools.models import ToolModelCategory

        # Mock providers
        mock_openai = MagicMock()
        mock_openai.SUPPORTED_MODELS = {
            "o3": {"context_window": 200000},
            "o3-mini": {"context_window": 200000},
            "o4-mini": {"context_window": 200000},
        }
        mock_openai.get_provider_type.return_value = ProviderType.OPENAI

        def openai_list_models(respect_restrictions=True):
            from utils.model_restrictions import get_restriction_service

            restriction_service = get_restriction_service() if respect_restrictions else None
            models = []
            for model_name, config in mock_openai.SUPPORTED_MODELS.items():
                if isinstance(config, str):
                    target_model = config
                    if restriction_service and not restriction_service.is_allowed(ProviderType.OPENAI, target_model):
                        continue
                    models.append(model_name)
                else:
                    if restriction_service and not restriction_service.is_allowed(ProviderType.OPENAI, model_name):
                        continue
                    models.append(model_name)
            return models

        mock_openai.list_models = openai_list_models
        mock_openai.list_all_known_models.return_value = ["o3", "o3-mini", "o4-mini"]

        # Add get_preferred_model method to mock to match new implementation
        def get_preferred_model(category, allowed_models):
            # Simple preference logic for testing - just return first allowed model
            return allowed_models[0] if allowed_models else None

        mock_openai.get_preferred_model = get_preferred_model

        def get_provider_side_effect(provider_type):
            if provider_type == ProviderType.OPENAI:
                return mock_openai
            return None

        mock_get_provider.side_effect = get_provider_side_effect

        # Set up registry
        registry = ModelProviderRegistry()
        registry._providers = {ProviderType.OPENAI: type(mock_openai)}

        with patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "o4-mini"}):
            # Clear cached restriction service
            import utils.model_restrictions

            utils.model_restrictions._restriction_service = None

            # Should pick o4-mini instead of o3-mini for fast response
            model = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)
            assert model == "o4-mini"

    @patch.dict(os.environ, {"OPENAI_ALLOWED_MODELS": "mini", "GEMINI_API_KEY": "", "OPENAI_API_KEY": "test-key"})
    def test_fallback_with_shorthand_restrictions(self):
        """Test fallback model selection with shorthand restrictions."""
        # Clear caches and reset registry
        import utils.model_restrictions
        from providers.registry import ModelProviderRegistry
        from tools.models import ToolModelCategory

        utils.model_restrictions._restriction_service = None

        # Store original providers for restoration
        registry = ModelProviderRegistry()
        original_providers = registry._providers.copy()
        original_initialized = registry._initialized_providers.copy()

        try:
            # Clear registry and register only OpenAI and Gemini providers
            ModelProviderRegistry._instance = None
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            # Even with "mini" restriction, fallback should work if provider handles it correctly
            # This tests the real-world scenario
            model = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)

            # The fallback will depend on how get_available_models handles aliases
            # When "mini" is allowed, it's returned as the allowed model
            # "mini" is now an alias for gpt-5-mini, but the list shows "mini" itself
            assert model in ["mini", "gpt-5-mini", "o4-mini", "gemini-2.5-flash"]
        finally:
            # Restore original registry state
            registry = ModelProviderRegistry()
            registry._providers.clear()
            registry._initialized_providers.clear()
            registry._providers.update(original_providers)
            registry._initialized_providers.update(original_initialized)
