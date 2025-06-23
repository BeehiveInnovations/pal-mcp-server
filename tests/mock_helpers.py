"""Helper functions for test mocking."""

from unittest.mock import Mock

from providers.base import ModelCapabilities, ProviderType, RangeTemperatureConstraint


def create_mock_provider(model_name="gemini-2.5-flash", context_window=1_048_576):
    """Create a properly configured mock provider."""
    mock_provider = Mock()

    # Set up capabilities
    mock_capabilities = ModelCapabilities(
        provider=ProviderType.GOOGLE,
        model_name=model_name,
        friendly_name="Gemini",
        context_window=context_window,
        max_output_tokens=8192,
        supports_extended_thinking=False,
        supports_system_prompts=True,
        supports_streaming=True,
        supports_function_calling=True,
        temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 0.7),
    )

    mock_provider.get_capabilities.return_value = mock_capabilities
    mock_provider.get_provider_type.return_value = ProviderType.GOOGLE
    mock_provider.supports_thinking_mode.return_value = False
    mock_provider.validate_model_name.return_value = True

    # Set up generate_content response
    mock_response = Mock()
    mock_response.content = "Test response"
    mock_response.usage = {"input_tokens": 10, "output_tokens": 20}
    mock_response.model_name = model_name
    mock_response.friendly_name = "Gemini"
    mock_response.provider = ProviderType.GOOGLE
    mock_response.metadata = {"finish_reason": "STOP"}

    mock_provider.generate_content.return_value = mock_response

    return mock_provider
