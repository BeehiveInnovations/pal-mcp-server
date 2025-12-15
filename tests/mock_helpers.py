"""Helper functions for test mocking."""

from unittest.mock import Mock

from providers.shared import ModelCapabilities, ProviderType, RangeTemperatureConstraint


def create_mock_provider(model_name="gemini-2.5-flash", context_window=1_048_576):
    """Create a properly configured mock provider.

    Uses spec to limit available methods - this ensures that hasattr() checks
    for optional provider methods (like _calculate_text_tokens) return False,
    allowing ModelContext to fall back to default token estimation logic.
    """
    mock_provider = Mock(
        spec=[
            "get_capabilities",
            "get_provider_type",
            "validate_model_name",
            "generate_content",
        ]
    )

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
