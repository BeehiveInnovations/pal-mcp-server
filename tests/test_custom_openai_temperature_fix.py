"""
Test for custom OpenAI models temperature parameter fix.

This test verifies that custom OpenAI models configured through custom_models.json
with supports_temperature=false do not send temperature parameters to the API.
This addresses issue #245.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from providers.openai_provider import OpenAIModelProvider


class TestCustomOpenAITemperatureParameterFix:
    """Test custom OpenAI model parameter filtering."""

    def _create_test_config(self, models_config: list[dict]) -> str:
        """Create a temporary config file for testing."""
        config = {"_README": {"description": "Test config"}, "models": models_config}

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(config, temp_file, indent=2)
        temp_file.close()
        return temp_file.name

    @patch("utils.model_restrictions.get_restriction_service")
    @patch("providers.openai_compatible.OpenAI")
    def test_custom_openai_models_exclude_temperature_from_api_call(self, mock_openai_class, mock_restriction_service):
        """Test that custom OpenAI models with supports_temperature=false don't send temperature to the API."""
        # Create test config with a custom OpenAI model that doesn't support temperature
        config_models = [
            {
                "model_name": "gpt-5-2025-08-07",
                "provider": "ProviderType.OPENAI",
                "is_custom": True,
                "context_window": 400000,
                "max_output_tokens": 128000,
                "supports_extended_thinking": True,
                "supports_json_mode": True,
                "supports_system_prompts": True,
                "supports_streaming": True,
                "supports_function_calling": True,
                "supports_temperature": False,
                "temperature_constraint": "fixed",
                "supports_images": True,
                "max_image_size_mb": 20.0,
                "reasoning": {"effort": "low"},
                "description": "Custom OpenAI GPT-5 test model",
            }
        ]

        config_path = self._create_test_config(config_models)

        try:
            # Mock restriction service to allow all models
            mock_service = Mock()
            mock_service.is_allowed.return_value = True
            mock_restriction_service.return_value = mock_service

            # Setup mock client
            mock_client = Mock()
            mock_openai_class.return_value = mock_client

            # Setup mock response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].finish_reason = "stop"
            mock_response.model = "gpt-5-2025-08-07"
            mock_response.id = "test-id"
            mock_response.created = 1234567890
            mock_response.usage = Mock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5
            mock_response.usage.total_tokens = 15

            mock_client.chat.completions.create.return_value = mock_response

            # Create provider with custom config
            with patch("providers.openrouter_registry.OpenRouterModelRegistry") as mock_registry_class:
                # Mock registry to load our test config
                mock_registry = Mock()
                mock_registry_class.return_value = mock_registry

                # Mock get_model_config to return our test model
                from providers.base import ModelCapabilities, ProviderType, create_temperature_constraint

                test_capabilities = ModelCapabilities(
                    provider=ProviderType.OPENAI,
                    model_name="gpt-5-2025-08-07",
                    friendly_name="Custom GPT-5",
                    context_window=400000,
                    max_output_tokens=128000,
                    supports_extended_thinking=True,
                    supports_system_prompts=True,
                    supports_streaming=True,
                    supports_function_calling=True,
                    supports_json_mode=True,
                    supports_images=True,
                    max_image_size_mb=20.0,
                    supports_temperature=False,  # This is the key setting
                    temperature_constraint=create_temperature_constraint("fixed"),
                    description="Custom OpenAI GPT-5 test model",
                )

                mock_registry.get_model_config.return_value = test_capabilities

                provider = OpenAIModelProvider(api_key="test-key")

                # Override model validation to bypass restrictions
                provider.validate_model_name = lambda name: True

                # Call generate_content with custom model
                provider.generate_content(
                    prompt="Test prompt", model_name="gpt-5-2025-08-07", temperature=0.5, max_output_tokens=100
                )

                # Verify the API call was made without temperature or max_tokens
                mock_client.chat.completions.create.assert_called_once()
                call_kwargs = mock_client.chat.completions.create.call_args[1]

                assert (
                    "temperature" not in call_kwargs
                ), "Custom OpenAI models with supports_temperature=false should not include temperature parameter"
                assert (
                    "max_tokens" not in call_kwargs
                ), "Custom OpenAI models with supports_temperature=false should not include max_tokens parameter"
                assert call_kwargs["model"] == "gpt-5-2025-08-07"
                assert "messages" in call_kwargs

        finally:
            # Clean up temp file
            Path(config_path).unlink(missing_ok=True)

    @patch("utils.model_restrictions.get_restriction_service")
    @patch("providers.openai_compatible.OpenAI")
    def test_custom_openai_models_include_temperature_when_supported(self, mock_openai_class, mock_restriction_service):
        """Test that custom OpenAI models with supports_temperature=true still send temperature to the API."""
        # Mock restriction service to allow all models
        mock_service = Mock()
        mock_service.is_allowed.return_value = True
        mock_restriction_service.return_value = mock_service

        # Setup mock client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Setup mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4-custom"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        # Create provider with custom config
        with patch("providers.openrouter_registry.OpenRouterModelRegistry") as mock_registry_class:
            # Mock registry to load our test config
            mock_registry = Mock()
            mock_registry_class.return_value = mock_registry

            # Mock get_model_config to return a model that supports temperature
            from providers.base import ModelCapabilities, ProviderType, create_temperature_constraint

            test_capabilities = ModelCapabilities(
                provider=ProviderType.OPENAI,
                model_name="gpt-4-custom",
                friendly_name="Custom GPT-4",
                context_window=128000,
                max_output_tokens=32000,
                supports_extended_thinking=False,
                supports_system_prompts=True,
                supports_streaming=True,
                supports_function_calling=True,
                supports_json_mode=True,
                supports_images=True,
                max_image_size_mb=20.0,
                supports_temperature=True,  # This model DOES support temperature
                temperature_constraint=create_temperature_constraint("range"),
                description="Custom OpenAI GPT-4 test model",
            )

            mock_registry.get_model_config.return_value = test_capabilities

            provider = OpenAIModelProvider(api_key="test-key")

            # Override model validation to bypass restrictions
            provider.validate_model_name = lambda name: True

            # Call generate_content with custom model that supports temperature
            provider.generate_content(
                prompt="Test prompt", model_name="gpt-4-custom", temperature=0.5, max_output_tokens=100
            )

            # Verify the API call was made WITH temperature and max_tokens
            mock_client.chat.completions.create.assert_called_once()
            call_kwargs = mock_client.chat.completions.create.call_args[1]

            assert (
                call_kwargs["temperature"] == 0.5
            ), "Custom OpenAI models with supports_temperature=true should include temperature parameter"
            assert (
                call_kwargs["max_tokens"] == 100
            ), "Custom OpenAI models with supports_temperature=true should include max_tokens parameter"
            assert call_kwargs["model"] == "gpt-4-custom"

    @patch("utils.model_restrictions.get_restriction_service")
    def test_custom_openai_model_validation(self, mock_restriction_service):
        """Test that custom OpenAI models are properly validated."""
        # Mock restriction service to allow all models
        mock_service = Mock()
        mock_service.is_allowed.return_value = True
        mock_restriction_service.return_value = mock_service

        with patch("providers.openrouter_registry.OpenRouterModelRegistry") as mock_registry_class:
            # Mock registry to return a custom OpenAI model
            mock_registry = Mock()
            mock_registry_class.return_value = mock_registry

            from providers.base import ModelCapabilities, ProviderType, create_temperature_constraint

            test_capabilities = ModelCapabilities(
                provider=ProviderType.OPENAI,
                model_name="o3-2025-04-16",
                friendly_name="Custom O3",
                context_window=200000,
                max_output_tokens=65536,
                supports_extended_thinking=False,
                supports_system_prompts=True,
                supports_streaming=True,
                supports_function_calling=True,
                supports_json_mode=True,
                supports_images=True,
                max_image_size_mb=20.0,
                supports_temperature=False,
                temperature_constraint=create_temperature_constraint("fixed"),
                description="Custom OpenAI O3 test model",
            )

            mock_registry.get_model_config.return_value = test_capabilities

            provider = OpenAIModelProvider(api_key="test-key")

            # Test that custom model validates successfully
            assert provider.validate_model_name("o3-2025-04-16") is True

            # Test that get_capabilities returns the custom config
            capabilities = provider.get_capabilities("o3-2025-04-16")
            assert capabilities.supports_temperature is False
            assert capabilities.model_name == "o3-2025-04-16"
            assert capabilities.provider == ProviderType.OPENAI

    @patch("utils.model_restrictions.get_restriction_service")
    def test_fallback_to_builtin_models_when_registry_fails(self, mock_restriction_service):
        """Test that provider falls back to built-in models when registry fails."""
        # Mock restriction service to allow all models
        mock_service = Mock()
        mock_service.is_allowed.return_value = True
        mock_restriction_service.return_value = mock_service

        with patch("providers.openrouter_registry.OpenRouterModelRegistry") as mock_registry_class:
            # Mock registry to raise an exception
            mock_registry_class.side_effect = Exception("Registry not available")

            provider = OpenAIModelProvider(api_key="test-key")

            # Test that built-in models still work
            assert provider.validate_model_name("o3-mini") is True

            # Test that unsupported models return false
            assert provider.validate_model_name("unknown-model") is False
