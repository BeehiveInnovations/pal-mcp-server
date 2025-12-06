"""Tests for image validation utility helpers."""

import base64
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from utils.image_utils import DEFAULT_MAX_IMAGE_SIZE_MB, validate_image


class TestImageValidation:
    """Test suite for image validation functionality."""

    def test_validate_data_url_valid(self) -> None:
        """Test validation of valid data URL."""
        # Create a small test image (1x1 PNG)
        test_image_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        data_url = f"data:image/png;base64,{base64.b64encode(test_image_data).decode()}"

        image_bytes, mime_type = validate_image(data_url)

        assert image_bytes == test_image_data
        assert mime_type == "image/png"

    @pytest.mark.parametrize(
        "invalid_url,expected_error",
        [
            ("data:image/png", "Invalid data URL format"),  # Missing base64 part
            ("data:image/png;base64", "Invalid data URL format"),  # Missing data
            ("data:text/plain;base64,dGVzdA==", "Unsupported image type"),  # Not an image
        ],
    )
    def test_validate_data_url_invalid_format(self, invalid_url: str, expected_error: str) -> None:
        """Test validation of malformed data URL."""
        with pytest.raises(ValueError) as excinfo:
            validate_image(invalid_url)
        assert expected_error in str(excinfo.value)

    def test_non_data_url_treated_as_file_path(self) -> None:
        """Test that non-data URLs are treated as file paths."""
        # Test case that's not a data URL at all
        with pytest.raises(ValueError) as excinfo:
            validate_image("image/png;base64,abc123")
        assert "Image file not found" in str(excinfo.value)  # Treated as file path

    def test_validate_data_url_unsupported_type(self) -> None:
        """Test validation of unsupported image type in data URL."""
        data_url = "data:image/bmp;base64,Qk0="  # BMP format

        with pytest.raises(ValueError) as excinfo:
            validate_image(data_url)
        assert "Unsupported image type: image/bmp" in str(excinfo.value)

    def test_validate_data_url_invalid_base64(self) -> None:
        """Test validation of data URL with invalid base64."""
        data_url = "data:image/png;base64,@@@invalid@@@"

        with pytest.raises(ValueError) as excinfo:
            validate_image(data_url)
        assert "Invalid base64 data" in str(excinfo.value)

    def test_validate_large_data_url(self) -> None:
        """Test validation of large data URL to ensure size limits work."""
        # Create a large image (21MB)
        large_data = b"x" * (21 * 1024 * 1024)  # 21MB

        # Encode as base64 and create data URL
        import base64

        encoded_data = base64.b64encode(large_data).decode()
        data_url = f"data:image/png;base64,{encoded_data}"

        # Should fail with default 20MB limit
        with pytest.raises(ValueError) as excinfo:
            validate_image(data_url)
        assert f"Image too large: 21.0MB (max: {DEFAULT_MAX_IMAGE_SIZE_MB:.1f}MB)" in str(excinfo.value)

        # Should succeed with higher limit
        image_bytes, mime_type = validate_image(data_url, max_size_mb=25.0)
        assert len(image_bytes) == len(large_data)
        assert mime_type == "image/png"

    def test_validate_file_path_valid(self) -> None:
        """Test validation of valid image file."""
        # Create a temporary image file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            # Write a small test PNG
            test_image_data = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
            tmp_file.write(test_image_data)
            tmp_file_path = tmp_file.name

        try:
            image_bytes, mime_type = validate_image(tmp_file_path)

            assert image_bytes == test_image_data
            assert mime_type == "image/png"
        finally:
            os.unlink(tmp_file_path)

    def test_validate_file_path_not_found(self) -> None:
        """Test validation of non-existent file."""
        with pytest.raises(ValueError) as excinfo:
            validate_image("/path/to/nonexistent/image.png")
        assert "Image file not found" in str(excinfo.value)

    def test_validate_file_path_unsupported_extension(self) -> None:
        """Test validation of file with unsupported extension."""
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp_file:
            tmp_file.write(b"dummy data")
            tmp_file_path = tmp_file.name

        try:
            with pytest.raises(ValueError) as excinfo:
                validate_image(tmp_file_path)
            assert "Unsupported image format: .bmp" in str(excinfo.value)
        finally:
            os.unlink(tmp_file_path)

    def test_validate_file_path_read_error(self) -> None:
        """Test validation when file cannot be read."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file_path = tmp_file.name

        # Remove the file but keep the path
        os.unlink(tmp_file_path)

        with pytest.raises(ValueError) as excinfo:
            validate_image(tmp_file_path)
        assert "Image file not found" in str(excinfo.value)

    def test_validate_image_size_limit(self) -> None:
        """Test validation of image size limits."""
        # Create a large "image" (just random data)
        large_data = b"x" * (21 * 1024 * 1024)  # 21MB

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(large_data)
            tmp_file_path = tmp_file.name

        try:
            with pytest.raises(ValueError) as excinfo:
                validate_image(tmp_file_path, max_size_mb=20.0)
            assert "Image too large: 21.0MB (max: 20.0MB)" in str(excinfo.value)
        finally:
            os.unlink(tmp_file_path)

    def test_validate_image_custom_size_limit(self) -> None:
        """Test validation with custom size limit."""
        # Create a 2MB "image"
        data = b"x" * (2 * 1024 * 1024)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(data)
            tmp_file_path = tmp_file.name

        try:
            # Should fail with 1MB limit
            with pytest.raises(ValueError) as excinfo:
                validate_image(tmp_file_path, max_size_mb=1.0)
            assert "Image too large: 2.0MB (max: 1.0MB)" in str(excinfo.value)

            # Should succeed with 3MB limit
            image_bytes, mime_type = validate_image(tmp_file_path, max_size_mb=3.0)
            assert len(image_bytes) == len(data)
            assert mime_type == "image/png"
        finally:
            os.unlink(tmp_file_path)

    def test_validate_image_default_size_limit(self) -> None:
        """Test validation with default size limit (None)."""
        # Create a small image that's under the default limit
        data = b"x" * (1024 * 1024)  # 1MB

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_file.write(data)
            tmp_file_path = tmp_file.name

        try:
            # Should succeed with default limit (20MB)
            image_bytes, mime_type = validate_image(tmp_file_path)
            assert len(image_bytes) == len(data)
            assert mime_type == "image/jpeg"

            # Should also succeed when explicitly passing None
            image_bytes, mime_type = validate_image(tmp_file_path, max_size_mb=None)
            assert len(image_bytes) == len(data)
            assert mime_type == "image/jpeg"
        finally:
            os.unlink(tmp_file_path)

    def test_validate_all_supported_formats(self) -> None:
        """Test validation of all supported image formats.

        Note: GIF is NOT supported by Gemini API
        Reference: https://ai.google.dev/gemini-api/docs/vision
        """
        supported_formats = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }

        for ext, expected_mime in supported_formats.items():
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
                tmp_file.write(b"dummy image data")
                tmp_file_path = tmp_file.name

            try:
                image_bytes, mime_type = validate_image(tmp_file_path)
                assert mime_type == expected_mime
                assert image_bytes == b"dummy image data"
            finally:
                os.unlink(tmp_file_path)


class TestProviderIntegration:
    """Test image validation integration with different providers."""

    @patch("providers.gemini.logger")
    def test_gemini_provider_uses_validation(self, mock_logger: Mock) -> None:
        """Test that Gemini provider uses the base validation."""
        from providers.gemini import GeminiModelProvider

        # Create a provider instance
        provider = GeminiModelProvider(api_key="test-key")

        # Test with non-existent file
        result = provider._process_image("/nonexistent/image.png")
        assert result is None
        mock_logger.warning.assert_called_with("Image file not found: /nonexistent/image.png")

    @patch("providers.openai_compatible.logging")
    def test_openai_compatible_provider_uses_validation(self, mock_logging: Mock) -> None:
        """Test that OpenAI-compatible providers use the base validation."""
        from providers.xai import XAIModelProvider

        # Create a provider instance (XAI inherits from OpenAICompatibleProvider)
        provider = XAIModelProvider(api_key="test-key")

        # Test with non-existent file
        result = provider._process_image("/nonexistent/image.png")
        assert result is None
        mock_logging.warning.assert_called_with("Image file not found: /nonexistent/image.png")

    def test_data_url_preservation(self) -> None:
        """Test that data URLs are properly preserved through validation."""
        from providers.xai import XAIModelProvider

        provider = XAIModelProvider(api_key="test-key")

        # Valid data URL
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

        result = provider._process_image(data_url)
        assert result is not None
        assert result["type"] == "image_url"
        assert result["image_url"]["url"] == data_url
