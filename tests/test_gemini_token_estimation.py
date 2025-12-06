"""Tests for Gemini shared token estimation utility (via provider delegation)."""

import unittest
from unittest.mock import Mock, mock_open, patch

from providers.gemini import GeminiModelProvider


class TestGeminiTokenEstimation(unittest.TestCase):
    """Test Gemini token estimation through provider delegation to shared utility."""

    def setUp(self):
        """Set up test fixtures."""
        self.provider = GeminiModelProvider("test-key")

    # Test: Text token calculation
    def test_calculate_text_tokens_success(self):
        """Test text token calculation uses LocalTokenizer when available."""
        # Test with real LocalTokenizer (requires google-genai[local-tokenizer]>=1.34.0)
        try:
            from google.genai.local_tokenizer import LocalTokenizer  # noqa: F401

            # If LocalTokenizer is available, it should work
            tokens = self.provider._calculate_text_tokens("gemini-2.5-flash", "Hello world")
            # LocalTokenizer should return actual token count (not character-based fallback)
            # "Hello world" is typically 2-3 tokens with SentencePiece
            self.assertGreater(tokens, 0)
            self.assertLess(tokens, 10)  # Sanity check
        except ImportError:
            # If LocalTokenizer not available, should use fallback
            # "Hello world" = 11 characters / 4 = 2 tokens
            tokens = self.provider._calculate_text_tokens("gemini-2.5-flash", "Hello world")
            self.assertEqual(tokens, 2)

    def test_calculate_text_tokens_fallback(self):
        """Test text token calculation uses character-based fallback when LocalTokenizer fails."""
        # Mock LocalTokenizer to raise exception
        with patch("utils.gemini_token_estimator._HAS_LOCAL_TOKENIZER", False):
            # "Hello world" = 11 characters / 4 = 2 tokens
            tokens = self.provider._calculate_text_tokens("gemini-2.5-flash", "Hello world")
            self.assertEqual(tokens, 2)

    # Test: Image token calculation
    def test_calculate_image_tokens_small_image(self):
        """Test image token calculation for small image (≤384px)."""
        with patch("imagesize.get", return_value=(200, 300)):
            tokens = self.provider._calculate_image_tokens("/path/to/small.jpg")
            self.assertEqual(tokens, 258)

    def test_calculate_image_tokens_large_image(self):
        """Test image token calculation for large image with 768×768 tiles (Gemini 2.0+)."""
        with patch("imagesize.get", return_value=(960, 540)):
            tokens = self.provider._calculate_image_tokens("/path/to/large.jpg", "gemini-2.5-flash")
            # 960x540: tiles_x=ceil(960/768)=2, tiles_y=ceil(540/768)=1, total=2*1*258=516
            self.assertEqual(tokens, 516)

    def test_calculate_image_tokens_large_image_gemini_15(self):
        """Test image token calculation for large image with Gemini 1.5 (fixed 258 tokens)."""
        with patch("imagesize.get", return_value=(960, 540)):
            tokens = self.provider._calculate_image_tokens("/path/to/large.jpg", "gemini-1.5-pro")
            # Gemini 1.5: Fixed 258 tokens (no tiling for large images)
            self.assertEqual(tokens, 258)

    def test_calculate_image_tokens_error_fallback(self):
        """Test image token calculation fallback on non-file errors."""
        with patch("imagesize.get", side_effect=Exception("Image read failed")):
            tokens = self.provider._calculate_image_tokens("/path/to/error.jpg")
            self.assertEqual(tokens, 258)

    def test_calculate_image_tokens_file_not_found(self):
        """Test image token calculation raises ValueError on file not found."""
        with patch("imagesize.get", side_effect=FileNotFoundError("No such file")):
            with self.assertRaises(ValueError) as context:
                self.provider._calculate_image_tokens("/path/to/missing.jpg")
            self.assertIn("Image file not found", str(context.exception))

    # Test: PDF token calculation
    def test_calculate_pdf_tokens_success(self):
        """Test PDF token calculation (258 tokens per page)."""
        with patch("builtins.open", mock_open(read_data=b"PDF")):
            with patch("pypdf.PdfReader") as mock_pdf_reader:
                mock_pdf = Mock()
                mock_pdf.pages = [Mock()] * 5  # 5 pages
                mock_pdf_reader.return_value = mock_pdf

                tokens = self.provider._calculate_pdf_tokens("/path/to/doc.pdf")
                # 5 pages * 258 tokens/page = 1290
                self.assertEqual(tokens, 1290)

    def test_calculate_pdf_tokens_error_fallback(self):
        """Test PDF token calculation fallback on non-file errors."""
        with patch("builtins.open", mock_open(read_data=b"PDF")):
            with patch("pypdf.PdfReader", side_effect=Exception("Corrupted PDF")):
                tokens = self.provider._calculate_pdf_tokens("/path/to/error.pdf")
                # Fallback: 10 pages * 258 = 2580
                self.assertEqual(tokens, 2580)

    def test_calculate_pdf_tokens_permission_denied(self):
        """Test PDF token calculation raises ValueError on permission denied."""
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with self.assertRaises(ValueError) as context:
                self.provider._calculate_pdf_tokens("/path/to/noaccess.pdf")
            self.assertIn("Permission denied", str(context.exception))

    # Test: Video token calculation
    def test_calculate_video_tokens_medium_resolution(self):
        """Test video token calculation with MEDIUM resolution (~300 tokens/sec)."""
        with patch("utils.gemini_token_estimator.TinyTag.get") as mock_get:
            mock_tag = Mock()
            mock_tag.duration = 10.0  # 10 seconds
            mock_get.return_value = mock_tag

            tokens = self.provider._calculate_video_tokens("/path/to/video.mp4")
            # 10 sec * 300 tokens/sec = 3000
            self.assertEqual(tokens, 3000)

    def test_calculate_video_tokens_low_resolution(self):
        """Test video token calculation with LOW resolution (~100 tokens/sec)."""
        with patch("utils.gemini_token_estimator.TinyTag.get") as mock_get:
            with patch("providers.gemini.GEMINI_MEDIA_RESOLUTION", "LOW"):
                mock_tag = Mock()
                mock_tag.duration = 10.0  # 10 seconds
                mock_get.return_value = mock_tag

                tokens = self.provider._calculate_video_tokens("/path/to/video.mp4")
                # 10 sec * 100 tokens/sec = 1000
                self.assertEqual(tokens, 1000)

    def test_calculate_video_tokens_no_duration(self):
        """Test video token calculation when duration is None (fallback 10 sec)."""
        with patch("utils.gemini_token_estimator.TinyTag.get") as mock_get:
            mock_tag = Mock()
            mock_tag.duration = None
            mock_get.return_value = mock_tag

            tokens = self.provider._calculate_video_tokens("/path/to/video.mp4")
            # Fallback: 10 sec * 300 tokens/sec = 3000
            self.assertEqual(tokens, 3000)

    def test_calculate_video_tokens_error_fallback(self):
        """Test video token calculation fallback on non-file errors."""
        with patch("utils.gemini_token_estimator.TinyTag.get", side_effect=Exception("Corrupted video")):
            tokens = self.provider._calculate_video_tokens("/path/to/error.mp4")
            # Fallback: 10 sec * 300 tokens/sec = 3000
            self.assertEqual(tokens, 3000)

    def test_calculate_video_tokens_os_error(self):
        """Test video token calculation raises ValueError on OS error."""
        with patch("utils.gemini_token_estimator.TinyTag.get", side_effect=OSError("Cannot read file")):
            with self.assertRaises(ValueError) as context:
                self.provider._calculate_video_tokens("/path/to/unreadable.mp4")
            self.assertIn("Cannot access video file", str(context.exception))

    # Test: Audio token calculation
    def test_calculate_audio_tokens_success(self):
        """Test audio token calculation (32 tokens/sec)."""
        with patch("utils.gemini_token_estimator.TinyTag.get") as mock_get:
            mock_tag = Mock()
            mock_tag.duration = 15.0  # 15 seconds
            mock_get.return_value = mock_tag

            tokens = self.provider._calculate_audio_tokens("/path/to/audio.mp3")
            # 15 sec * 32 tokens/sec = 480
            self.assertEqual(tokens, 480)

    def test_calculate_audio_tokens_no_duration(self):
        """Test audio token calculation when duration is None (fallback 10 sec)."""
        with patch("utils.gemini_token_estimator.TinyTag.get") as mock_get:
            mock_tag = Mock()
            mock_tag.duration = None
            mock_get.return_value = mock_tag

            tokens = self.provider._calculate_audio_tokens("/path/to/audio.mp3")
            # Fallback: 10 sec * 32 tokens/sec = 320
            self.assertEqual(tokens, 320)

    def test_calculate_audio_tokens_error_fallback(self):
        """Test audio token calculation fallback on non-file errors."""
        with patch("utils.gemini_token_estimator.TinyTag.get", side_effect=Exception("Unsupported format")):
            tokens = self.provider._calculate_audio_tokens("/path/to/error.mp3")
            # Fallback: 10 sec * 32 tokens/sec = 320
            self.assertEqual(tokens, 320)

    def test_calculate_audio_tokens_io_error(self):
        """Test audio token calculation raises ValueError on I/O error."""
        with patch("utils.gemini_token_estimator.TinyTag.get", side_effect=OSError("I/O error")):
            with self.assertRaises(ValueError) as context:
                self.provider._calculate_audio_tokens("/path/to/ioerror.mp3")
            self.assertIn("Cannot access audio file", str(context.exception))

    # Test: estimate_tokens_for_files - offline estimation
    @patch("utils.gemini_token_estimator.imagesize.get", return_value=(200, 300))
    def test_estimate_tokens_offline_with_images(self, mock_imagesize):
        """Test offline estimation for images."""
        files = [
            {"path": "/path/to/image1.jpg", "mime_type": "image/jpeg"},
            {"path": "/path/to/image2.png", "mime_type": "image/png"},
        ]

        tokens = self.provider.estimate_tokens_for_files("gemini-2.5-flash", files)

        # 2 small images (≤384px) * 258 tokens = 516
        self.assertEqual(tokens, 516)
        self.assertEqual(mock_imagesize.call_count, 2)

    @patch("builtins.open", new_callable=mock_open, read_data=b"PDF content")
    @patch("utils.gemini_token_estimator.pypdf.PdfReader")
    def test_estimate_tokens_offline_with_pdf(self, mock_pdf_reader, mock_file):
        """Test offline estimation for PDF."""
        mock_reader = Mock()
        mock_reader.pages = [Mock()] * 5  # 5 pages
        mock_pdf_reader.return_value = mock_reader

        files = [{"path": "/path/to/doc.pdf", "mime_type": "application/pdf"}]

        tokens = self.provider.estimate_tokens_for_files("gemini-2.5-flash", files)

        # 5 pages * 258 tokens/page = 1290
        self.assertEqual(tokens, 1290)

    @patch("builtins.open", new_callable=mock_open, read_data="Hello world")
    def test_estimate_tokens_offline_with_text(self, mock_file):
        """Test offline estimation for text files."""
        files = [{"path": "/path/to/file.txt", "mime_type": "text/plain"}]

        tokens = self.provider.estimate_tokens_for_files("gemini-2.5-flash", files)

        # "Hello world" = 11 chars / 4 = 2 tokens (fallback estimation)
        self.assertGreater(tokens, 0)

    @patch("utils.gemini_token_estimator.TinyTag.get")
    def test_estimate_tokens_offline_with_video(self, mock_tinytag):
        """Test offline estimation for video."""
        mock_tag = Mock()
        mock_tag.duration = 10.0  # 10 seconds
        mock_tinytag.return_value = mock_tag

        files = [{"path": "/path/to/video.mp4", "mime_type": "video/mp4"}]

        tokens = self.provider.estimate_tokens_for_files("gemini-2.5-flash", files)

        # 10 sec * 300 tokens/sec = 3000
        self.assertEqual(tokens, 3000)

    @patch("utils.gemini_token_estimator.TinyTag.get")
    def test_estimate_tokens_offline_with_audio(self, mock_tinytag):
        """Test offline estimation for audio."""
        mock_tag = Mock()
        mock_tag.duration = 15.0  # 15 seconds
        mock_tinytag.return_value = mock_tag

        files = [{"path": "/path/to/audio.mp3", "mime_type": "audio/mpeg"}]

        tokens = self.provider.estimate_tokens_for_files("gemini-2.5-flash", files)

        # 15 sec * 32 tokens/sec = 480
        self.assertEqual(tokens, 480)

    def test_estimate_tokens_with_empty_files(self):
        """Test estimation with empty file list."""
        tokens = self.provider.estimate_tokens_for_files("gemini-2.5-flash", [])

        self.assertEqual(tokens, 0)

    def test_estimate_tokens_with_unknown_mime_type(self):
        """Test estimation raises ValueError for unknown mime type."""
        files = [{"path": "/path/to/unknown.xyz", "mime_type": "application/unknown"}]

        with self.assertRaises(ValueError) as context:
            self.provider.estimate_tokens_for_files("gemini-2.5-flash", files)

        self.assertIn("Unsupported mime type", str(context.exception))
        self.assertIn("application/unknown", str(context.exception))

    def test_estimate_tokens_with_missing_file(self):
        """Test estimation raises ValueError for missing file."""
        files = [{"path": "/nonexistent/file.txt", "mime_type": "text/plain"}]

        with self.assertRaises(ValueError) as context:
            self.provider.estimate_tokens_for_files("gemini-2.5-flash", files)

        self.assertIn("cannot access", str(context.exception).lower())
        self.assertIn("/nonexistent/file.txt", str(context.exception))


if __name__ == "__main__":
    unittest.main()
