"""Integration tests for BedrockModelProvider with real API calls.

These tests use VCR cassettes to record/replay real API interactions.
Run with: pytest tests/test_bedrock_integration.py -m slow
"""

import pytest

from providers.bedrock import BedrockModelProvider
from providers.shared import ProviderType


@pytest.mark.slow
@pytest.mark.integration
class TestBedrockIntegration:
    """Integration tests with real Bedrock API (VCR cassettes)."""

    def test_real_model_discovery(self):
        """Test real model discovery API call.
        
        Note: This test requires AWS credentials and will be recorded
        to a VCR cassette on first run.
        """
        pytest.skip("Requires AWS credentials - run manually with real credentials")
        
        provider = BedrockModelProvider()

        assert len(provider._model_cache) > 0
        claude_models = [m for m in provider._model_cache if 'claude' in m.lower()]
        assert len(claude_models) > 0

    def test_real_claude_haiku_call(self):
        """Test real API call to Claude Haiku.
        
        Note: This test requires AWS credentials and will be recorded
        to a VCR cassette on first run.
        """
        pytest.skip("Requires AWS credentials - run manually with real credentials")
        
        provider = BedrockModelProvider()

        messages = [
            {'role': 'user', 'content': 'Say hello in 5 words'}
        ]

        result = provider.generate_content('bc-haiku-4.5-us', messages, max_tokens=50)

        assert result.content
        assert len(result.content) > 0
        assert result.provider == ProviderType.BEDROCK
        assert result.input_tokens > 0
        assert result.output_tokens > 0

    def test_real_claude_sonnet_call(self):
        """Test real API call to Claude Sonnet.
        
        Note: This test requires AWS credentials and will be recorded
        to a VCR cassette on first run.
        """
        pytest.skip("Requires AWS credentials - run manually with real credentials")
        
        provider = BedrockModelProvider()

        messages = [
            {'role': 'user', 'content': 'Explain async/await in Python in 2 sentences'}
        ]

        result = provider.generate_content('bc-sonnet-4.5-us', messages, max_tokens=200)

        assert result.content
        assert 'async' in result.content.lower() or 'await' in result.content.lower()

    def test_fallback_models_available(self):
        """Test that fallback models are available even without discovery."""
        provider = BedrockModelProvider()
        
        assert 'us.anthropic.claude-haiku-4-5-20251001-v1:0' in provider._model_cache
        assert 'us.anthropic.claude-sonnet-4-5-20250929-v1:0' in provider._model_cache
        assert 'us.anthropic.claude-opus-4-1-20250805-v1:0' in provider._model_cache
        
        assert 'bc-haiku-4.5-us' in provider._alias_map
        assert 'bc-sonnet-4.5-us' in provider._alias_map
        assert 'bc-opus-4.1' in provider._alias_map
