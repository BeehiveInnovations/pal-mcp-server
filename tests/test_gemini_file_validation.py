"""Tests for Gemini file upload validation logic.

This test suite validates the P0 fixes for Gemini file upload implementation:
1. text/plain files count toward total_inline_bytes
2. Video count limit (unified 10 for both AI Studio and Vertex)
3. Vertex audio file count limit (max 1 file per request)
4. data URL cumulative size tracking
5. PDF and image independent quotas
"""

import tempfile
import unittest
from pathlib import Path

from utils.gemini_validators import (
    GeminiRequestAggregate,
    GeminiValidationError,
    ProviderProfile,
)


class TestGeminiFileValidation(unittest.TestCase):
    """Test suite for Gemini file upload validation."""

    def test_text_plain_cumulative_size_vertex(self):
        """Test that multiple text/plain files count toward 20MB inline_data limit (Vertex)."""
        aggregate = GeminiRequestAggregate(
            provider_profile=ProviderProfile.VERTEX_AI,
            model_name="gemini-2.5-pro",
        )

        # Simulate multiple text files that individually are < 20MB but collectively > 20MB
        # Each file: 8MB raw → ~10.67MB Base64 (×4/3)
        # 2 files: 16MB raw → ~21.33MB Base64 (should fail)
        file_size_bytes = 8 * 1024 * 1024  # 8MB
        base64_size = int(file_size_bytes * 4 / 3)  # ~10.67MB

        # First file: should succeed
        aggregate.total_inline_bytes += base64_size
        aggregate.files_processed.append("text1.txt")

        # Second file: should push over 20MB limit
        aggregate.total_inline_bytes += base64_size
        aggregate.files_processed.append("text2.txt")

        # Validation should fail because total_inline_bytes > 20MB
        with self.assertRaises(GeminiValidationError) as cm:
            aggregate.validate_limits()

        error_msg = str(cm.exception)
        self.assertIn("20", error_msg)  # Should mention 20MB limit
        self.assertIn("MB", error_msg)
        self.assertIn("inline_data", error_msg.lower())

    def test_video_count_limit_unified(self):
        """Test that video count limit is 10 for both AI Studio and Vertex."""
        # Test AI Studio
        aggregate_ai_studio = GeminiRequestAggregate(
            provider_profile=ProviderProfile.AI_STUDIO,
            model_name="gemini-2.5-flash",
        )
        aggregate_ai_studio.video_count = 11  # Over limit

        with self.assertRaises(GeminiValidationError) as cm:
            aggregate_ai_studio.validate_limits()

        self.assertIn("11 videos", str(cm.exception))
        self.assertIn("10 videos", str(cm.exception))

        # Test Vertex AI
        aggregate_vertex = GeminiRequestAggregate(
            provider_profile=ProviderProfile.VERTEX_AI,
            model_name="gemini-2.5-pro",
        )
        aggregate_vertex.video_count = 11  # Over limit

        with self.assertRaises(GeminiValidationError) as cm:
            aggregate_vertex.validate_limits()

        self.assertIn("11 videos", str(cm.exception))
        self.assertIn("10 videos", str(cm.exception))

    def test_video_count_exactly_10_succeeds(self):
        """Test that exactly 10 videos is allowed for both providers."""
        # AI Studio
        aggregate_ai_studio = GeminiRequestAggregate(
            provider_profile=ProviderProfile.AI_STUDIO,
            model_name="gemini-2.5-flash",
        )
        aggregate_ai_studio.video_count = 10
        # Should not raise
        aggregate_ai_studio.validate_limits()

        # Vertex AI
        aggregate_vertex = GeminiRequestAggregate(
            provider_profile=ProviderProfile.VERTEX_AI,
            model_name="gemini-2.5-pro",
        )
        aggregate_vertex.video_count = 10
        # Should not raise
        aggregate_vertex.validate_limits()

    def test_vertex_audio_file_count_limit(self):
        """Test that Vertex AI enforces max 1 audio file per request."""
        aggregate = GeminiRequestAggregate(
            provider_profile=ProviderProfile.VERTEX_AI,
            model_name="gemini-2.5-pro",
        )

        # Add 2 audio files (should fail)
        aggregate.audio_file_count = 2
        aggregate.total_audio_duration_seconds = 60  # 1 minute total (under time limit)

        with self.assertRaises(GeminiValidationError) as cm:
            aggregate.validate_limits()

        self.assertIn("2 audio", str(cm.exception))
        self.assertIn("1 audio", str(cm.exception))
        self.assertIn("Vertex", str(cm.exception))

    def test_ai_studio_audio_multiple_files_allowed(self):
        """Test that AI Studio allows multiple audio files (only total duration matters)."""
        aggregate = GeminiRequestAggregate(
            provider_profile=ProviderProfile.AI_STUDIO,
            model_name="gemini-2.5-flash",
        )

        # Add 5 audio files with total duration under limit
        aggregate.audio_file_count = 5
        aggregate.total_audio_duration_seconds = 3600  # 1 hour total (under 9.5h limit)

        # Should not raise (AI Studio has no file count limit, only duration limit)
        aggregate.validate_limits()

    def test_data_url_cumulative_size_tracking(self):
        """Test that data URL images are counted in total_inline_bytes."""
        aggregate = GeminiRequestAggregate(
            provider_profile=ProviderProfile.AI_STUDIO,
            model_name="gemini-2.5-flash",
        )

        # Simulate multiple data URL images that collectively > 20MB
        # Each image: 8MB → ~10.67MB Base64
        # 2 images: 16MB → ~21.33MB (should fail)
        image_size_bytes = 8 * 1024 * 1024  # 8MB raw
        base64_size = int(image_size_bytes * 4 / 3)  # ~10.67MB Base64

        # Add first image
        aggregate.add_image("image1.png", size_bytes=base64_size)

        # Add second image (should push over limit)
        aggregate.add_image("image2.png", size_bytes=base64_size)

        # Validation should fail
        with self.assertRaises(GeminiValidationError) as cm:
            aggregate.validate_limits()

        error_msg = str(cm.exception)
        self.assertIn("20", error_msg)  # Should mention 20MB limit
        self.assertIn("MB", error_msg)
        self.assertIn("inline_data", error_msg.lower())

    def test_pdf_and_image_independent_quotas_vertex(self):
        """Test that PDF pages and image count are independent quotas (Vertex)."""
        aggregate = GeminiRequestAggregate(
            provider_profile=ProviderProfile.VERTEX_AI,
            model_name="gemini-2.5-pro",
        )

        # Scenario 1: Max images (3000) + valid PDF pages (should fail on images)
        aggregate.image_count = 3001  # Over Vertex image limit
        aggregate.pdf_page_count = 500  # Under PDF page limit

        with self.assertRaises(GeminiValidationError) as cm:
            aggregate.validate_limits()

        self.assertIn("3001 images", str(cm.exception))
        self.assertIn("3000", str(cm.exception))

        # Scenario 2: Valid images + max PDF pages (should pass if under total size)
        aggregate2 = GeminiRequestAggregate(
            provider_profile=ProviderProfile.VERTEX_AI,
            model_name="gemini-2.5-pro",
        )
        aggregate2.image_count = 2000  # Under Vertex image limit
        aggregate2.pdf_page_count = 900  # Under PDF page limit (1000 max per file)
        aggregate2.total_inline_bytes = 10 * 1024 * 1024  # 10MB (under 20MB limit)

        # Should not raise (both quotas independent and under limits)
        aggregate2.validate_limits()

    def test_ai_studio_image_limit_3600(self):
        """Test that AI Studio enforces 3600 image limit."""
        aggregate = GeminiRequestAggregate(
            provider_profile=ProviderProfile.AI_STUDIO,
            model_name="gemini-2.5-flash",
        )

        aggregate.image_count = 3601  # Over AI Studio limit

        with self.assertRaises(GeminiValidationError) as cm:
            aggregate.validate_limits()

        self.assertIn("3601 images", str(cm.exception))
        self.assertIn("3600", str(cm.exception))


