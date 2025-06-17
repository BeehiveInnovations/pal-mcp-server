"""Tests for Gemini provider token usage extraction."""

import unittest
from unittest.mock import Mock

from providers.gemini import GeminiModelProvider


class TestGeminiTokenUsage(unittest.TestCase):
    """Test Gemini provider token usage handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.provider = GeminiModelProvider("test-key")

    def test_extract_usage_with_valid_tokens(self):
        """Test token extraction with valid token counts."""
        response = Mock()
        response.usage_metadata = Mock()
        response.usage_metadata.prompt_token_count = 100
        response.usage_metadata.candidates_token_count = 50

        usage = self.provider._extract_usage(response)

        self.assertEqual(usage["input_tokens"], 100)
        self.assertEqual(usage["output_tokens"], 50)
        self.assertEqual(usage["total_tokens"], 150)

    def test_extract_usage_with_none_input_tokens(self):
        """Test token extraction when input_tokens is None (regression test for bug)."""
        response = Mock()
        response.usage_metadata = Mock()
        response.usage_metadata.prompt_token_count = None  # This was causing crashes
        response.usage_metadata.candidates_token_count = 50

        usage = self.provider._extract_usage(response)

        # Should not include input_tokens when None
        self.assertNotIn("input_tokens", usage)
        self.assertEqual(usage["output_tokens"], 50)
        # Should not calculate total_tokens when input is None
        self.assertNotIn("total_tokens", usage)

    def test_extract_usage_with_none_output_tokens(self):
        """Test token extraction when output_tokens is None (regression test for bug)."""
        response = Mock()
        response.usage_metadata = Mock()
        response.usage_metadata.prompt_token_count = 100
        response.usage_metadata.candidates_token_count = None  # This was causing crashes

        usage = self.provider._extract_usage(response)

        self.assertEqual(usage["input_tokens"], 100)
        # Should not include output_tokens when None
        self.assertNotIn("output_tokens", usage)
        # Should not calculate total_tokens when output is None
        self.assertNotIn("total_tokens", usage)

    def test_extract_usage_with_both_none_tokens(self):
        """Test token extraction when both token counts are None."""
        response = Mock()
        response.usage_metadata = Mock()
        response.usage_metadata.prompt_token_count = None
        response.usage_metadata.candidates_token_count = None

        usage = self.provider._extract_usage(response)

        # Should return empty dict when all tokens are None
        self.assertEqual(usage, {})

    def test_extract_usage_without_usage_metadata(self):
        """Test token extraction when response has no usage_metadata."""
        response = Mock(spec=[])

        usage = self.provider._extract_usage(response)

        # Should return empty dict
        self.assertEqual(usage, {})

    def test_extract_usage_with_zero_tokens(self):
        """Test token extraction with zero token counts."""
        response = Mock()
        response.usage_metadata = Mock()
        response.usage_metadata.prompt_token_count = 0
        response.usage_metadata.candidates_token_count = 0

        usage = self.provider._extract_usage(response)

        self.assertEqual(usage["input_tokens"], 0)
        self.assertEqual(usage["output_tokens"], 0)
        self.assertEqual(usage["total_tokens"], 0)

    def test_extract_usage_missing_attributes(self):
        """Test token extraction when metadata lacks token count attributes."""
        response = Mock()
        response.usage_metadata = Mock(spec=[])

        usage = self.provider._extract_usage(response)

        # Should return empty dict when attributes are missing
        self.assertEqual(usage, {})


if __name__ == "__main__":
    unittest.main()
