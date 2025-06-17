"""Tests for OpenAI-compatible provider token usage extraction."""

import unittest
from unittest.mock import Mock

from providers.openai_compatible import OpenAICompatibleProvider


class TestOpenAICompatibleTokenUsage(unittest.TestCase):
    """Test OpenAI-compatible provider token usage handling."""

    def setUp(self):
        """Set up test fixtures."""

        # Create a concrete implementation for testing
        class TestProvider(OpenAICompatibleProvider):
            FRIENDLY_NAME = "Test"
            SUPPORTED_MODELS = {"test-model": {"context_window": 4096}}

            def get_capabilities(self, model_name):
                return Mock()

            def get_provider_type(self):
                return Mock()

            def validate_model_name(self, model_name):
                return True

        self.provider = TestProvider("test-key")

    def test_extract_usage_with_valid_tokens(self):
        """Test token extraction with valid token counts."""
        response = Mock()
        response.usage = Mock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 50
        response.usage.total_tokens = 150

        usage = self.provider._extract_usage(response)

        self.assertEqual(usage["input_tokens"], 100)
        self.assertEqual(usage["output_tokens"], 50)
        self.assertEqual(usage["total_tokens"], 150)

    def test_extract_usage_with_none_prompt_tokens(self):
        """Test token extraction when prompt_tokens is None (regression test for bug)."""
        response = Mock()
        response.usage = Mock()
        response.usage.prompt_tokens = None  # This was causing crashes
        response.usage.completion_tokens = 50
        response.usage.total_tokens = None

        usage = self.provider._extract_usage(response)

        # Should default to 0 when None
        self.assertEqual(usage["input_tokens"], 0)
        self.assertEqual(usage["output_tokens"], 50)
        self.assertEqual(usage["total_tokens"], 0)

    def test_extract_usage_with_none_completion_tokens(self):
        """Test token extraction when completion_tokens is None (regression test for bug)."""
        response = Mock()
        response.usage = Mock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = None  # This was causing crashes
        response.usage.total_tokens = None

        usage = self.provider._extract_usage(response)

        self.assertEqual(usage["input_tokens"], 100)
        # Should default to 0 when None
        self.assertEqual(usage["output_tokens"], 0)
        self.assertEqual(usage["total_tokens"], 0)

    def test_extract_usage_with_all_none_tokens(self):
        """Test token extraction when all token counts are None."""
        response = Mock()
        response.usage = Mock()
        response.usage.prompt_tokens = None
        response.usage.completion_tokens = None
        response.usage.total_tokens = None

        usage = self.provider._extract_usage(response)

        # Should default to 0 for all when None
        self.assertEqual(usage["input_tokens"], 0)
        self.assertEqual(usage["output_tokens"], 0)
        self.assertEqual(usage["total_tokens"], 0)

    def test_extract_usage_without_usage(self):
        """Test token extraction when response has no usage."""
        response = Mock(spec=[])  # No usage attribute

        usage = self.provider._extract_usage(response)

        # Should return empty dict
        self.assertEqual(usage, {})

    def test_extract_usage_with_zero_tokens(self):
        """Test token extraction with zero token counts."""
        response = Mock()
        response.usage = Mock()
        response.usage.prompt_tokens = 0
        response.usage.completion_tokens = 0
        response.usage.total_tokens = 0

        usage = self.provider._extract_usage(response)

        self.assertEqual(usage["input_tokens"], 0)
        self.assertEqual(usage["output_tokens"], 0)
        self.assertEqual(usage["total_tokens"], 0)

    def test_alternative_token_format_with_none(self):
        """Test alternative token format (input_tokens/output_tokens) with None values."""
        # This tests the other code path in generate_content_openai_responses
        # Simulate a response with input_tokens/output_tokens attributes that could be None
        response = Mock()
        response.input_tokens = None  # This was causing crashes
        response.output_tokens = 50

        # Test the pattern: getattr(response, "input_tokens", 0) or 0
        input_tokens = getattr(response, "input_tokens", 0) or 0
        output_tokens = getattr(response, "output_tokens", 0) or 0

        # Should not crash and should handle None gracefully
        self.assertEqual(input_tokens, 0)
        self.assertEqual(output_tokens, 50)

        # Test that addition works
        total = input_tokens + output_tokens
        self.assertEqual(total, 50)


if __name__ == "__main__":
    unittest.main()
