"""Tests for OpenAI token estimation utilities."""

import os
import tempfile

import pytest

from utils import openai_token_estimator


class TestOpenAIModelDetection:
    """Test OpenAI model detection functions."""

    def test_is_openai_model_direct(self):
        """Test detection of direct OpenAI model names."""
        assert openai_token_estimator.is_openai_model("gpt-4o")
        assert openai_token_estimator.is_openai_model("gpt-5")
        assert openai_token_estimator.is_openai_model("gpt-5-pro")
        assert openai_token_estimator.is_openai_model("o3")
        assert openai_token_estimator.is_openai_model("o4-mini")

    def test_is_openai_model_openrouter(self):
        """Test detection of OpenRouter-proxied OpenAI models."""
        assert openai_token_estimator.is_openai_model("openai/gpt-4o")
        assert openai_token_estimator.is_openai_model("openai/gpt-5")
        assert openai_token_estimator.is_openai_model("openai/o3-mini")

    def test_is_openai_model_non_openai(self):
        """Test rejection of non-OpenAI models."""
        assert not openai_token_estimator.is_openai_model("gemini-2.5-pro")
        assert not openai_token_estimator.is_openai_model("claude-3-opus")
        assert not openai_token_estimator.is_openai_model("llama-3-70b")


class TestTextTokenEstimation:
    """Test text token counting."""

    def test_calculate_text_tokens_with_tiktoken(self):
        """Test text token calculation with tiktoken."""
        text = "Hello, world! This is a test."
        tokens = openai_token_estimator.calculate_text_tokens("gpt-4o", text)
        assert tokens > 0
        # Should be more accurate than simple char count
        assert tokens < len(text)

    def test_calculate_text_tokens_empty(self):
        """Test empty text handling."""
        assert openai_token_estimator.calculate_text_tokens("gpt-4o", "") == 0

    def test_calculate_text_tokens_unknown_model(self):
        """Test text token calculation with unknown model (uses encoding inference)."""
        text = "Hello, world! This is a test."
        # Unknown model will fall back to cl100k_base or o200k_base
        tokens = openai_token_estimator.calculate_text_tokens("gpt-unknown", text)
        assert tokens > 0
        assert tokens < len(text)


