"""
Tests that reproduce and prevent provider routing bugs.

These tests specifically cover bugs that were found in production:
1. Fallback provider registration bypassing API key validation
2. OpenRouter alias-based restrictions not working
3. Double restriction filtering
4. Missing provider_used metadata
"""

import os
from unittest.mock import Mock

import pytest

from providers.base import ProviderType
from providers.registry import ModelProviderRegistry
from tools.base import ToolRequest
from tools.chat import ChatTool


class MockRequest(ToolRequest):
    """Mock request for testing."""

    pass


class TestProviderRoutingBugs:
    """Test cases that reproduce provider routing bugs."""

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

    @pytest.mark.no_mock_provider
    def test_fallback_routing_bug_reproduction(self):
        """
        CRITICAL BUG TEST: Reproduce the bug where fallback logic auto-registers
        Google provider for 'flash' model without checking GEMINI_API_KEY.

        Scenario: User has only OPENROUTER_API_KEY, requests 'flash' model.
        Bug: System incorrectly uses Google provider instead of OpenRouter.
        """
        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up bug scenario: only OpenRouter API key
            os.environ.pop("GEMINI_API_KEY", None)  # No Google API key
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("XAI_API_KEY", None)
            os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"

            # Register only OpenRouter provider (like in server.py:configure_providers)
            from providers.openrouter import OpenRouterProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

            # Create tool to test fallback logic
            tool = ChatTool()

            # Test: Request 'flash' model - should use OpenRouter, not auto-register Google
            provider = tool.get_model_provider("flash")

            # ASSERTION: Should get OpenRouter provider, not Google
            assert provider is not None, "Should find a provider for 'flash' model"
            assert provider.get_provider_type() == ProviderType.OPENROUTER, (
                f"Expected OpenRouter provider for 'flash' model with only OPENROUTER_API_KEY set, "
                f"but got {provider.get_provider_type()}"
            )

            # Test common aliases that should all route to OpenRouter
            test_models = ["flash", "pro", "o3", "o3-mini", "o4-mini"]
            for model_name in test_models:
                provider = tool.get_model_provider(model_name)
                assert provider is not None, f"Should find provider for '{model_name}'"
                assert provider.get_provider_type() == ProviderType.OPENROUTER, (
                    f"Model '{model_name}' should route to OpenRouter when only OPENROUTER_API_KEY is set, "
                    f"but got {provider.get_provider_type()}"
                )

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    @pytest.mark.no_mock_provider
    def test_fallback_should_not_register_without_api_key(self):
        """
        Test that fallback logic correctly validates API keys before registering providers.

        This test ensures the fix in tools/base.py:2067-2081 works correctly.
        """
        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up scenario: NO API keys at all
            for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Create tool to test fallback logic
            tool = ChatTool()

            # Test: Request 'flash' model with no API keys - should fail gracefully
            with pytest.raises(ValueError, match="No provider found for model 'flash'"):
                tool.get_model_provider("flash")

            # Test: Request 'o3' model with no API keys - should fail gracefully
            with pytest.raises(ValueError, match="No provider found for model 'o3'"):
                tool.get_model_provider("o3")

            # Verify no providers were auto-registered
            registry = ModelProviderRegistry()
            assert len(registry._providers) == 0, "No providers should be registered without API keys"

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    @pytest.mark.no_mock_provider
    def test_mixed_api_keys_correct_routing(self):
        """
        Test that when multiple API keys are available, provider routing works correctly.
        """
        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up scenario: Multiple API keys available
            os.environ["GEMINI_API_KEY"] = "test-gemini-key"
            os.environ["OPENAI_API_KEY"] = "test-openai-key"
            os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"
            os.environ.pop("XAI_API_KEY", None)

            # Register providers in priority order (like server.py)
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider
            from providers.openrouter import OpenRouterProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

            tool = ChatTool()

            # Test priority order: Native APIs should be preferred over OpenRouter
            # Google models should use Google provider
            flash_provider = tool.get_model_provider("flash")
            assert (
                flash_provider.get_provider_type() == ProviderType.GOOGLE
            ), "When both Google and OpenRouter API keys are available, 'flash' should prefer Google provider"

            # OpenAI models should use OpenAI provider
            o3_provider = tool.get_model_provider("o3")
            assert (
                o3_provider.get_provider_type() == ProviderType.OPENAI
            ), "When both OpenAI and OpenRouter API keys are available, 'o3' should prefer OpenAI provider"

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


