"""Unit tests for BedrockModelProvider."""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError, NoCredentialsError

from providers.bedrock import BedrockModelProvider
from providers.shared import ProviderType


@pytest.fixture
def mock_boto3():
    """Mock boto3 clients."""
    with patch('providers.bedrock.boto3') as mock:
        yield mock


@pytest.fixture
def mock_bedrock_response():
    """Sample Bedrock list_foundation_models response."""
    return {
        'modelSummaries': [
            {
                'modelId': 'anthropic.claude-haiku-v1:20240307',
                'modelName': 'Claude Haiku',
                'providerName': 'Anthropic',
                'inputModalities': ['TEXT', 'IMAGE'],
                'outputModalities': ['TEXT'],
                'responseStreamingSupported': True,
                'customizationsSupported': [],
                'inferenceTypesSupported': ['ON_DEMAND'],
            },
            {
                'modelId': 'amazon.titan-text-premier-v1:0',
                'modelName': 'Titan Text Premier',
                'providerName': 'Amazon',
                'inputModalities': ['TEXT'],
                'outputModalities': ['TEXT'],
                'responseStreamingSupported': True,
                'customizationsSupported': [],
                'inferenceTypesSupported': ['ON_DEMAND'],
            },
        ]
    }


class TestBedrockModelProvider:
    """Test BedrockModelProvider functionality."""

    def test_initialization_with_auto_discovery(self, mock_boto3, mock_bedrock_response):
        """Test provider initializes and discovers models."""
        mock_client = Mock()
        mock_client.list_foundation_models.return_value = mock_bedrock_response
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()

        assert len(provider._model_cache) == 2
        assert 'anthropic.claude-haiku-v1:20240307' in provider._model_cache
        assert 'amazon.titan-text-premier-v1:0' in provider._model_cache

    def test_initialization_fallback_on_discovery_failure(self, mock_boto3):
        """Test provider falls back to hardcoded models if discovery fails."""
        mock_client = Mock()
        mock_client.list_foundation_models.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'ListFoundationModels'
        )
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()

        assert len(provider._model_cache) >= 3
        assert any('claude-haiku' in model_id for model_id in provider._model_cache)

    def test_alias_creation_claude(self, mock_boto3, mock_bedrock_response):
        """Test alias creation for Claude models."""
        mock_client = Mock()
        mock_client.list_foundation_models.return_value = mock_bedrock_response
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()

        assert len(provider._alias_map) > 0

    def test_alias_resolution(self, mock_boto3):
        """Test alias resolves to full model ID."""
        mock_client = Mock()
        mock_client.list_foundation_models.return_value = {'modelSummaries': []}
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()
        provider._alias_map['bc-haiku-4.5-us'] = 'us.anthropic.claude-haiku-4-5-20251001-v1:0'

        resolved = provider._alias_map.get('bc-haiku-4.5-us')
        assert resolved == 'us.anthropic.claude-haiku-4-5-20251001-v1:0'

    def test_claude_request_formatting(self, mock_boto3):
        """Test Claude request format."""
        mock_client = Mock()
        mock_client.list_foundation_models.return_value = {'modelSummaries': []}
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()

        messages = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there!'},
            {'role': 'user', 'content': 'How are you?'}
        ]

        request = provider._format_claude_request(messages, max_tokens=1024, temperature=0.5)

        assert request['anthropic_version'] == 'bedrock-2023-05-31'
        assert request['messages'] == messages
        assert request['max_tokens'] == 1024
        assert request['temperature'] == 0.5

    def test_titan_request_formatting(self, mock_boto3):
        """Test Titan request format."""
        mock_client = Mock()
        mock_client.list_foundation_models.return_value = {'modelSummaries': []}
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()

        messages = [
            {'role': 'user', 'content': 'Hello'},
        ]

        request = provider._format_titan_request(messages, max_tokens=512, temperature=0.7)

        assert 'inputText' in request
        assert 'user: Hello' in request['inputText']
        assert request['textGenerationConfig']['maxTokenCount'] == 512
        assert request['textGenerationConfig']['temperature'] == 0.7

    def test_claude_response_parsing(self, mock_boto3):
        """Test Claude response parsing."""
        mock_client = Mock()
        mock_client.list_foundation_models.return_value = {'modelSummaries': []}
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()

        response_body = {
            'id': 'msg_123',
            'type': 'message',
            'role': 'assistant',
            'content': [{'type': 'text', 'text': 'Hello, world!'}],
            'model': 'claude-haiku-v1',
            'stop_reason': 'end_turn',
            'usage': {'input_tokens': 10, 'output_tokens': 5}
        }

        result = provider._parse_claude_response(response_body)

        assert result.content == 'Hello, world!'
        assert result.provider == ProviderType.BEDROCK
        assert result.input_tokens == 10
        assert result.output_tokens == 5

    def test_generate_content_with_alias(self, mock_boto3):
        """Test generate_content with model alias."""
        mock_runtime = Mock()
        mock_runtime.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'id': 'msg_123',
                'content': [{'type': 'text', 'text': 'Response'}],
                'usage': {'input_tokens': 5, 'output_tokens': 3}
            }).encode())
        }
        mock_boto3.client.return_value = mock_runtime

        provider = BedrockModelProvider()
        provider._alias_map['bc-haiku'] = 'anthropic.claude-haiku-v1:20240307'
        provider._model_cache['anthropic.claude-haiku-v1:20240307'] = Mock()

        messages = [{'role': 'user', 'content': 'Test'}]
        result = provider.generate_content('bc-haiku', messages)

        assert result.content == 'Response'
        mock_runtime.invoke_model.assert_called_once()

    def test_error_handling_invalid_model(self, mock_boto3):
        """Test error handling for invalid model."""
        mock_client = Mock()
        mock_client.list_foundation_models.return_value = {'modelSummaries': []}
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()

        with pytest.raises(ValueError, match="Model .* not found"):
            provider.generate_content('invalid-model', [])

    def test_error_handling_api_error(self, mock_boto3):
        """Test error handling for Bedrock API errors."""
        mock_runtime = Mock()
        mock_runtime.invoke_model.side_effect = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate limit exceeded'}},
            'InvokeModel'
        )
        mock_boto3.client.return_value = mock_runtime

        provider = BedrockModelProvider()
        provider._model_cache['test-model'] = Mock()

        with pytest.raises(RuntimeError, match="Bedrock API error"):
            provider.generate_content('test-model', [{'role': 'user', 'content': 'Test'}])

    def test_intelligence_score_estimation(self, mock_boto3):
        """Test intelligence score estimation for different models."""
        mock_client = Mock()
        mock_client.list_foundation_models.return_value = {'modelSummaries': []}
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()

        assert provider._estimate_intelligence_score('anthropic.claude-opus-v1', 'Opus') == 19
        assert provider._estimate_intelligence_score('anthropic.claude-sonnet-v1', 'Sonnet') == 16
        assert provider._estimate_intelligence_score('anthropic.claude-haiku-v1', 'Haiku') == 14
        assert provider._estimate_intelligence_score('meta.llama3-70b', 'Llama 3 70B') >= 15
        assert provider._estimate_intelligence_score('meta.llama3-8b', 'Llama 3 8B') >= 12

    def test_context_window_estimation(self, mock_boto3):
        """Test context window estimation for different models."""
        mock_client = Mock()
        mock_client.list_foundation_models.return_value = {'modelSummaries': []}
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()

        assert provider._estimate_context_window('anthropic.claude-haiku-v1') == 200_000
        assert provider._estimate_context_window('meta.llama3-70b') == 128_000
        assert provider._estimate_context_window('amazon.titan-text-v1') == 32_000

    def test_provider_type(self, mock_boto3):
        """Test get_provider_type returns BEDROCK."""
        mock_client = Mock()
        mock_client.list_foundation_models.return_value = {'modelSummaries': []}
        mock_boto3.client.return_value = mock_client

        provider = BedrockModelProvider()
        assert provider.get_provider_type() == ProviderType.BEDROCK
