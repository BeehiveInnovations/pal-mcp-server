"""Test listmodels tool respects model restrictions."""

import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch

from providers.base import ModelProvider
from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from tools.listmodels import ListModelsTool


class TestListModelsRestrictions(unittest.TestCase):
    """Test that listmodels respects OPENROUTER_ALLOWED_MODELS."""

    def setUp(self):
        """Set up test environment."""
        # Clear any existing registry state
        ModelProviderRegistry.clear_cache()

        # Create mock OpenRouter provider
        self.mock_openrouter = MagicMock(spec=ModelProvider)
        self.mock_openrouter.provider_type = ProviderType.OPENROUTER

        # Create mock Gemini provider for comparison
        self.mock_gemini = MagicMock(spec=ModelProvider)
        self.mock_gemini.provider_type = ProviderType.GOOGLE
        self.mock_gemini.list_models.return_value = ["gemini-2.5-flash", "gemini-2.5-pro"]

    def tearDown(self):
        """Clean up after tests."""
        ModelProviderRegistry.clear_cache()
        # Clean up environment variables
        for key in ["OPENROUTER_ALLOWED_MODELS", "OPENROUTER_API_KEY", "GEMINI_API_KEY"]:
            os.environ.pop(key, None)

    @patch.dict(
        os.environ,
        {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_ALLOWED_MODELS": "opus,sonnet,deepseek/deepseek-r1-0528:free,qwen/qwen3-235b-a22b-04-28:free",
            "GEMINI_API_KEY": "gemini-test-key",
        },
    )
    @patch("utils.model_restrictions.get_restriction_service")
    @patch("providers.openrouter_registry.OpenRouterModelRegistry")
    @patch.object(ModelProviderRegistry, "get_available_models")
    @patch.object(ModelProviderRegistry, "get_provider")
    def test_listmodels_respects_openrouter_restrictions(
        self, mock_get_provider, mock_get_models, mock_registry_class, mock_get_restriction
    ):
        """Test that listmodels only shows allowed OpenRouter models."""
        # Set up mock to return only allowed models when restrictions are respected
        # Include both aliased models and full model names without aliases
        self.mock_openrouter.list_models.return_value = [
            "anthropic/claude-opus-4",  # Has alias "opus"
            "anthropic/claude-sonnet-4",  # Has alias "sonnet"
            "deepseek/deepseek-r1-0528:free",  # No alias, full name
            "qwen/qwen3-235b-a22b-04-28:free",  # No alias, full name
        ]

        # Mock registry instance
        mock_registry = MagicMock()
        mock_registry_class.return_value = mock_registry

        # Mock resolve method - return config for aliased models, None for others
        def resolve_side_effect(model_name):
            if "opus" in model_name.lower():
                config = MagicMock()
                config.model_name = "anthropic/claude-opus-4-20240229"
                config.context_window = 200000
                config.get_effective_capability_rank.return_value = 90  # High rank for Opus
                return config
            elif "sonnet" in model_name.lower():
                config = MagicMock()
                config.model_name = "anthropic/claude-sonnet-4-20240229"
                config.context_window = 200000
                config.get_effective_capability_rank.return_value = 80  # Lower rank for Sonnet
                return config
            elif "deepseek" in model_name.lower():
                config = MagicMock()
                config.model_name = "deepseek/deepseek-r1-0528:free"
                config.context_window = 100000
                config.get_effective_capability_rank.return_value = 70
                return config
            elif "qwen" in model_name.lower():
                config = MagicMock()
                config.model_name = "qwen/qwen3-235b-a22b-04-28:free"
                config.context_window = 100000
                config.get_effective_capability_rank.return_value = 60
                return config
            return None  # No config for models without aliases

        mock_registry.resolve.side_effect = resolve_side_effect

        # Mock provider registry
        def get_provider_side_effect(provider_type, force_new=False):
            if provider_type == ProviderType.OPENROUTER:
                return self.mock_openrouter
            elif provider_type == ProviderType.GOOGLE:
                return self.mock_gemini
            return None

        mock_get_provider.side_effect = get_provider_side_effect

        # Ensure registry is cleared before test
        ModelProviderRegistry._registry = {}

        # Mock available models
        mock_get_models.return_value = {
            "gemini-2.5-flash": ProviderType.GOOGLE,
            "gemini-2.5-pro": ProviderType.GOOGLE,
            "anthropic/claude-opus-4-20240229": ProviderType.OPENROUTER,
            "anthropic/claude-sonnet-4-20240229": ProviderType.OPENROUTER,
            "deepseek/deepseek-r1-0528:free": ProviderType.OPENROUTER,
            "qwen/qwen3-235b-a22b-04-28:free": ProviderType.OPENROUTER,
        }

        # Mock restriction service
        mock_restriction_service = MagicMock()
        mock_restriction_service.has_restrictions.return_value = True
        mock_restriction_service.get_allowed_models.return_value = {
            "opus",
            "sonnet",
            "deepseek/deepseek-r1-0528:free",
            "qwen/qwen3-235b-a22b-04-28:free",
        }
        mock_get_restriction.return_value = mock_restriction_service

        # Create tool and execute
        tool = ListModelsTool()
        # Execute asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result_contents = loop.run_until_complete(tool.execute({}))
        loop.close()

        # Extract text content from result
        result_text = result_contents[0].text

        # Parse JSON response
        import json

        result_json = json.loads(result_text)
        result = result_json["content"]

        # Parse the output
        lines = result.split("\n")

        # Debug: print the actual result for troubleshooting
        # print(f"DEBUG: Full result:\n{result}")

        # Check that OpenRouter section exists
        openrouter_section_found = False
        openrouter_models = []
        in_openrouter_section = False

        for line in lines:
            if "OpenRouter" in line and "✅" in line:
                openrouter_section_found = True
            elif "Available Models" in line and openrouter_section_found:
                in_openrouter_section = True
            elif in_openrouter_section:
                # Check for lines with model names in backticks
                # Format: - `model-name` (score X)
                if line.strip().startswith("- ") and "`" in line:
                    # Extract model name between backticks
                    parts = line.split("`")
                    if len(parts) >= 2:
                        model_name = parts[1]
                        openrouter_models.append(model_name)
                # Stop parsing when we hit the next section
                elif "##" in line and in_openrouter_section:
                    break

        self.assertTrue(openrouter_section_found, "OpenRouter section not found")
        self.assertEqual(
            len(openrouter_models), 4, f"Expected 4 models, got {len(openrouter_models)}: {openrouter_models}"
        )

        # Verify list_models was called with respect_restrictions=True
        self.mock_openrouter.list_models.assert_called_with(respect_restrictions=True)

        # Check for restriction note
        self.assertIn("Restricted to models matching:", result)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key", "GEMINI_API_KEY": "gemini-test-key"}, clear=True)
    @patch("providers.openrouter_registry.OpenRouterModelRegistry")
    @patch.object(ModelProviderRegistry, "get_provider")
    def test_listmodels_shows_all_models_without_restrictions(self, mock_get_provider, mock_registry_class):
        """Test that listmodels shows all models when no restrictions are set."""
        # Clear any cached restriction service to ensure it reads from patched environment
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # Set up mock to return many models when no restrictions
        all_models = [f"provider{i // 10}/model-{i}" for i in range(50)]  # Simulate 50 models from different providers
        self.mock_openrouter.list_models.return_value = all_models

        # Mock registry instance
        mock_registry = MagicMock()
        mock_registry_class.return_value = mock_registry
        mock_registry.resolve.return_value = None  # No configs for simplicity

        # Mock provider registry
        def get_provider_side_effect(provider_type, force_new=False):
            if provider_type == ProviderType.OPENROUTER:
                return self.mock_openrouter
            elif provider_type == ProviderType.GOOGLE:
                return self.mock_gemini
            return None

        mock_get_provider.side_effect = get_provider_side_effect

        # Create tool and execute
        tool = ListModelsTool()
        # Execute asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result_contents = loop.run_until_complete(tool.execute({}))
        loop.close()

        # Extract text content from result
        result_text = result_contents[0].text

        # Parse JSON response
        import json

        result_json = json.loads(result_text)
        result = result_json["content"]

        # Count OpenRouter models specifically
        lines = result.split("\n")
        openrouter_section_found = False
        openrouter_model_count = 0

        for line in lines:
            if "OpenRouter" in line and "✅" in line:
                openrouter_section_found = True
            elif "Custom/Local API" in line:
                # End of OpenRouter section
                break
            elif openrouter_section_found and line.strip().startswith("- ") and "`" in line:
                openrouter_model_count += 1

        # After removing limits, the tool shows ALL available models (no truncation)
        # With 50 models from providers, we expect to see ALL of them
        self.assertGreaterEqual(
            openrouter_model_count,
            30,
            f"Expected to see many OpenRouter models (no limits), found {openrouter_model_count}",
        )

        # Should NOT show "and X more models available" message since we show all models now
        self.assertNotIn("more models available", result)

        # Verify list_models was called with respect_restrictions=True
        # (even without restrictions, we always pass True)
        self.mock_openrouter.list_models.assert_called_with(respect_restrictions=True)

        # Should NOT have restriction note when no restrictions are set
        self.assertNotIn("Restricted to models matching:", result)


if __name__ == "__main__":
    unittest.main()
