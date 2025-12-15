"""Tests for OpenAI ModelContext token estimation integration."""

import unittest
from unittest.mock import Mock, patch

from utils.model_context import ModelContext


class TestOpenAIModelContextIntegration(unittest.TestCase):
    """Test OpenAI token estimation integration with ModelContext."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_openai_provider = Mock()
        self.mock_openai_provider.get_capabilities.return_value = Mock(
            context_window=200_000,
            max_output_tokens=16_000,
        )

    def test_estimate_tokens_with_openai_provider(self):
        """Test estimate_tokens calls OpenAI provider's text tokenization."""
        # Setup mock provider with _calculate_text_tokens method
        self.mock_openai_provider._calculate_text_tokens.return_value = 15

        with patch(
            "utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_openai_provider
        ):
            model_context = ModelContext("gpt-4o")

            tokens = model_context.estimate_tokens("Hello, world!")

            # Should call provider's text token calculation
            self.assertEqual(tokens, 15)
            self.mock_openai_provider._calculate_text_tokens.assert_called_once_with("gpt-4o", "Hello, world!")

    def test_estimate_tokens_fallback_when_provider_lacks_method(self):
        """Test estimate_tokens falls back when provider doesn't have _calculate_text_tokens."""
        # Mock provider without _calculate_text_tokens attribute
        mock_provider_no_calc = Mock(spec=["get_capabilities", "generate_content"])
        mock_provider_no_calc.get_capabilities.return_value = Mock(
            context_window=200_000,
            max_output_tokens=4096,
        )

        with patch(
            "utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=mock_provider_no_calc
        ):
            model_context = ModelContext("unknown-model")

            tokens = model_context.estimate_tokens("Hello, world!")

            # Should use fallback: len(text) // 4
            self.assertEqual(tokens, len("Hello, world!") // 4)

    def test_estimate_tokens_fallback_on_provider_exception(self):
        """Test estimate_tokens falls back when provider raises exception."""
        self.mock_openai_provider._calculate_text_tokens.side_effect = Exception("Tokenizer error")

        with patch(
            "utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_openai_provider
        ):
            model_context = ModelContext("gpt-4o")

            tokens = model_context.estimate_tokens("Test text")

            # Should fall back to conservative estimation (1 token ≈ 4 chars)
            self.assertEqual(tokens, len("Test text") // 4)

    @patch("utils.model_context.ModelProviderRegistry.get_provider_for_model")
    def test_estimate_file_tokens_with_openai_provider(self, mock_get_provider):
        """Test estimate_file_tokens calls OpenAI provider for different file types."""
        # Test cases: (file_path, expected_tokens, expected_mime_type)
        test_cases = [
            ("/path/to/image.jpg", 255, "image/jpeg"),
            ("/path/to/audio.mp3", 100, "audio/mpeg"),
        ]

        for file_path, expected_tokens, expected_mime in test_cases:
            with self.subTest(file_path=file_path):
                # Setup mock provider
                self.mock_openai_provider.estimate_tokens_for_files.return_value = expected_tokens
                mock_get_provider.return_value = self.mock_openai_provider

                model_context = ModelContext("gpt-4o")
                tokens = model_context.estimate_file_tokens(file_path)

                # Verify result
                self.assertEqual(tokens, expected_tokens)

                # Verify call arguments
                call_args = self.mock_openai_provider.estimate_tokens_for_files.call_args
                model_name, files = call_args[0]
                self.assertEqual(model_name, "gpt-4o")
                self.assertEqual(len(files), 1)
                self.assertEqual(files[0]["path"], file_path)
                self.assertEqual(files[0]["mime_type"], expected_mime)

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
        self.mock_openai_provider.estimate_tokens_for_files.side_effect = ValueError("Unsupported file type")

        with patch(
            "utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_openai_provider
        ):
            with patch("utils.file_utils.estimate_file_tokens", return_value=150) as mock_fallback:
                model_context = ModelContext("gpt-4o")

                tokens = model_context.estimate_file_tokens("/path/to/video.mp4")

                # Should fall back to file_utils estimation
                self.assertEqual(tokens, 150)
                mock_fallback.assert_called_once_with("/path/to/video.mp4")

    @patch("utils.model_context.ModelProviderRegistry.get_provider_for_model")
    @patch("utils.file_utils.estimate_file_tokens")
    def test_estimate_file_tokens_fallback_when_provider_returns_none(self, mock_fallback, mock_get_provider):
        """Test estimate_file_tokens falls back when provider returns None (unknown file types)."""
        # Setup provider to return None
        self.mock_openai_provider.estimate_tokens_for_files.return_value = None
        mock_get_provider.return_value = self.mock_openai_provider

        # Test cases: (file_path, fallback_tokens)
        test_cases = [
            ("/path/to/unknown.xyz", 200),  # Unknown extension
            ("/path/to/noext", 300),  # No extension
        ]

        for file_path, fallback_tokens in test_cases:
            with self.subTest(file_path=file_path):
                mock_fallback.return_value = fallback_tokens

                model_context = ModelContext("gpt-4o")
                tokens = model_context.estimate_file_tokens(file_path)

                # Should fall back when provider returns None
                self.assertEqual(tokens, fallback_tokens)
                mock_fallback.assert_called_with(file_path)

    def test_unsupported_content_type_propagates_error(self):
        """Test that UnsupportedContentTypeError is propagated, not caught for fallback."""
        from utils.openai_token_estimator import UnsupportedContentTypeError

        # Setup OpenAI provider that raises UnsupportedContentTypeError for audio on GPT-5
        self.mock_openai_provider.estimate_tokens_for_files.side_effect = UnsupportedContentTypeError(
            "gpt-5", "audio files", "/path/to/audio.mp3"
        )

        with patch(
            "utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_openai_provider
        ):
            with patch("utils.file_utils.estimate_file_tokens") as mock_fallback:
                model_context = ModelContext("gpt-5")

                # Should raise UnsupportedContentTypeError, NOT use fallback
                with self.assertRaises(UnsupportedContentTypeError) as context:
                    model_context.estimate_file_tokens("/path/to/audio.mp3")

                # Verify the error message
                self.assertIn("gpt-5", str(context.exception))
                self.assertIn("audio files", str(context.exception))

                # Verify fallback was NOT called
                mock_fallback.assert_not_called()

    def test_regular_errors_still_use_fallback(self):
        """Test that regular errors (not UnsupportedContentTypeError) still use fallback."""
        # Setup provider to raise a regular ValueError
        self.mock_openai_provider.estimate_tokens_for_files.side_effect = ValueError("Some other error")

        with patch(
            "utils.model_context.ModelProviderRegistry.get_provider_for_model", return_value=self.mock_openai_provider
        ):
            with patch("utils.file_utils.estimate_file_tokens", return_value=200) as mock_fallback:
                model_context = ModelContext("gpt-4o")

                # Regular errors should still use fallback
                tokens = model_context.estimate_file_tokens("/path/to/file.txt")

                # Should use fallback
                self.assertEqual(tokens, 200)
                mock_fallback.assert_called_once_with("/path/to/file.txt")


class TestOpenRouterIntegration(unittest.TestCase):
    """Test OpenRouter's multi-provider routing for OpenAI models."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_openrouter_provider = Mock()
        self.mock_openrouter_provider.get_capabilities.return_value = Mock(
            context_window=200_000,
            max_output_tokens=16_000,
        )

    @patch("utils.model_context.ModelProviderRegistry.get_provider_for_model")
    def test_openrouter_routes_openai_models(self, mock_get_provider):
        """Test that OpenRouter routes OpenAI models to OpenAI estimator (text and files)."""
        mock_get_provider.return_value = self.mock_openrouter_provider

        # Test text estimation
        self.mock_openrouter_provider._calculate_text_tokens.return_value = 25
        model_context = ModelContext("openai/gpt-4o")
        tokens = model_context.estimate_tokens("OpenRouter test text")
        self.assertEqual(tokens, 25)
        self.mock_openrouter_provider._calculate_text_tokens.assert_called_once_with(
            "openai/gpt-4o", "OpenRouter test text"
        )

        # Test image estimation
        self.mock_openrouter_provider.estimate_tokens_for_files.return_value = 340
        model_context = ModelContext("openai/gpt-5")
        tokens = model_context.estimate_file_tokens("/path/to/large_image.png")
        self.assertEqual(tokens, 340)
        call_args = self.mock_openrouter_provider.estimate_tokens_for_files.call_args
        model_name, files = call_args[0]
        self.assertEqual(model_name, "openai/gpt-5")
        self.assertEqual(files[0]["mime_type"], "image/png")
