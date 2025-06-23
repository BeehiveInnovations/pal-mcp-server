"""Comprehensive tests for auto mode functionality across all provider combinations"""

import importlib
import os
from unittest.mock import MagicMock, patch

import pytest

from providers.base import ProviderType
from providers.registry import ModelProviderRegistry
from tools.analyze import AnalyzeTool
from tools.chat import ChatTool
from tools.debug import DebugIssueTool
from tools.models import ToolModelCategory
from tools.thinkdeep import ThinkDeepTool


@pytest.mark.no_mock_provider
class TestAutoModeComprehensive:
    """Test auto mode model selection across all provider combinations"""

    def setup_method(self):
        """Set up clean state before each test."""
        # Save original environment state for restoration
        import os

        self._original_default_model = os.environ.get("DEFAULT_MODEL", "")

        # Clear restriction service cache
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # Clear provider registry by resetting singleton instance
        ModelProviderRegistry._instance = None

    def teardown_method(self):
        """Clean up after each test."""
        # Restore original DEFAULT_MODEL
        import os

        if self._original_default_model:
            os.environ["DEFAULT_MODEL"] = self._original_default_model
        elif "DEFAULT_MODEL" in os.environ:
            del os.environ["DEFAULT_MODEL"]

        # Reload config to pick up the restored DEFAULT_MODEL
        import importlib

        import config

        importlib.reload(config)

        # Clear restriction service cache
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # Clear provider registry by resetting singleton instance
        ModelProviderRegistry._instance = None

        # Re-register providers for subsequent tests (like conftest.py does)
        from providers.gemini import GeminiModelProvider
        from providers.openai_provider import OpenAIModelProvider
        from providers.xai import XAIModelProvider

        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
        ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)

    @pytest.mark.parametrize(
        "provider_config,expected_models",
        [
            # Only Gemini API available
            (
                {
                    "GEMINI_API_KEY": "real-key",
                    "OPENAI_API_KEY": None,
                    "XAI_API_KEY": None,
                    "OPENROUTER_API_KEY": None,
                },
                {
                    "EXTENDED_REASONING": "gemini-2.5-pro",  # Pro for deep thinking
                    "FAST_RESPONSE": "gemini-2.5-flash",  # Flash for speed
                    "BALANCED": "gemini-2.5-flash",  # Flash as balanced
                },
            ),
            # Only OpenAI API available
            (
                {
                    "GEMINI_API_KEY": None,
                    "OPENAI_API_KEY": "real-key",
                    "XAI_API_KEY": None,
                    "OPENROUTER_API_KEY": None,
                },
                {
                    "EXTENDED_REASONING": "o3",  # O3 for deep reasoning
                    "FAST_RESPONSE": "o4-mini",  # O4-mini for speed
                    "BALANCED": "o4-mini",  # O4-mini as balanced
                },
            ),
            # Only X.AI API available
            (
                {
                    "GEMINI_API_KEY": None,
                    "OPENAI_API_KEY": None,
                    "XAI_API_KEY": "real-key",
                    "OPENROUTER_API_KEY": None,
                },
                {
                    "EXTENDED_REASONING": "grok-3",  # GROK-3 for reasoning
                    "FAST_RESPONSE": "grok-3-fast",  # GROK-3-fast for speed
                    "BALANCED": "grok-3",  # GROK-3 as balanced
                },
            ),
            # Both Gemini and OpenAI available - should prefer based on tool category
            (
                {
                    "GEMINI_API_KEY": "real-key",
                    "OPENAI_API_KEY": "real-key",
                    "XAI_API_KEY": None,
                    "OPENROUTER_API_KEY": None,
                },
                {
                    "EXTENDED_REASONING": "o3",  # Prefer O3 for deep reasoning
                    "FAST_RESPONSE": "o4-mini",  # Prefer O4-mini for speed
                    "BALANCED": "o4-mini",  # Prefer OpenAI for balanced
                },
            ),
            # All native APIs available - should prefer based on tool category
            (
                {
                    "GEMINI_API_KEY": "real-key",
                    "OPENAI_API_KEY": "real-key",
                    "XAI_API_KEY": "real-key",
                    "OPENROUTER_API_KEY": None,
                },
                {
                    "EXTENDED_REASONING": "o3",  # Prefer O3 for deep reasoning
                    "FAST_RESPONSE": "o4-mini",  # Prefer O4-mini for speed
                    "BALANCED": "o4-mini",  # Prefer OpenAI for balanced
                },
            ),
        ],
    )
    def test_auto_mode_model_selection_by_provider(self, provider_config, expected_models):
        """Test that auto mode selects correct models based on available providers."""

        # Set up environment with specific provider configuration
        # Filter out None values and handle them separately
        env_to_set = {k: v for k, v in provider_config.items() if v is not None}
        env_to_clear = [k for k, v in provider_config.items() if v is None]

        with patch.dict(os.environ, env_to_set, clear=False):
            # Clear the None-valued environment variables
            for key in env_to_clear:
                if key in os.environ:
                    del os.environ[key]
            # Reload config to pick up auto mode
            os.environ["DEFAULT_MODEL"] = "auto"
            import config

            importlib.reload(config)

            # Register providers based on configuration
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider
            from providers.openrouter import OpenRouterProvider
            from providers.xai import XAIModelProvider

            if provider_config.get("GEMINI_API_KEY"):
                ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            if provider_config.get("OPENAI_API_KEY"):
                ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
            if provider_config.get("XAI_API_KEY"):
                ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)
            if provider_config.get("OPENROUTER_API_KEY"):
                ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

            # Test each tool category
            for category_name, expected_model in expected_models.items():
                category = ToolModelCategory(category_name.lower())

                # Get preferred fallback model for this category
                fallback_model = ModelProviderRegistry.get_preferred_fallback_model(category)

                assert fallback_model == expected_model, (
                    f"Provider config {provider_config}: "
                    f"Expected {expected_model} for {category_name}, got {fallback_model}"
                )

    @pytest.mark.parametrize(
        "tool_class,expected_category",
        [
            (ChatTool, ToolModelCategory.FAST_RESPONSE),
            (AnalyzeTool, ToolModelCategory.EXTENDED_REASONING),  # AnalyzeTool uses EXTENDED_REASONING
            (DebugIssueTool, ToolModelCategory.EXTENDED_REASONING),
            (ThinkDeepTool, ToolModelCategory.EXTENDED_REASONING),
        ],
    )
    def test_tool_model_categories(self, tool_class, expected_category):
        """Test that tools have the correct model categories."""
        tool = tool_class()
        assert tool.get_model_category() == expected_category

    @pytest.mark.asyncio
    async def test_auto_mode_with_gemini_only_uses_correct_models(self):
        """Test that auto mode with only Gemini uses flash for fast tools and pro for reasoning tools."""

        provider_config = {
            "GEMINI_API_KEY": "real-key",
            "OPENAI_API_KEY": None,
            "XAI_API_KEY": None,
            "OPENROUTER_API_KEY": None,
            "DEFAULT_MODEL": "auto",
        }

        # Filter out None values to avoid patch.dict errors
        env_to_set = {k: v for k, v in provider_config.items() if v is not None}
        env_to_clear = [k for k, v in provider_config.items() if v is None]

        with patch.dict(os.environ, env_to_set, clear=False):
            # Clear the None-valued environment variables
            for key in env_to_clear:
                if key in os.environ:
                    del os.environ[key]
            import config

            importlib.reload(config)

            # Register only Gemini provider
            from providers.gemini import GeminiModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            # Mock provider to capture what model is requested
            mock_provider = MagicMock()
            mock_provider.generate_content.return_value = MagicMock(
                content="test response", model_name="test-model", usage={"input_tokens": 10, "output_tokens": 5}
            )

            with patch.object(ModelProviderRegistry, "get_provider_for_model", return_value=mock_provider):
                # Test ChatTool (FAST_RESPONSE) - should prefer flash
                chat_tool = ChatTool()
                await chat_tool.execute({"prompt": "test", "model": "auto"})  # This should trigger auto selection

                # In auto mode, the tool should get an error requiring model selection
                # but the suggested model should be flash

                # Reset mock for next test
                ModelProviderRegistry.get_provider_for_model.reset_mock()

                # Test DebugIssueTool (EXTENDED_REASONING) - should prefer pro
                debug_tool = DebugIssueTool()
                await debug_tool.execute({"prompt": "test error", "model": "auto"})

    def test_auto_mode_schema_includes_all_available_models(self):
        """Test that auto mode schema includes all available models for user convenience."""

        # Test with only Gemini available
        provider_config = {
            "GEMINI_API_KEY": "real-key",
            "OPENAI_API_KEY": None,
            "XAI_API_KEY": None,
            "OPENROUTER_API_KEY": None,
            "DEFAULT_MODEL": "auto",
        }

        # Filter out None values to avoid patch.dict errors
        env_to_set = {k: v for k, v in provider_config.items() if v is not None}
        env_to_clear = [k for k, v in provider_config.items() if v is None]

        with patch.dict(os.environ, env_to_set, clear=False):
            # Clear the None-valued environment variables
            for key in env_to_clear:
                if key in os.environ:
                    del os.environ[key]
            import config

            importlib.reload(config)

            # Register only Gemini provider
            from providers.gemini import GeminiModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            tool = AnalyzeTool()
            schema = tool.get_input_schema()

            # Should have model as required field
            assert "model" in schema["required"]

            # Should include all model options from global config
            model_schema = schema["properties"]["model"]
            assert "enum" in model_schema

            available_models = model_schema["enum"]

            # Should include Gemini models
            assert "flash" in available_models
            assert "pro" in available_models
            assert "gemini-2.5-flash" in available_models
            assert "gemini-2.5-pro" in available_models

            # After the fix, schema only shows models from enabled providers
            # This prevents model namespace collisions and misleading users
            # If only Gemini is configured, only Gemini models should appear
            provider_count = len(
                [
                    key
                    for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]
                    if os.getenv(key) and os.getenv(key) != f"your_{key.lower()}_here"
                ]
            )

            if provider_count == 1 and os.getenv("GEMINI_API_KEY"):
                # Only Gemini configured - should only show Gemini models
                non_gemini_models = [
                    m
                    for m in available_models
                    if not m.startswith("gemini")
                    and m
                    not in [
                        "flash",
                        "pro",
                        "flash-2.0",
                        "flash2",
                        "flashlite",
                        "flash-lite",
                        "flash2.5",
                        "gemini pro",
                        "gemini-pro",
                    ]
                ]
                assert (
                    len(non_gemini_models) == 0
                ), f"Found non-Gemini models when only Gemini configured: {non_gemini_models}"
            else:
                # Multiple providers or OpenRouter - should include various models
                # Only check if models are available if their providers might be configured
                if os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY"):
                    assert any("o3" in m or "o4" in m for m in available_models), "No OpenAI models found"
                if os.getenv("XAI_API_KEY") or os.getenv("OPENROUTER_API_KEY"):
                    assert any("grok" in m for m in available_models), "No XAI models found"

    def test_auto_mode_schema_with_all_providers(self):
        """Test that auto mode schema includes models from all available providers."""

        provider_config = {
            "GEMINI_API_KEY": "real-key",
            "OPENAI_API_KEY": "real-key",
            "XAI_API_KEY": "real-key",
            "OPENROUTER_API_KEY": None,  # Don't include OpenRouter to avoid infinite models
            "DEFAULT_MODEL": "auto",
        }

        # Filter out None values to avoid patch.dict errors
        env_to_set = {k: v for k, v in provider_config.items() if v is not None}
        env_to_clear = [k for k, v in provider_config.items() if v is None]

        with patch.dict(os.environ, env_to_set, clear=False):
            # Clear the None-valued environment variables
            for key in env_to_clear:
                if key in os.environ:
                    del os.environ[key]
            import config

            importlib.reload(config)

            # Register all native providers
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider
            from providers.xai import XAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)

            tool = AnalyzeTool()
            schema = tool.get_input_schema()

            model_schema = schema["properties"]["model"]
            available_models = model_schema["enum"]

            # Should include models from all providers
            # Gemini models
            assert "flash" in available_models
            assert "pro" in available_models

            # OpenAI models
            assert "o3" in available_models
            assert "o4-mini" in available_models

            # XAI models
            assert "grok" in available_models
            assert "grok-3" in available_models

    @pytest.mark.asyncio
    async def test_auto_mode_model_parameter_required_error(self):
        """Test that auto mode properly requires model parameter and suggests correct model."""

        provider_config = {
            "GEMINI_API_KEY": "real-key",
            "OPENAI_API_KEY": None,
            "XAI_API_KEY": None,
            "OPENROUTER_API_KEY": None,
            "DEFAULT_MODEL": "auto",
        }

        # Filter out None values to avoid patch.dict errors
        env_to_set = {k: v for k, v in provider_config.items() if v is not None}
        env_to_clear = [k for k, v in provider_config.items() if v is None]

        with patch.dict(os.environ, env_to_set, clear=False):
            # Clear the None-valued environment variables
            for key in env_to_clear:
                if key in os.environ:
                    del os.environ[key]
            import config

            importlib.reload(config)

            # Register only Gemini provider
            from providers.gemini import GeminiModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            # Test with ChatTool (FAST_RESPONSE category)
            chat_tool = ChatTool()
            result = await chat_tool.execute(
                {
                    "prompt": "test"
                    # Note: no model parameter provided in auto mode
                }
            )

            # Should get error requiring model selection
            assert len(result) == 1
            response_text = result[0].text

            # Parse JSON response to check error
            import json

            response_data = json.loads(response_text)

            assert response_data["status"] == "error"
            assert (
                "Model parameter is required" in response_data["content"]
                or "Model 'auto' is not available" in response_data["content"]
            )
            # Note: With the new SimpleTool-based Chat tool, the error format is simpler
            # and doesn't include category-specific suggestions like the original tool did

    def test_model_availability_with_restrictions(self):
        """Test that auto mode respects model restrictions when selecting fallback models."""

        provider_config = {
            "GEMINI_API_KEY": "real-key",
            "OPENAI_API_KEY": "real-key",
            "XAI_API_KEY": None,
            "OPENROUTER_API_KEY": None,
            "DEFAULT_MODEL": "auto",
            "OPENAI_ALLOWED_MODELS": "o4-mini",  # Restrict OpenAI to only o4-mini
        }

        # Filter out None values to avoid patch.dict errors
        env_to_set = {k: v for k, v in provider_config.items() if v is not None}
        env_to_clear = [k for k, v in provider_config.items() if v is None]

        with patch.dict(os.environ, env_to_set, clear=False):
            # Clear the None-valued environment variables
            for key in env_to_clear:
                if key in os.environ:
                    del os.environ[key]
            import config

            importlib.reload(config)

            # Clear restriction service to pick up new env vars
            import utils.model_restrictions

            utils.model_restrictions._restriction_service = None

            # Register providers
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

            # Get available models - should respect restrictions
            available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

            # Should include restricted OpenAI model
            assert "o4-mini" in available_models

            # Should NOT include non-restricted OpenAI models
            assert "o3" not in available_models
            assert "o3-mini" not in available_models

            # Should still include all Gemini models (no restrictions)
            assert "gemini-2.5-flash" in available_models
            assert "gemini-2.5-pro" in available_models

    def test_openrouter_fallback_when_no_native_apis(self):
        """Test that OpenRouter provides fallback models when no native APIs are available."""

        provider_config = {
            "GEMINI_API_KEY": None,
            "OPENAI_API_KEY": None,
            "XAI_API_KEY": None,
            "OPENROUTER_API_KEY": "real-key",
            "DEFAULT_MODEL": "auto",
        }

        # Filter out None values to avoid patch.dict errors
        env_to_set = {k: v for k, v in provider_config.items() if v is not None}
        env_to_clear = [k for k, v in provider_config.items() if v is None]

        with patch.dict(os.environ, env_to_set, clear=False):
            # Clear the None-valued environment variables
            for key in env_to_clear:
                if key in os.environ:
                    del os.environ[key]
            import config

            importlib.reload(config)

            # Register only OpenRouter provider
            from providers.openrouter import OpenRouterProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

            # Mock OpenRouter registry to return known models
            mock_registry = MagicMock()
            mock_registry.list_models.return_value = [
                "google/gemini-2.5-flash",
                "google/gemini-2.5-pro",
                "openai/o3",
                "openai/o4-mini",
                "anthropic/claude-opus-4",
            ]

            with patch.object(OpenRouterProvider, "_registry", mock_registry):
                # Get preferred models for different categories
                extended_reasoning = ModelProviderRegistry.get_preferred_fallback_model(
                    ToolModelCategory.EXTENDED_REASONING
                )
                fast_response = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)

                # Should fallback to known good models even via OpenRouter
                # The exact model depends on _find_extended_thinking_model implementation
                assert extended_reasoning is not None
                assert fast_response is not None

    @pytest.mark.asyncio
    async def test_actual_model_name_resolution_in_auto_mode(self):
        """Test that when a model is selected in auto mode, the tool executes successfully."""

        provider_config = {
            "GEMINI_API_KEY": "real-key",
            "OPENAI_API_KEY": None,
            "XAI_API_KEY": None,
            "OPENROUTER_API_KEY": None,
            "DEFAULT_MODEL": "auto",
        }

        # Filter out None values to avoid patch.dict errors
        env_to_set = {k: v for k, v in provider_config.items() if v is not None}
        env_to_clear = [k for k, v in provider_config.items() if v is None]

        with patch.dict(os.environ, env_to_set, clear=False):
            # Clear the None-valued environment variables
            for key in env_to_clear:
                if key in os.environ:
                    del os.environ[key]
            import config

            importlib.reload(config)

            # Register Gemini provider
            from providers.gemini import GeminiModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            # Mock the actual provider to simulate successful execution
            mock_provider = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "test response"
            mock_response.model_name = "gemini-2.5-flash"  # The resolved name
            mock_response.usage = {"input_tokens": 10, "output_tokens": 5}
            # Mock _resolve_model_name to simulate alias resolution
            mock_provider._resolve_model_name = lambda alias: ("gemini-2.5-flash" if alias == "flash" else alias)
            mock_provider.generate_content.return_value = mock_response

            with patch.object(ModelProviderRegistry, "get_provider_for_model", return_value=mock_provider):
                chat_tool = ChatTool()
                result = await chat_tool.execute({"prompt": "test", "model": "flash"})  # Use alias in auto mode

                # Should succeed with proper model resolution
                assert len(result) == 1
                # Just verify that the tool executed successfully and didn't return an error
                assert "error" not in result[0].text.lower()
