"""
Simple test to verify GitHub issue #245 is fixed.

Issue: Custom OpenAI models (gpt-5, o3) use temperature despite the config having supports_temperature: false
"""

from unittest.mock import Mock, patch

from providers.openai_provider import OpenAIModelProvider


def test_issue_245_custom_openai_temperature_ignored():
    """Test that reproduces and validates the fix for issue #245."""

    with patch("utils.model_restrictions.get_restriction_service") as mock_restriction:
        with patch("providers.openai_compatible.OpenAI") as mock_openai:
            with patch("providers.openrouter_registry.OpenRouterModelRegistry") as mock_registry_class:

                # Mock restriction service
                mock_service = Mock()
                mock_service.is_allowed.return_value = True
                mock_restriction.return_value = mock_service

                # Mock OpenAI client
                mock_client = Mock()
                mock_openai.return_value = mock_client
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "Test response"
                mock_response.choices[0].finish_reason = "stop"
                mock_response.model = "gpt-5-2025-08-07"
                mock_response.id = "test"
                mock_response.created = 123
                mock_response.usage = Mock()
                mock_response.usage.prompt_tokens = 10
                mock_response.usage.completion_tokens = 5
                mock_response.usage.total_tokens = 15
                mock_client.chat.completions.create.return_value = mock_response

                # Mock registry with user's custom config (the issue scenario)
                mock_registry = Mock()
                mock_registry_class.return_value = mock_registry

                from providers.base import ModelCapabilities, ProviderType, create_temperature_constraint

                # This is what the user configured in their custom_models.json
                custom_config = ModelCapabilities(
                    provider=ProviderType.OPENAI,
                    model_name="gpt-5-2025-08-07",
                    friendly_name="Custom GPT-5",
                    context_window=400000,
                    max_output_tokens=128000,
                    supports_extended_thinking=True,
                    supports_json_mode=True,
                    supports_system_prompts=True,
                    supports_streaming=True,
                    supports_function_calling=True,
                    supports_temperature=False,  # User set this to false!
                    temperature_constraint=create_temperature_constraint("fixed"),
                    supports_images=True,
                    max_image_size_mb=20.0,
                    description="Custom OpenAI GPT-5",
                )
                mock_registry.get_model_config.return_value = custom_config

                # Create provider and test
                provider = OpenAIModelProvider(api_key="test-key")
                provider.validate_model_name = lambda name: True

                # This is what was causing the 400 error before the fix
                provider.generate_content(
                    prompt="Test", model_name="gpt-5-2025-08-07", temperature=0.2  # This should be ignored!
                )

                # Verify the fix: NO temperature should be sent to the API
                call_kwargs = mock_client.chat.completions.create.call_args[1]
                assert "temperature" not in call_kwargs, "Fix failed: temperature still being sent!"
