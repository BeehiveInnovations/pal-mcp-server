"""Tests for ModelContext token estimation integration."""

import unittest
from unittest.mock import Mock, patch

from utils.model_context import ModelContext


class TestModelContextTokenEstimation(unittest.TestCase):
    """Test ModelContext token estimation methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_provider = Mock()
        self.mock_provider.get_capabilities.return_value = Mock(
            context_window=1_000_000,
            max_output_tokens=8192,
        )

    def test_estimate_file_tokens_with_gemini_provider(self):
        """Test estimate_file_tokens calls Gemini provider's estimation."""
        # Setup mock provider with estimate_tokens_for_files method
        self.mock_provider.estimate_tokens_for_files.return_value = 258

        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            model_context = ModelContext("gemini-2.5-flash")

            tokens = model_context.estimate_file_tokens("/path/to/image.jpg")

            # Should call provider's estimation
            self.assertEqual(tokens, 258)
            self.mock_provider.estimate_tokens_for_files.assert_called_once()

            # Verify the call arguments
            call_args = self.mock_provider.estimate_tokens_for_files.call_args
            model_name, files = call_args[0]
            self.assertEqual(model_name, "gemini-2.5-flash")
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0]["path"], "/path/to/image.jpg")
            self.assertEqual(files[0]["mime_type"], "image/jpeg")

    def test_estimate_file_tokens_fallback_when_provider_lacks_method(self):
        """Test estimate_file_tokens falls back when provider doesn't have estimation method."""
        # Mock provider without estimate_tokens_for_files attribute
        mock_provider_no_estimation = Mock(spec=["get_capabilities", "generate_content"])
        mock_provider_no_estimation.get_capabilities.return_value = Mock(
            context_window=200_000,
            max_output_tokens=4096,
        )

        with patch(
            "utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=mock_provider_no_estimation
        ):
            with patch("utils.file_utils.estimate_file_tokens", return_value=100) as mock_fallback:
                model_context = ModelContext("gpt-5")

                tokens = model_context.estimate_file_tokens("/path/to/file.txt")

                # Should use fallback
                self.assertEqual(tokens, 100)
                mock_fallback.assert_called_once_with("/path/to/file.txt")

    def test_estimate_file_tokens_fallback_on_provider_exception(self):
        """Test estimate_file_tokens falls back when provider raises exception."""
        self.mock_provider.estimate_tokens_for_files.side_effect = Exception("Provider error")

        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            with patch("utils.file_utils.estimate_file_tokens", return_value=150) as mock_fallback:
                model_context = ModelContext("gemini-2.5-flash")

                tokens = model_context.estimate_file_tokens("/path/to/image.png")

                # Should fall back to file_utils estimation
                self.assertEqual(tokens, 150)
                mock_fallback.assert_called_once_with("/path/to/image.png")

    def test_estimate_file_tokens_fallback_when_provider_returns_none(self):
        """Test estimate_file_tokens falls back when provider returns None."""
        self.mock_provider.estimate_tokens_for_files.return_value = None

        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            with patch("utils.file_utils.estimate_file_tokens", return_value=200) as mock_fallback:
                model_context = ModelContext("gemini-2.5-flash")

                tokens = model_context.estimate_file_tokens("/path/to/unknown.xyz")

                # Should fall back when provider returns None
                self.assertEqual(tokens, 200)
                mock_fallback.assert_called_once_with("/path/to/unknown.xyz")

    def test_estimate_file_tokens_empty_path(self):
        """Test estimate_file_tokens returns 0 for empty file path."""
        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            model_context = ModelContext("gemini-2.5-flash")

            tokens = model_context.estimate_file_tokens("")

            self.assertEqual(tokens, 0)

    def test_detect_mime_type_common_extensions(self):
        """Test detect_mime_type correctly maps common file extensions."""
        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            model_context = ModelContext("flash")

            # Test image types
            self.assertEqual(model_context.detect_mime_type("/path/to/file.jpg"), "image/jpeg")
            self.assertEqual(model_context.detect_mime_type("/path/to/file.jpeg"), "image/jpeg")
            self.assertEqual(model_context.detect_mime_type("/path/to/file.png"), "image/png")
            self.assertEqual(model_context.detect_mime_type("/path/to/file.gif"), "image/gif")
            self.assertEqual(model_context.detect_mime_type("/path/to/file.webp"), "image/webp")

            # Test document types
            self.assertEqual(model_context.detect_mime_type("/path/to/file.pdf"), "application/pdf")

            # Test video types
            self.assertEqual(model_context.detect_mime_type("/path/to/file.mp4"), "video/mp4")
            self.assertEqual(model_context.detect_mime_type("/path/to/file.mov"), "video/quicktime")
            self.assertEqual(model_context.detect_mime_type("/path/to/file.avi"), "video/x-msvideo")

            # Test audio types
            self.assertEqual(model_context.detect_mime_type("/path/to/file.mp3"), "audio/mpeg")
            # Note: mimetypes.guess_type may return 'audio/x-wav', but our fallback map uses 'audio/wav'
            mime = model_context.detect_mime_type("/path/to/file.wav")
            self.assertIn(mime, ["audio/wav", "audio/x-wav"])  # Accept either

    def test_detect_mime_type_case_insensitive(self):
        """Test detect_mime_type handles uppercase extensions."""
        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            model_context = ModelContext("flash")

            # Uppercase extensions should work
            self.assertEqual(model_context.detect_mime_type("/path/to/FILE.JPG"), "image/jpeg")
            self.assertEqual(model_context.detect_mime_type("/path/to/FILE.PNG"), "image/png")
            self.assertEqual(model_context.detect_mime_type("/path/to/FILE.PDF"), "application/pdf")

    def test_detect_mime_type_no_extension(self):
        """Test detect_mime_type defaults to text/plain for files without extension."""
        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            model_context = ModelContext("flash")

            mime_type = model_context.detect_mime_type("/path/to/file_no_extension")

            self.assertEqual(mime_type, "text/plain")

    def test_detect_mime_type_unknown_extension(self):
        """Test detect_mime_type handles unknown extensions (may use mimetypes library or fallback)."""
        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            model_context = ModelContext("flash")

            # Use a truly unknown extension that mimetypes won't recognize
            mime_type = model_context.detect_mime_type("/path/to/file.unknownext12345")

            self.assertEqual(mime_type, "text/plain")

    def test_detect_mime_type_uses_mimetypes_library(self):
        """Test detect_mime_type uses mimetypes.guess_type first."""
        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            with patch("utils.model_context.mimetypes.guess_type", return_value=("image/svg+xml", None)):
                model_context = ModelContext("flash")

                mime_type = model_context.detect_mime_type("/path/to/file.svg")

                # Should use mimetypes.guess_type result
                self.assertEqual(mime_type, "image/svg+xml")

    def test_estimate_tokens_with_gemini_text_tokenizer(self):
        """Test estimate_tokens uses Gemini's text tokenizer when available."""
        # Mock provider with _calculate_text_tokens method
        self.mock_provider._calculate_text_tokens.return_value = 150

        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            model_context = ModelContext("gemini-2.5-flash")

            tokens = model_context.estimate_tokens("Hello, this is a test message.")

            # Should use provider's text tokenization
            self.assertEqual(tokens, 150)
            self.mock_provider._calculate_text_tokens.assert_called_once_with(
                "gemini-2.5-flash", "Hello, this is a test message."
            )

    def test_estimate_tokens_fallback_without_text_tokenizer(self):
        """Test estimate_tokens uses character-based fallback without provider tokenizer."""
        # Mock provider without _calculate_text_tokens
        mock_provider_no_tokenizer = Mock(spec=["get_capabilities", "generate_content"])
        mock_provider_no_tokenizer.get_capabilities.return_value = Mock(
            context_window=200_000,
            max_output_tokens=4096,
        )

        with patch(
            "utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=mock_provider_no_tokenizer
        ):
            model_context = ModelContext("gpt-5")

            # "Hello world" = 11 characters / 4 = 2 tokens (conservative estimate)
            tokens = model_context.estimate_tokens("Hello world")

            self.assertEqual(tokens, 2)

    def test_estimate_tokens_empty_text(self):
        """Test estimate_tokens returns 0 for empty text."""
        with patch("utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_provider):
            model_context = ModelContext("flash")

            tokens = model_context.estimate_tokens("")

            self.assertEqual(tokens, 0)


if __name__ == "__main__":
    unittest.main()