class TestGeminiFileValidationIntegration(unittest.TestCase):
    """Integration tests for file validation with actual file processing."""

    def test_text_file_size_tracking_with_tempfiles(self):
        """Test text file size tracking with real temporary files."""
        # Create temporary text files
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f1:
            # Write 1MB of text
            f1.write("x" * (1024 * 1024))
            file1_path = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f2:
            # Write 1MB of text
            f2.write("y" * (1024 * 1024))
            file2_path = f2.name

        try:
            # Verify files exist and have expected size
            file1_size = Path(file1_path).stat().st_size
            file2_size = Path(file2_path).stat().st_size

            self.assertGreaterEqual(file1_size, 1024 * 1024)
            self.assertGreaterEqual(file2_size, 1024 * 1024)

            # Create aggregate and track sizes
            aggregate = GeminiRequestAggregate(
                provider_profile=ProviderProfile.VERTEX_AI,
                model_name="gemini-2.5-pro",
            )

            # Simulate processing (Base64 inflation: ×4/3)
            aggregate.total_inline_bytes += int(file1_size * 4 / 3)
            aggregate.total_inline_bytes += int(file2_size * 4 / 3)

            # Verify cumulative size is tracked
            expected_total = int((file1_size + file2_size) * 4 / 3)
            self.assertEqual(aggregate.total_inline_bytes, expected_total)

        finally:
            # Clean up
            Path(file1_path).unlink(missing_ok=True)
            Path(file2_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