class TestImageTokenEstimation:
    """Test image token estimation."""

    @pytest.mark.parametrize(
        "detail,expected_tokens",
        [
            ("LOW", 85),  # Fixed base tokens for low detail
            ("low", 85),  # Case-insensitive
            ("HIGH", 85),  # Small image: 85 base + tiles (>= 85)
            ("high", 85),  # Case-insensitive
        ],
    )
    def test_estimate_image_tokens_tile_based(self, detail, expected_tokens):
        """Test tile-based estimation with different detail levels (case-insensitive)."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            # Create a minimal PNG (1x1 pixel)
            tmp.write(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
                b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            tmp_path = tmp.name

        try:
            tokens = openai_token_estimator.estimate_image_tokens(tmp_path, "gpt-4o", detail)
            assert tokens >= expected_tokens
        finally:
            os.unlink(tmp_path)

    def test_estimate_image_tokens_file_not_found(self):
        """Test error handling for missing image file."""
        with pytest.raises(ValueError, match="Image file not found"):
            openai_token_estimator.estimate_image_tokens("/nonexistent/image.png", "gpt-4o", "HIGH")


class TestPDFTokenEstimation:
    """Test PDF token estimation."""

    def test_estimate_pdf_tokens_simple(self):
        """Test PDF token estimation with simple text PDF."""
        # Create a minimal valid PDF with text
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
            b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td (Hello World) Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000300 00000 n\n"
            b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n394\n%%EOF"
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_content)
            tmp_path = tmp.name

        try:
            tokens = openai_token_estimator.estimate_pdf_tokens(tmp_path, "gpt-4o", "HIGH")
            # Should have: text tokens + (1 page × image tokens per page)
            # At minimum: some text tokens + base image tokens
            assert tokens > 85  # At least base image tokens for 1 page
        finally:
            os.unlink(tmp_path)

    def test_estimate_pdf_tokens_file_not_found(self):
        """Test error handling for missing PDF file."""
        with pytest.raises(ValueError, match="PDF file not found"):
            openai_token_estimator.estimate_pdf_tokens("/nonexistent/document.pdf", "gpt-4o", "HIGH")


class TestFileTokenEstimation:
    """Test complete file token estimation."""

    def test_estimate_tokens_for_files_empty(self):
        """Test empty file list."""
        assert openai_token_estimator.estimate_tokens_for_files("gpt-4o", [], "HIGH") == 0

    def test_estimate_tokens_for_files_text(self):
        """Test text file token estimation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("Hello, world! This is a test file.")
            tmp_path = tmp.name

        try:
            files = [{"path": tmp_path, "mime_type": "text/plain"}]
            tokens = openai_token_estimator.estimate_tokens_for_files("gpt-4o", files, "HIGH")
            assert tokens > 0
        finally:
            os.unlink(tmp_path)

    def test_estimate_tokens_for_files_image(self):
        """Test image file token estimation."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            # Minimal PNG
            tmp.write(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
                b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            tmp_path = tmp.name

        try:
            files = [{"path": tmp_path, "mime_type": "image/png"}]
            tokens = openai_token_estimator.estimate_tokens_for_files("gpt-4o", files, "HIGH")
            assert tokens >= 85  # At least base tokens
        finally:
            os.unlink(tmp_path)

    @pytest.mark.parametrize(
        "suffix,mime_type,error_pattern",
        [
            (".mp3", "audio/mpeg", "does not support audio"),
            (".mp4", "video/mp4", "does not support video"),
        ],
    )
    def test_estimate_tokens_for_files_unsupported_media(self, suffix, mime_type, error_pattern):
        """Test unsupported media files (audio/video) raise errors."""
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(b"fake media content")
            tmp_path = tmp.name

        try:
            files = [{"path": tmp_path, "mime_type": mime_type}]
            with pytest.raises(openai_token_estimator.UnsupportedContentTypeError, match=error_pattern):
                openai_token_estimator.estimate_tokens_for_files("gpt-4o", files, "HIGH")
        finally:
            os.unlink(tmp_path)

    @pytest.mark.parametrize(
        "use_responses_api,should_succeed",
        [
            (False, False),  # PDF requires Responses API
            (True, True),  # PDF works with Responses API
        ],
    )
    def test_estimate_tokens_for_files_pdf_responses_api(self, use_responses_api, should_succeed):
        """Test PDF files require Responses API enabled."""
        # Create a minimal valid PDF
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
            b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td (Hello World) Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000300 00000 n\n"
            b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n394\n%%EOF"
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_content)
            tmp_path = tmp.name

        try:
            files = [{"path": tmp_path, "mime_type": "application/pdf"}]
            if should_succeed:
                # With use_responses_api=True, should work
                tokens = openai_token_estimator.estimate_tokens_for_files(
                    "gpt-4o", files, "HIGH", use_responses_api=use_responses_api
                )
                # Should have text tokens + image tokens per page
                assert tokens > 85  # At least base image tokens for 1 page
            else:
                # Without use_responses_api=True, should raise error
                with pytest.raises(
                    openai_token_estimator.UnsupportedContentTypeError, match="PDF/document files .* Responses API"
                ):
                    openai_token_estimator.estimate_tokens_for_files(
                        "gpt-4o", files, "HIGH", use_responses_api=use_responses_api
                    )
        finally:
            os.unlink(tmp_path)

    def test_estimate_tokens_for_files_unsupported_mime(self):
        """Test unsupported mime type raises error."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            tmp.write(b"binary data")
            tmp_path = tmp.name

        try:
            files = [{"path": tmp_path, "mime_type": "application/octet-stream"}]
            with pytest.raises(openai_token_estimator.UnsupportedContentTypeError, match="does not support mime type"):
                openai_token_estimator.estimate_tokens_for_files("gpt-4o", files, "HIGH")
        finally:
            os.unlink(tmp_path)