class TestOpenRouterAliasRestrictions:
    """Test OpenRouter model restrictions with aliases - reproduces restriction bug."""

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

    @pytest.mark.no_mock_provider
    def test_openrouter_alias_restrictions_bug_reproduction(self):
        """
        CRITICAL BUG TEST: Reproduce the bug where OpenRouter restrictions with aliases
        resulted in "no models available" error.

        Bug scenario: OPENROUTER_ALLOWED_MODELS=o3-mini,pro,flash,o4-mini,o3
        Expected: 5 models available (aliases resolve to full names)
        Bug: 0 models available due to alias resolution failure
        """
        # Save original environment
        original_env = {}
        for key in [
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "XAI_API_KEY",
            "OPENROUTER_API_KEY",
            "OPENROUTER_ALLOWED_MODELS",
        ]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up bug scenario: Only OpenRouter with alias-based restrictions
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("XAI_API_KEY", None)
            os.environ["OPENROUTER_API_KEY"] = "test-key"
            os.environ["OPENROUTER_ALLOWED_MODELS"] = "o3-mini,pro,gpt4.1,flash,o4-mini,o3"  # User's exact config

            # Register OpenRouter provider
            from providers.openrouter import OpenRouterProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

            # Test: Get available models with restrictions
            available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

            # ASSERTION: Should have models available, not 0
            assert len(available_models) > 0, (
                f"Expected models available with alias restrictions 'o3-mini,pro,gpt4.1,flash,o4-mini,o3', "
                f"but got {len(available_models)} models. Available: {list(available_models.keys())}"
            )

            # Expected aliases that should resolve to models:
            # o3-mini -> openai/o3-mini
            # pro -> google/gemini-2.5-pro
            # flash -> google/gemini-2.5-flash
            # o4-mini -> openai/o4-mini
            # o3 -> openai/o3
            # gpt4.1 -> should not exist (expected to be filtered out)

            expected_models = {
                "openai/o3-mini",
                "google/gemini-2.5-pro",
                "google/gemini-2.5-flash",
                "openai/o4-mini",
                "openai/o3",
            }

            available_model_names = set(available_models.keys())

            # Should have at least the resolvable aliases (5 out of 6)
            assert len(available_model_names) >= 5, (
                f"Expected at least 5 models from alias restrictions, got {len(available_model_names)}: "
                f"{available_model_names}"
            )

            # Check that expected models are present
            missing_models = expected_models - available_model_names
            assert len(missing_models) == 0, (
                f"Missing expected models from alias restrictions: {missing_models}. "
                f"Available: {available_model_names}"
            )

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    @pytest.mark.no_mock_provider
    def test_openrouter_mixed_alias_and_full_names(self):
        """Test OpenRouter restrictions with mix of aliases and full model names."""
        # Save original environment
        original_env = {}
        for key in [
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "XAI_API_KEY",
            "OPENROUTER_API_KEY",
            "OPENROUTER_ALLOWED_MODELS",
        ]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up mixed restrictions: some aliases, some full names
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("XAI_API_KEY", None)
            os.environ["OPENROUTER_API_KEY"] = "test-key"
            os.environ["OPENROUTER_ALLOWED_MODELS"] = "o3-mini,anthropic/claude-3-opus,flash"

            # Register OpenRouter provider
            from providers.openrouter import OpenRouterProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

            # Test: Get available models
            available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

            expected_models = {
                "openai/o3-mini",  # from alias
                "anthropic/claude-3-opus",  # full name
                "google/gemini-2.5-flash",  # from alias
            }

            available_model_names = set(available_models.keys())

            assert (
                available_model_names == expected_models
            ), f"Expected models {expected_models}, got {available_model_names}"

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


class TestProviderMetadataBug:
    """Test for missing provider_used metadata bug."""

    def test_provider_used_metadata_included(self):
        """
        Test that provider_used metadata is included in tool responses.

        Bug: Only model_used was included, provider_used was missing.
        Fix: Added provider_used field in tools/base.py
        """
        # Test the actual _parse_response method with model_info
        tool = ChatTool()

        # Create mock provider
        mock_provider = Mock()
        mock_provider.get_provider_type.return_value = ProviderType.OPENROUTER

        # Create model_info like the execute method does
        model_info = {"provider": mock_provider, "model_name": "test-model", "model_response": Mock()}

        # Test _parse_response directly with a simple response
        request = MockRequest()
        result = tool._parse_response("Test response", request, model_info)

        # Verify metadata includes both model_used and provider_used
        assert hasattr(result, "metadata"), "ToolOutput should have metadata"
        assert result.metadata is not None, "Metadata should not be None"
        assert "model_used" in result.metadata, "Metadata should include model_used"
        assert result.metadata["model_used"] == "test-model", "model_used should be correct"
        assert "provider_used" in result.metadata, "Metadata should include provider_used (bug fix)"
        assert result.metadata["provider_used"] == "openrouter", "provider_used should be correct"
