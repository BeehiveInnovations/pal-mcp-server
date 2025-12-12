"""Unit tests for Gemini OpenAI-compatible mode."""

from unittest.mock import Mock, patch

import pytest

from providers.gemini import GeminiModelProvider
from providers.shared import ModelResponse, ProviderType


class TestGeminiOpenAICompatMode:
    """Test Gemini provider's OpenAI-compatible mode."""

    def test_should_use_openai_compatible_with_v1_suffix(self):
        """Test auto-detection when base_url ends with /v1."""
        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com/v1")
        assert provider._use_openai_compatible is True

    def test_should_use_openai_compatible_without_v1_suffix(self):
        """Test native mode when base_url does not end with /v1."""
        provider = GeminiModelProvider(api_key="test-key", base_url="https://generativelanguage.googleapis.com")
        assert provider._use_openai_compatible is False

    @patch.dict("os.environ", {"GEMINI_USE_OPENAI_COMPATIBLE": "true"})
    def test_should_use_openai_compatible_with_env_var(self):
        """Test explicit environment variable triggers OpenAI-compatible mode."""
        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com")
        assert provider._use_openai_compatible is True

    def test_openai_client_raises_error_in_native_mode(self):
        """Test accessing openai_client in native mode raises error."""
        provider = GeminiModelProvider(api_key="test-key", base_url="https://generativelanguage.googleapis.com")

        with pytest.raises(RuntimeError, match="not in OpenAI-compatible mode"):
            _ = provider.openai_client

    @patch("providers.gemini.OpenAI")
    def test_openai_client_initialization(self, mock_openai_class):
        """Test OpenAI client is properly initialized."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com/v1")

        # Access openai_client to trigger initialization
        client = provider.openai_client

        # Verify OpenAI was called with correct parameters
        mock_openai_class.assert_called_once()
        call_kwargs = mock_openai_class.call_args[1]
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["base_url"] == "https://api.example.com/v1"
        assert "timeout" in call_kwargs
        assert client == mock_client

    @patch("providers.gemini.OpenAI")
    def test_generate_content_openai_compatible_success(self, mock_openai_class):
        """Test successful API call in OpenAI-compatible mode."""
        # Setup mock OpenAI client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the API response
        mock_choice = Mock()
        mock_choice.message.content = "Test response"
        mock_choice.finish_reason = "stop"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client.chat.completions.create.return_value = mock_response

        # Create provider and call generate_content
        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com/v1")

        result = provider.generate_content(
            prompt="Test prompt", model_name="gemini-2.5-flash", system_prompt="System prompt", temperature=0.7
        )

        # Verify the result
        assert isinstance(result, ModelResponse)
        assert result.content == "Test response"
        assert result.usage["input_tokens"] == 10
        assert result.usage["output_tokens"] == 20
        assert result.usage["total_tokens"] == 30
        assert result.model_name == "gemini-2.5-flash"
        assert result.friendly_name == "Gemini"
        assert result.provider == ProviderType.GOOGLE
        assert result.metadata["mode"] == "openai_compatible"
        assert result.metadata["finish_reason"] == "stop"

    @patch("providers.gemini.OpenAI")
    def test_generate_content_empty_choices_raises_error(self, mock_openai_class):
        """Test that empty choices list raises RuntimeError."""
        # Setup mock OpenAI client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock response with empty choices
        mock_response = Mock()
        mock_response.choices = []

        mock_client.chat.completions.create.return_value = mock_response

        # Create provider
        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com/v1")

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="API returned empty choices"):
            provider.generate_content(prompt="Test prompt", model_name="gemini-2.5-flash")

    @patch("providers.gemini.OpenAI")
    def test_generate_content_usage_field_mapping(self, mock_openai_class):
        """Test usage field correctly maps prompt_tokens to input_tokens."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 200
        mock_usage.total_tokens = 300

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client.chat.completions.create.return_value = mock_response

        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com/v1")

        result = provider.generate_content(prompt="Test", model_name="gemini-2.5-pro")

        # Verify field mapping
        assert "input_tokens" in result.usage
        assert "output_tokens" in result.usage
        assert "total_tokens" in result.usage
        assert result.usage["input_tokens"] == 100
        assert result.usage["output_tokens"] == 200

    @patch("providers.gemini.OpenAI")
    def test_generate_content_none_usage_defaults_to_zero(self, mock_openai_class):
        """Test that None usage returns default zeros."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        mock_client.chat.completions.create.return_value = mock_response

        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com/v1")

        result = provider.generate_content(prompt="Test", model_name="gemini-2.5-flash")

        # Verify default values
        assert result.usage["input_tokens"] == 0
        assert result.usage["output_tokens"] == 0
        assert result.usage["total_tokens"] == 0

    @patch("providers.gemini.OpenAI")
    def test_generate_content_api_parameters(self, mock_openai_class):
        """Test that correct parameters are passed to OpenAI API."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        mock_client.chat.completions.create.return_value = mock_response

        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com/v1")

        provider.generate_content(
            prompt="User prompt",
            model_name="gemini-2.5-pro",
            system_prompt="System instruction",
            temperature=0.8,
            max_output_tokens=1000,
        )

        # Verify API was called with correct parameters
        call_args = mock_client.chat.completions.create.call_args[1]
        assert call_args["model"] == "gemini-2.5-pro"
        assert call_args["temperature"] == 0.8
        assert call_args["max_tokens"] == 1000
        assert len(call_args["messages"]) == 2
        assert call_args["messages"][0]["role"] == "system"
        assert call_args["messages"][0]["content"] == "System instruction"
        assert call_args["messages"][1]["role"] == "user"
        assert call_args["messages"][1]["content"] == "User prompt"

    def test_native_mode_still_works(self):
        """Test that native mode is not affected by OpenAI-compatible changes."""
        provider = GeminiModelProvider(
            api_key="test-key"
            # No base_url, should use native mode
        )

        assert provider._use_openai_compatible is False
        assert provider._client is None  # Not initialized yet
        # Native client should be accessible without errors
        assert hasattr(provider, "client")

    @patch("providers.gemini.OpenAI")
    def test_warns_about_ignored_images_parameter(self, mock_openai_class):
        """Test that images parameter triggers warning in OpenAI-compatible mode."""
        # Setup mock OpenAI client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        mock_client.chat.completions.create.return_value = mock_response

        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com/v1")

        # Call with images parameter
        with patch("providers.gemini.logger") as mock_logger:
            provider.generate_content(prompt="Test", model_name="gemini-2.5-flash", images=["image1.png", "image2.png"])

            # Verify warning was logged
            mock_logger.warning.assert_called()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "Images are not supported" in warning_call
            assert "will be ignored" in warning_call

    @patch("providers.gemini.OpenAI")
    def test_warns_about_ignored_thinking_mode_parameter(self, mock_openai_class):
        """Test that non-default thinking_mode triggers warning in OpenAI-compatible mode."""
        # Setup mock OpenAI client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        mock_client.chat.completions.create.return_value = mock_response

        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com/v1")

        # Call with non-default thinking_mode
        with patch("providers.gemini.logger") as mock_logger:
            provider.generate_content(prompt="Test", model_name="gemini-2.5-flash", thinking_mode="high")

            # Verify warning was logged
            mock_logger.warning.assert_called()
            warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
            assert any("thinking_mode" in call and "will be ignored" in call for call in warning_calls)

    @patch("providers.gemini.OpenAI")
    def test_no_warning_for_default_thinking_mode(self, mock_openai_class):
        """Test that default thinking_mode does not trigger warning."""
        # Setup mock OpenAI client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        mock_client.chat.completions.create.return_value = mock_response

        provider = GeminiModelProvider(api_key="test-key", base_url="https://api.example.com/v1")

        # Call with default thinking_mode
        with patch("providers.gemini.logger") as mock_logger:
            provider.generate_content(prompt="Test", model_name="gemini-2.5-flash", thinking_mode="medium")

            # Verify no thinking_mode warning was logged
            warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
            assert not any("thinking_mode" in call for call in warning_calls)
