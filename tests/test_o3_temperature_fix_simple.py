"""
Simple integration test for the O3 model temperature parameter fix.

This test confirms that the fix properly excludes temperature parameters
for O3 models while maintaining them for regular models.
"""

from unittest.mock import Mock, patch

from providers.openai_provider import OpenAIModelProvider


class TestO3TemperatureParameterFixSimple:
    """Simple test for O3 model parameter filtering."""

    @patch("utils.model_restrictions.get_restriction_service")
    @patch("providers.openai_compatible.OpenAI")
    def test_o3_models_exclude_temperature_from_api_call(self, mock_openai_class, mock_restriction_service):
        """Test that O3 models don't send temperature to the API."""
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
        mock_response.model = "o3-mini"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        # Create provider
        provider = OpenAIModelProvider(api_key="test-key")

        # Override _resolve_model_name to return the resolved model name
        provider._resolve_model_name = lambda name: name
        # Override model validation to bypass restrictions
        provider.validate_model_name = lambda name: True

        # Call generate_content with O3 model
        provider.generate_content(prompt="Test prompt", model_name="o3-mini", temperature=0.5, max_output_tokens=100)

        # Verify the API call was made without temperature or max_tokens
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        assert "temperature" not in call_kwargs, "O3 models should not include temperature parameter"
        assert "max_tokens" not in call_kwargs, "O3 models should not include max_tokens parameter"
        assert call_kwargs["model"] == "o3-mini"
        assert "messages" in call_kwargs

    @patch("utils.model_restrictions.get_restriction_service")
    @patch("providers.openai_compatible.OpenAI")
    def test_regular_models_include_temperature_in_api_call(self, mock_openai_class, mock_restriction_service):
        """Test that regular models still send temperature to the API."""
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
        mock_response.model = "gpt-4.1-2025-04-14"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        # Create provider
        provider = OpenAIModelProvider(api_key="test-key")

        # Override _resolve_model_name to return the resolved model name
        provider._resolve_model_name = lambda name: name
        # Override model validation to bypass restrictions
        provider.validate_model_name = lambda name: True

        # Call generate_content with regular model (use supported model)
        provider.generate_content(
            prompt="Test prompt", model_name="gpt-4.1-2025-04-14", temperature=0.5, max_output_tokens=100
        )

        # Verify the API call was made WITH temperature and max_tokens
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        assert call_kwargs["temperature"] == 0.5, "Regular models should include temperature parameter"
        assert call_kwargs["max_tokens"] == 100, "Regular models should include max_tokens parameter"
        assert call_kwargs["model"] == "gpt-4.1-2025-04-14"

    @patch("utils.model_restrictions.get_restriction_service")
    @patch("providers.openai_compatible.OpenAI")
    def test_o3_models_filter_unsupported_parameters(self, mock_openai_class, mock_restriction_service):
        """Test that O3 models filter out top_p, frequency_penalty, etc."""
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
        mock_response.model = "o3"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        # Create provider
        provider = OpenAIModelProvider(api_key="test-key")

        # Override _resolve_model_name to return the resolved model name
        provider._resolve_model_name = lambda name: name
        # Override model validation to bypass restrictions
        provider.validate_model_name = lambda name: True

        # Call generate_content with O3 model and unsupported parameters
        provider.generate_content(
            prompt="Test prompt",
            model_name="o3",
            temperature=0.5,
            top_p=0.9,
            frequency_penalty=0.1,
            presence_penalty=0.1,
            seed=42,
            stop=["END"],
        )

        # Verify the API call filters out unsupported parameters
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # Should be excluded for O3 models
        assert "temperature" not in call_kwargs, "O3 should not include temperature"
        assert "top_p" not in call_kwargs, "O3 should not include top_p"
        assert "frequency_penalty" not in call_kwargs, "O3 should not include frequency_penalty"
        assert "presence_penalty" not in call_kwargs, "O3 should not include presence_penalty"

        # Should be included (supported parameters)
        assert call_kwargs["seed"] == 42, "O3 should include seed parameter"
        assert call_kwargs["stop"] == ["END"], "O3 should include stop parameter"

    @patch("utils.model_restrictions.get_restriction_service")
    def test_all_o3_models_have_correct_temperature_capability(self, mock_restriction_service):
        """Test that all O3/O4 models have supports_temperature=False in their capabilities."""
        from providers.openai_provider import OpenAIModelProvider

        # Mock restriction service to allow all models
        mock_service = Mock()
        mock_service.is_allowed.return_value = True
        mock_restriction_service.return_value = mock_service

        provider = OpenAIModelProvider(api_key="test-key")

        # Test O3/O4 models that should NOT support temperature parameter
        o3_o4_models = ["o3", "o3-mini", "o3-pro", "o4-mini"]

        for model in o3_o4_models:
            capabilities = provider.get_capabilities(model)
            assert hasattr(
                capabilities, "supports_temperature"
            ), f"Model {model} capabilities should have supports_temperature field"
            assert capabilities.supports_temperature is False, f"Model {model} should have supports_temperature=False"

        # Test that regular models DO support temperature parameter
        regular_models = ["gpt-4.1-2025-04-14"]

        for model in regular_models:
            try:
                capabilities = provider.get_capabilities(model)
                assert hasattr(
                    capabilities, "supports_temperature"
                ), f"Model {model} capabilities should have supports_temperature field"
                assert capabilities.supports_temperature is True, f"Model {model} should have supports_temperature=True"
            except ValueError:
                # Skip if model not in SUPPORTED_MODELS (that's okay for this test)
                pass

    @patch("utils.model_restrictions.get_restriction_service")
    def test_openai_provider_temperature_constraints(self, mock_restriction_service):
        """Test that OpenAI provider has correct temperature constraints for O3 models."""
        from providers.openai_provider import OpenAIModelProvider

        # Mock restriction service to allow all models
        mock_service = Mock()
        mock_service.is_allowed.return_value = True
        mock_restriction_service.return_value = mock_service

        provider = OpenAIModelProvider(api_key="test-key")

        # Test O3 model constraints
        o3_capabilities = provider.get_capabilities("o3-mini")
        assert o3_capabilities.temperature_constraint is not None

        # O3 models should have fixed temperature constraint
        temp_constraint = o3_capabilities.temperature_constraint
        assert temp_constraint.validate(1.0) is True
        assert temp_constraint.validate(0.5) is False

        # Test regular model constraints - use gpt-4.1 which is supported
        gpt41_capabilities = provider.get_capabilities("gpt-4.1-2025-04-14")
        assert gpt41_capabilities.temperature_constraint is not None

        # Regular models should allow a range
        temp_constraint = gpt41_capabilities.temperature_constraint
        assert temp_constraint.validate(0.5) is True
        assert temp_constraint.validate(1.0) is True
