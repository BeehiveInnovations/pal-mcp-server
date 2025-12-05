"""Comprehensive tests for auto mode functionality across all provider combinations"""

import importlib
import os
from unittest.mock import MagicMock, patch

import pytest

from providers.gemini import GeminiModelProvider
from providers.openai import OpenAIModelProvider
from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from providers.xai import XAIModelProvider
from tools.analyze import AnalyzeTool
from tools.chat import ChatTool
from tools.debug import DebugIssueTool
from tools.models import ToolModelCategory
from tools.shared.exceptions import ToolExecutionError
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
                    "EXTENDED_REASONING": "gemini-3-pro-preview",  # Gemini 3 Pro Preview for deep thinking
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
                    "EXTENDED_REASONING": "gpt-5.1-codex",  # GPT-5.1 Codex prioritized for coding tasks
                    "FAST_RESPONSE": "gpt-5.1",  # Prefer gpt-5.1 for speed
                    "BALANCED": "gpt-5.1",  # Prefer gpt-5.1 for balanced
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
                    "EXTENDED_REASONING": "grok-4-1-fast-reasoning",  # GROK-4.1-Fast-Reasoning (latest) for cost-efficient reasoning
                    "FAST_RESPONSE": "grok-4-1-fast-non-reasoning",  # GROK-4.1-Fast-Non-Reasoning (latest) for fastest responses
                    "BALANCED": "grok-4",  # GROK-4 as balanced (still preferred)
                },
            ),
            # Both Gemini and OpenAI available - Google comes first in priority
            (
                {
                    "GEMINI_API_KEY": "real-key",
                    "OPENAI_API_KEY": "real-key",
                    "XAI_API_KEY": None,
                    "OPENROUTER_API_KEY": None,
                },
                {
                    "EXTENDED_REASONING": "gemini-3-pro-preview",  # Gemini 3 Pro Preview comes first in priority
                    "FAST_RESPONSE": "gemini-2.5-flash",  # Prefer flash for speed
                    "BALANCED": "gemini-2.5-flash",  # Prefer flash for balanced
                },
            ),
            # All native APIs available - Google still comes first
            (
                {
                    "GEMINI_API_KEY": "real-key",
                    "OPENAI_API_KEY": "real-key",
                    "XAI_API_KEY": "real-key",
                    "OPENROUTER_API_KEY": None,
                },
                {
                    "EXTENDED_REASONING": "gemini-3-pro-preview",  # Gemini 3 Pro Preview comes first in priority
                    "FAST_RESPONSE": "gemini-2.5-flash",  # Prefer flash for speed
                    "BALANCED": "gemini-2.5-flash",  # Prefer flash for balanced
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
            from providers.openrouter import OpenRouterProvider

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
    async def test_auto_mode_with_gemini_only_uses_correct_models(self, tmp_path):
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
            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            # Test ChatTool (FAST_RESPONSE) - auto mode should suggest flash variant
            chat_tool = ChatTool()
            chat_message = chat_tool._build_auto_mode_required_message()
            assert "flash" in chat_message

            # Test DebugIssueTool (EXTENDED_REASONING) - auto mode should suggest pro variant
            debug_tool = DebugIssueTool()
            debug_message = debug_tool._build_auto_mode_required_message()
            assert "pro" in debug_message

    def test_auto_mode_schema_includes_all_available_models(self):
        """Test that auto mode schema includes all available models for user convenience."""

        # Test with only Gemini available
        provider_config = {
            "GEMINI_API_KEY": "real-key",
            "OPENAI_API_KEY": None,
            "XAI_API_KEY": None,
            "OPENROUTER_API_KEY": None,
            "CUSTOM_API_URL": None,
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
            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            tool = AnalyzeTool()
            schema = tool.get_input_schema()

            # Should have model as required field
            assert "model" in schema["required"]

            # In auto mode, the schema should now have a description field
            # instructing users to use the listmodels tool instead of an enum
            model_schema = schema["properties"]["model"]
            assert "type" in model_schema
            assert model_schema["type"] == "string"
            assert "description" in model_schema

            # Check that the description mentions using listmodels tool
            description = model_schema["description"]
            assert "listmodels" in description.lower()
            assert "auto" in description.lower() or "selection" in description.lower()

            # Should NOT have enum field anymore - this is the new behavior
            assert "enum" not in model_schema

            # After the design change, the system directs users to use listmodels
            # instead of enumerating all models in the schema
            # This prevents model namespace collisions and keeps the schema cleaner

            # With the new design change, we no longer enumerate models in the schema
            # The listmodels tool should be used to discover available models
            # This test now validates the schema structure rather than model enumeration

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
            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)

            tool = AnalyzeTool()
            schema = tool.get_input_schema()

            # In auto mode with multiple providers, should still use the new schema format
            model_schema = schema["properties"]["model"]
            assert "type" in model_schema
            assert model_schema["type"] == "string"
            assert "description" in model_schema

            # Check that the description mentions using listmodels tool
            description = model_schema["description"]
            assert "listmodels" in description.lower()

            # Should NOT have enum field - uses listmodels tool instead
            assert "enum" not in model_schema

            # With multiple providers configured, the listmodels tool
            # would show models from all providers when called

    @pytest.mark.asyncio
    async def test_auto_mode_model_parameter_required_error(self, tmp_path):
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
            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            # Test with ChatTool (FAST_RESPONSE category)
            chat_tool = ChatTool()
            workdir = tmp_path / "chat_artifacts"
            workdir.mkdir(parents=True, exist_ok=True)
            with pytest.raises(ToolExecutionError) as exc_info:
                await chat_tool.execute(
                    {
                        "prompt": "test",
                        "working_directory_absolute_path": str(workdir),
                        # Note: no model parameter provided in auto mode
                    }
                )

            # Should get error requiring model selection with fallback suggestion
            import json

            response_data = json.loads(exc_info.value.payload)

            assert response_data["status"] == "error"
            assert (
                "Model parameter is required" in response_data["content"] or "Model 'auto'" in response_data["content"]
            )
            assert "flash" in response_data["content"]

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
    async def test_actual_model_name_resolution_in_auto_mode(self, tmp_path):
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
                workdir = tmp_path / "chat_artifacts"
                workdir.mkdir(parents=True, exist_ok=True)
                result = await chat_tool.execute(
                    {"prompt": "test", "model": "flash", "working_directory_absolute_path": str(workdir)}
                )  # Use alias in auto mode

                # Should succeed with proper model resolution
                assert len(result) == 1
                # Just verify that the tool executed successfully and didn't return an error
                assert "error" not in result[0].text.lower()
