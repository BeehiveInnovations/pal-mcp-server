"""Tests for OpenAI provider implementation."""

import os
from unittest.mock import MagicMock, patch

import pytest

from providers.openai import OpenAIModelProvider
from providers.shared import ProviderType


class TestOpenAIProvider:
    """Test OpenAI provider functionality."""

    def setup_method(self):
        """Set up clean state before each test."""
        # Clear restriction service cache before each test
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def teardown_method(self):
        """Clean up after each test to avoid singleton issues."""
        # Clear restriction service cache after each test
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        provider = OpenAIModelProvider("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.OPENAI
        assert provider.base_url == "https://api.openai.com/v1"
        # Verify OpenAIResponsesProvider is properly initialized
        assert provider.responses_provider is not None
        assert provider.responses_provider.__class__.__name__ == "OpenAIResponsesProvider"

    def test_initialization_with_custom_url(self):
        """Test provider initialization with custom base URL."""
        provider = OpenAIModelProvider("test-key", base_url="https://custom.openai.com/v1")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.openai.com/v1"

    def test_model_validation(self):
        """Test model name validation."""
        provider = OpenAIModelProvider("test-key")

        # Test valid models
        assert provider.validate_model_name("o3") is True
        assert provider.validate_model_name("o3-mini") is True
        assert provider.validate_model_name("o3-pro") is True
        assert provider.validate_model_name("o4-mini") is True
        assert provider.validate_model_name("o4-mini") is True
        assert provider.validate_model_name("gpt-5") is True
        assert provider.validate_model_name("gpt-5-mini") is True
        assert provider.validate_model_name("gpt-5.2") is True
        assert provider.validate_model_name("gpt-5.1-codex") is True
        assert provider.validate_model_name("gpt-5.1-codex-mini") is True

        # Test valid aliases
        assert provider.validate_model_name("mini") is True
        assert provider.validate_model_name("o3mini") is True
        assert provider.validate_model_name("o4mini") is True
        assert provider.validate_model_name("o4mini") is True
        assert provider.validate_model_name("gpt5") is True
        assert provider.validate_model_name("gpt5-mini") is True
        assert provider.validate_model_name("gpt5mini") is True
        assert provider.validate_model_name("gpt5.2") is True
        assert provider.validate_model_name("gpt5.1") is True
        assert provider.validate_model_name("gpt5.1-codex") is True
        assert provider.validate_model_name("codex-mini") is True

        # Test invalid model
        assert provider.validate_model_name("invalid-model") is False
        assert provider.validate_model_name("gpt-4") is False
        assert provider.validate_model_name("gemini-pro") is False

    def test_resolve_model_name(self):
        """Test model name resolution."""
        provider = OpenAIModelProvider("test-key")

        # Test shorthand resolution
        assert provider._resolve_model_name("mini") == "gpt-5-mini"  # "mini" now resolves to gpt-5-mini
        assert provider._resolve_model_name("o3mini") == "o3-mini"
        assert provider._resolve_model_name("o4mini") == "o4-mini"
        assert provider._resolve_model_name("o4mini") == "o4-mini"
        assert provider._resolve_model_name("gpt5") == "gpt-5"
        assert provider._resolve_model_name("gpt5-mini") == "gpt-5-mini"
        assert provider._resolve_model_name("gpt5mini") == "gpt-5-mini"
        assert provider._resolve_model_name("gpt5.2") == "gpt-5.2"
        assert provider._resolve_model_name("gpt5.1") == "gpt-5.2"
        assert provider._resolve_model_name("gpt5.1-codex") == "gpt-5.1-codex"
        assert provider._resolve_model_name("codex-mini") == "gpt-5.1-codex-mini"

        # Test full name passthrough
        assert provider._resolve_model_name("o3") == "o3"
        assert provider._resolve_model_name("o3-mini") == "o3-mini"
        assert provider._resolve_model_name("o3-pro") == "o3-pro"
        assert provider._resolve_model_name("o4-mini") == "o4-mini"
        assert provider._resolve_model_name("o4-mini") == "o4-mini"
        assert provider._resolve_model_name("gpt-5") == "gpt-5"
        assert provider._resolve_model_name("gpt-5-mini") == "gpt-5-mini"
        assert provider._resolve_model_name("gpt-5.2") == "gpt-5.2"
        assert provider._resolve_model_name("gpt-5.1") == "gpt-5.2"
        assert provider._resolve_model_name("gpt-5.1-codex") == "gpt-5.1-codex"
        assert provider._resolve_model_name("gpt-5.1-codex-mini") == "gpt-5.1-codex-mini"

    def test_get_capabilities_o3(self):
        """Test getting model capabilities for O3."""
        provider = OpenAIModelProvider("test-key")

        capabilities = provider.get_capabilities("o3")
        assert capabilities.model_name == "o3"  # Should NOT be resolved in capabilities
        assert capabilities.friendly_name == "OpenAI (O3)"
        assert capabilities.context_window == 200_000
        assert capabilities.provider == ProviderType.OPENAI
        assert not capabilities.supports_extended_thinking
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True

        # Test temperature constraint (O3 has fixed temperature)
        assert capabilities.temperature_constraint.value == 1.0

    def test_get_capabilities_with_alias(self):
        """Test getting model capabilities with alias resolves correctly."""
        provider = OpenAIModelProvider("test-key")

        capabilities = provider.get_capabilities("mini")
        assert capabilities.model_name == "gpt-5-mini"  # "mini" now resolves to gpt-5-mini
        assert capabilities.friendly_name == "OpenAI (GPT-5-mini)"
        assert capabilities.context_window == 400_000
        assert capabilities.provider == ProviderType.OPENAI

    def test_get_capabilities_gpt5(self):
        """Test getting model capabilities for GPT-5."""
        provider = OpenAIModelProvider("test-key")

        capabilities = provider.get_capabilities("gpt-5")
        assert capabilities.model_name == "gpt-5"
        assert capabilities.friendly_name == "OpenAI (GPT-5)"
        assert capabilities.context_window == 400_000
        assert capabilities.max_output_tokens == 128_000
        assert capabilities.provider == ProviderType.OPENAI
        assert capabilities.supports_extended_thinking is True
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is False
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_temperature is True

    def test_get_capabilities_gpt5_mini(self):
        """Test getting model capabilities for GPT-5-mini."""
        provider = OpenAIModelProvider("test-key")

        capabilities = provider.get_capabilities("gpt-5-mini")
        assert capabilities.model_name == "gpt-5-mini"
        assert capabilities.friendly_name == "OpenAI (GPT-5-mini)"
        assert capabilities.context_window == 400_000
        assert capabilities.max_output_tokens == 128_000
        assert capabilities.provider == ProviderType.OPENAI
        assert capabilities.supports_extended_thinking is True
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is False
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_temperature is True

    def test_get_capabilities_gpt52(self):
        """Test GPT-5.2 capabilities reflect new metadata."""
        provider = OpenAIModelProvider("test-key")

        capabilities = provider.get_capabilities("gpt-5.2")
        assert capabilities.model_name == "gpt-5.2"
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_json_mode is True
        assert capabilities.allow_code_generation is True

    def test_get_capabilities_gpt51_codex(self):
        """Test GPT-5.1 Codex is responses-only and non-streaming."""
        provider = OpenAIModelProvider("test-key")

        capabilities = provider.get_capabilities("gpt-5.1-codex")
        assert capabilities.model_name == "gpt-5.1-codex"
        assert capabilities.supports_streaming is False
        assert capabilities.use_openai_response_api is True
        assert capabilities.allow_code_generation is True

    def test_get_capabilities_gpt51_codex_mini(self):
        """Test GPT-5.1 Codex mini exposes streaming and code generation."""
        provider = OpenAIModelProvider("test-key")

        capabilities = provider.get_capabilities("gpt-5.1-codex-mini")
        assert capabilities.model_name == "gpt-5.1-codex-mini"
        assert capabilities.supports_streaming is True
        assert capabilities.allow_code_generation is True

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_resolves_alias_before_api_call(self, mock_openai_class):
        """Test that generate_content resolves aliases before making API calls.

        This is the CRITICAL test that was missing - verifying that aliases
        like 'mini' get resolved to 'o4-mini' before being sent to OpenAI API.

        Note: gpt-4.1 uses Responses API, so we mock responses.create
        """
        # Set up mock OpenAI client for Responses API
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock the Responses API response
        mock_response = MagicMock()
        mock_response.output_text = "Test response"
        mock_response.model = "gpt-4.1-2025-04-14"  # API returns the resolved model name
        mock_response.id = "test-id"
        mock_response.created_at = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        mock_client.responses.create.return_value = mock_response

        provider = OpenAIModelProvider("test-key")

        # Call generate_content with alias 'gpt4.1' (resolves to gpt-4.1, uses Responses API)
        result = provider.generate_content(
            prompt="Test prompt",
            model_name="gpt4.1",
            temperature=1.0,
        )

        # Verify the Responses API was called with the RESOLVED model name
        mock_client.responses.create.assert_called_once()
        call_kwargs = mock_client.responses.create.call_args[1]

        # CRITICAL ASSERTION: The API should receive "gpt-4.1", not "gpt4.1"
        assert call_kwargs["model"] == "gpt-4.1", f"Expected 'gpt-4.1' but API received '{call_kwargs['model']}'"

        # Verify response
        assert result.content == "Test response"
        assert result.model_name == "gpt-4.1"  # Should be the resolved name

    @patch("providers.openai_responses.OpenAI")
    def test_generate_content_other_aliases(self, mock_openai_class):
        """Test other alias resolutions in generate_content.

        Note: o3-mini and o4-mini use Responses API, so we mock responses.create
        """
        # Set up mock for Responses API
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = "Test response"
        mock_response.id = "test-id"
        mock_response.created_at = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_client.responses.create.return_value = mock_response

        provider = OpenAIModelProvider("test-key")

        # Test o3mini -> o3-mini (Responses API)
        mock_response.model = "o3-mini"
        provider.generate_content(prompt="Test", model_name="o3mini", temperature=1.0)
        call_kwargs = mock_client.responses.create.call_args[1]
        assert call_kwargs["model"] == "o3-mini"

        # Test o4mini -> o4-mini (Responses API)
        mock_response.model = "o4-mini"
        provider.generate_content(prompt="Test", model_name="o4mini", temperature=1.0)
        call_kwargs = mock_client.responses.create.call_args[1]
        assert call_kwargs["model"] == "o4-mini"

    @patch("providers.openai_responses.OpenAI")
    def test_generate_content_no_alias_passthrough(self, mock_openai_class):
        """Test that full model names pass through unchanged.

        Note: o3-mini uses Responses API, so we mock responses.create
        """
        # Set up mock for Responses API
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = "Test response"
        mock_response.model = "o3-mini"
        mock_response.id = "test-id"
        mock_response.created_at = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_client.responses.create.return_value = mock_response

        provider = OpenAIModelProvider("test-key")

        # Test full model name passes through unchanged (use o3-mini since o3-pro has special handling)
        provider.generate_content(prompt="Test", model_name="o3-mini", temperature=1.0)
        call_kwargs = mock_client.responses.create.call_args[1]
        assert call_kwargs["model"] == "o3-mini"  # Should be unchanged

    def test_extended_thinking_capabilities(self):
        """Thinking-mode support should be reflected via ModelCapabilities."""
        provider = OpenAIModelProvider("test-key")

        supported_aliases = [
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt5",
            "gpt5-mini",
            "gpt5mini",
            "gpt5-nano",
            "gpt5nano",
            "nano",
            "mini",  # resolves to gpt-5-mini
        ]
        for alias in supported_aliases:
            assert provider.get_capabilities(alias).supports_extended_thinking is True

        unsupported_aliases = ["o3", "o3-mini", "o4-mini"]
        for alias in unsupported_aliases:
            assert provider.get_capabilities(alias).supports_extended_thinking is False

        # Invalid models should not validate, treat as unsupported
        assert not provider.validate_model_name("invalid-model")

    @patch("providers.openai_responses.OpenAI")
    def test_o3_pro_routes_to_responses_endpoint(self, mock_openai_class):
        """Test that o3-pro model routes to the /v1/responses endpoint (mock test)."""
        # Set up mock for OpenAI Responses API client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        # New o3-pro format: direct output_text field
        mock_response.output_text = "4"
        mock_response.model = "o3-pro"
        mock_response.id = "test-id"
        mock_response.created_at = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        mock_client.responses.create.return_value = mock_response

        provider = OpenAIModelProvider("test-key")

        # Generate content with o3-pro
        result = provider.generate_content(prompt="What is 2 + 2?", model_name="o3-pro", temperature=1.0)

        # Verify responses.create was called
        mock_client.responses.create.assert_called_once()
        call_args = mock_client.responses.create.call_args[1]
        assert call_args["model"] == "o3-pro"
        assert call_args["input"][0]["role"] == "user"
        assert "What is 2 + 2?" in call_args["input"][0]["content"][0]["text"]

        # Verify the response
        assert result.content == "4"
        assert result.model_name == "o3-pro"
        assert result.metadata["endpoint"] == "responses"

    @patch("providers.openai_compatible.OpenAI")
    def test_non_o3_pro_uses_chat_completions(self, mock_openai_class):
        """Test that models without use_openai_response_api use chat completions.

        Note: Using gpt-4o which doesn't have use_openai_response_api set
        """
        # Set up mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4o"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIModelProvider("test-key")

        # Mock validate_model_name to allow gpt-4o regardless of restrictions
        provider.validate_model_name = MagicMock(return_value=True)

        # Generate content with gpt-4o (uses Chat API)
        result = provider.generate_content(prompt="Test prompt", model_name="gpt-4o", temperature=1.0)

        # Verify chat.completions.create was called
        mock_client.chat.completions.create.assert_called_once()

        # Verify the response
        assert result.content == "Test response"
        assert result.model_name == "gpt-4o"

    @patch("providers.openai_responses.OpenAI")
    @patch("providers.openai_compatible.OpenAI")
    def test_responses_api_fallback_to_chat(self, mock_chat_openai, mock_responses_openai):
        """Test automatic fallback from Responses API to Chat API when model not supported.

        Critical test for graceful degradation: when a model is configured with
        use_openai_response_api=true but the API returns a model error, should
        automatically fallback to Chat Completions API instead of failing.
        """
        # Setup Responses API to fail with model error
        mock_responses_client = MagicMock()
        mock_responses_openai.return_value = mock_responses_client
        mock_responses_client.responses.create.side_effect = Exception("Model 'test-model' not found")

        # Setup Chat API to succeed
        mock_chat_client = MagicMock()
        mock_chat_openai.return_value = mock_chat_client
        mock_chat_response = MagicMock()
        mock_chat_response.choices = [MagicMock()]
        mock_chat_response.choices[0].message.content = "Chat API response"
        mock_chat_response.choices[0].finish_reason = "stop"
        mock_chat_response.model = "test-model"
        mock_chat_response.id = "test-id"
        mock_chat_response.created = 1234567890
        mock_chat_response.usage = MagicMock()
        mock_chat_response.usage.prompt_tokens = 10
        mock_chat_response.usage.completion_tokens = 5
        mock_chat_response.usage.total_tokens = 15
        mock_chat_client.chat.completions.create.return_value = mock_chat_response

        provider = OpenAIModelProvider("test-key")

        # Mock a model with use_openai_response_api=true
        mock_capabilities = MagicMock()
        mock_capabilities.use_openai_response_api = True
        provider.get_capabilities = MagicMock(return_value=mock_capabilities)

        # Generate content - should try Responses, fail, then fallback to Chat
        result = provider.generate_content(
            prompt="Test prompt",
            model_name="test-model",
            temperature=1.0,
        )

        # Verify Responses API was tried first
        mock_responses_client.responses.create.assert_called_once()

        # Verify fallback to Chat API succeeded
        mock_chat_client.chat.completions.create.assert_called_once()
        assert result.content == "Chat API response"
        assert result.model_name == "test-model"

    def test_file_attachment_requires_responses_api(self):
        """Test that file attachments require Responses API support.

        Critical validation: when user provides file attachments but the model
        doesn't support Responses API, should raise a clear error message with
        recommendations, not silently fail or ignore the files.
        """
        provider = OpenAIModelProvider("test-key")

        # Mock a model without Responses API support
        mock_capabilities = MagicMock()
        mock_capabilities.use_openai_response_api = False
        provider.get_capabilities = MagicMock(return_value=mock_capabilities)

        # Try to generate content with files - should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            provider.generate_content(
                prompt="Analyze this document",
                model_name="gpt-4o",
                files=["/path/to/document.pdf"],
            )

        # Verify error message is helpful
        error_msg = str(exc_info.value)
        assert "does not support file attachments" in error_msg
        assert "Responses API" in error_msg
        assert "gpt-5" in error_msg or "o3-pro" in error_msg  # Should suggest supported models

    @patch("utils.openai_token_estimator.calculate_text_tokens")
    @patch("utils.openai_token_estimator.estimate_image_tokens")
    @patch("utils.openai_token_estimator.estimate_tokens_for_files")
    def test_token_estimation_delegation(self, mock_estimate_files, mock_estimate_image, mock_calculate_text):
        """Test that provider correctly delegates to openai_token_estimator utility.

        Verifies the delegation pattern: provider methods (_calculate_text_tokens,
        _calculate_image_tokens, estimate_tokens_for_files) should act as thin
        wrappers that delegate to the shared openai_token_estimator module.
        """
        # Setup mocks
        mock_calculate_text.return_value = 15
        mock_estimate_image.return_value = 255
        mock_estimate_files.return_value = 500

        provider = OpenAIModelProvider("test-key")

        # Test text token calculation delegation
        text_tokens = provider._calculate_text_tokens("gpt-4o", "Hello world")
        assert text_tokens == 15
        mock_calculate_text.assert_called_once_with("gpt-4o", "Hello world")

        # Test image token estimation delegation
        image_tokens = provider._calculate_image_tokens("/path/image.jpg", "gpt-4o", "high")
        assert image_tokens == 255
        mock_estimate_image.assert_called_once_with("/path/image.jpg", "gpt-4o", "high")

        # Test file token estimation delegation
        files = [{"path": "/path/file.txt", "mime_type": "text/plain"}]
        file_tokens = provider.estimate_tokens_for_files("gpt-4o", files, "high")
        assert file_tokens == 500
        # Should pass through all parameters including use_responses_api flag
        call_args = mock_estimate_files.call_args
        assert call_args[0] == ("gpt-4o", files, "high")
        assert "use_responses_api" in call_args[1]
