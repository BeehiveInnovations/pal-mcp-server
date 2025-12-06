"""Gemini API file validation utilities.

This module provides pre-upload validation for files to ensure they meet
Gemini API limits before sending requests.

Official Documentation:
- Document Processing (PDF): https://ai.google.dev/gemini-api/docs/document-processing
- Image Understanding: https://ai.google.dev/gemini-api/docs/vision
- Audio Understanding: https://ai.google.dev/gemini-api/docs/audio
- Video Understanding: https://ai.google.dev/gemini-api/docs/video-understanding
- Vertex AI Multimodal: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/overview
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

logger = logging.getLogger(__name__)

# ==============================================================================
# Provider Profiles
# ==============================================================================


class ProviderProfile(str, Enum):
    """Gemini provider profiles with different limits.

    Reference:
    - AI Studio: https://ai.google.dev/gemini-api/docs/vision
    - Vertex AI: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-understanding
    """

    AI_STUDIO = "aistudio"
    VERTEX_AI = "vertex"


# ==============================================================================
# Gemini API Limits (Official Documentation)
# ==============================================================================

# PDF limits
# Reference: https://ai.google.dev/gemini-api/docs/document-processing
# Both AI Studio and Vertex AI: 1000 pages per file
MAX_PDF_PAGES_PER_FILE = 1000

# Vertex AI specific: 50MB per PDF file
# Reference: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/document-understanding
MAX_PDF_SIZE_VERTEX_MB = 50

# Audio limits
# Reference: https://ai.google.dev/gemini-api/docs/audio
# Total audio duration across all files: 9.5 hours
MAX_AUDIO_DURATION_HOURS = 9.5
MAX_AUDIO_DURATION_SECONDS = MAX_AUDIO_DURATION_HOURS * 3600

# Video limits
# Reference (AI Studio): https://ai.google.dev/gemini-api/docs/video-understanding
#   - Documentation suggests single video as "best practice" but does not specify hard limit
#   - No official hard restriction found for multiple videos
# Reference (Vertex AI): https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models/gemini-2-0-flash
#                        https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models/gemini-2-5-flash
#   - Gemini 1.5/2.0/2.5: Maximum 10 videos per request (official limit)
# Confirmed: 2025-11-05
#
# Implementation note: Using 10 videos as unified limit for both AI Studio and Vertex
# to align with Vertex's official limit and avoid overly restrictive enforcement
MAX_VIDEO_COUNT = 10

# Video duration limits (depends on context window and resolution)
# Reference: https://ai.google.dev/gemini-api/docs/video-understanding
#
# 1M context window:
#   - MEDIUM/HIGH resolution: 1 hour
#   - LOW resolution: 3 hours
#
# 2M context window:
#   - MEDIUM/HIGH resolution: 2 hours
#   - LOW resolution: 6 hours
VIDEO_DURATION_LIMITS = {
    "1M": {
        "DEFAULT": 3600,  # 1 hour in seconds
        "LOW": 10800,  # 3 hours in seconds
    },
    "2M": {
        "DEFAULT": 7200,  # 2 hours in seconds
        "LOW": 21600,  # 6 hours in seconds
    },
}

RECOMMENDED_VIDEO_INLINE_SECONDS = 60  # Recommended for inline_data

# Inline data size limits
# Reference: Gemini API total request size limit (includes prompt + all files)
INLINE_DATA_SOFT_LIMIT_MB = 18.0  # Soft warning threshold
INLINE_DATA_HARD_LIMIT_MB = 20.0  # Hard limit

# ==============================================================================
# MIME Canonicalization & Whitelist
# ==============================================================================

SYNONYM_MIME_MAP: dict[str, str] = {
    # Documents
    "application/x-pdf": "application/pdf",
    # Audio
    "audio/mp3": "audio/mpeg",
    "audio/wave": "audio/wav",
    "audio/x-wav": "audio/wav",
    "audio/x-aiff": "audio/aiff",
    "audio/m4a": "audio/mp4",
    "audio/x-aac": "audio/aac",
    # Video
    "video/mov": "video/quicktime",
    "video/avi": "video/x-msvideo",
    "video/mpg": "video/mpeg",
    "video/wmv": "video/x-ms-wmv",
    "video/x-m4v": "video/mp4",
}


def canonicalize_mime(mime_type: str) -> str:
    """Canonicalize MIME type to standard form."""
    if not mime_type:
        return mime_type
    mt = mime_type.strip().lower()
    return SYNONYM_MIME_MAP.get(mt, mt)


# Image limits
# Reference:
# - AI Studio: https://ai.google.dev/gemini-api/docs/vision (3600 images, no per-image size limit)
# - Vertex AI: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-understanding (3000 images, 7MB per image)
MAX_IMAGE_COUNT_AI_STUDIO = 3600
MAX_IMAGE_COUNT_VERTEX = 3000
MAX_IMAGE_SIZE_VERTEX_MB = 7  # Vertex AI only

# Note: We do NOT validate image file sizes in this implementation.
# Rationale:
# - The 20MB total request limit (inline_data) includes prompt + all files
# - We cannot accurately predict the final serialized request size
# - Let the API return accurate errors for size issues
# - For Vertex AI, the 7MB per-image limit will be enforced by the API
#
# Future consideration: Add optional size pre-check with Files API fallback


# ==============================================================================
# MIME Type Whitelists
# Reference (AI Studio): https://ai.google.dev/gemini-api/docs/vision
# Reference (Vertex): https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models/gemini-2-5-flash
# Confirmed: 2025-11-05
# ==============================================================================

# AI Studio supports HEIC/HEIF; Vertex only supports PNG/JPEG/WEBP
ALLOWED_IMAGE_MIMES_AI_STUDIO = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "image/heif",
}

ALLOWED_IMAGE_MIMES_VERTEX = {
    "image/png",
    "image/jpeg",
    "image/webp",
}

ALLOWED_AUDIO_MIMES = {
    "audio/wav",
    "audio/aiff",
    "audio/aac",
    "audio/ogg",  # OGG Vorbis
    "audio/flac",
    "audio/mpeg",
    "audio/mp4",
    "audio/mpga",  # MPEG Audio
    "audio/webm",  # WebM Audio
    "audio/pcm",  # PCM/RAW
}

ALLOWED_VIDEO_MIMES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-flv",
    "video/webm",
    "video/x-ms-wmv",
    "video/3gpp",
}

# Both AI Studio and Vertex support PDF and plain text documents
# Reference (AI Studio): https://ai.google.dev/api/files (Files API supports text/plain)
# Reference (Vertex): https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models/gemini-2-5-pro
# Confirmed: 2025-11-05
ALLOWED_DOCUMENT_MIMES_AI_STUDIO = {
    "application/pdf",
    "text/plain",
}

ALLOWED_DOCUMENT_MIMES_VERTEX = {
    "application/pdf",
    "text/plain",
}

# ==============================================================================
# Helper Functions
# ==============================================================================


def calculate_base64_size(raw_bytes: int) -> int:
    """Calculate exact Base64 encoded size for raw bytes.

    Base64 encoding converts 3 bytes to 4 characters, padding with '=' if needed.
    Formula: 4 * ceil(raw_bytes / 3) = 4 * ((raw_bytes + 2) // 3)

    Reference: RFC 4648 - The Base16, Base32, and Base64 Data Encodings
    https://www.rfc-editor.org/rfc/rfc4648

    Args:
        raw_bytes: Number of raw bytes before encoding

    Returns:
        Exact number of bytes in Base64 encoded output
    """
    if raw_bytes <= 0:
        return 0
    return 4 * ((raw_bytes + 2) // 3)


# ==============================================================================
# Validation Functions
# ==============================================================================


class GeminiValidationError(ValueError):
    """Raised when file validation fails against Gemini API limits."""

    pass


def validate_mime_type(
    mime_type: str, file_name: str = "file", provider_profile: ProviderProfile = ProviderProfile.AI_STUDIO
) -> None:
    """Validate MIME type against Gemini API whitelist.

    Reference (AI Studio): https://ai.google.dev/gemini-api/docs/vision
    Reference (Vertex): https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models/gemini-2-5-flash

    Args:
        mime_type: MIME type to validate
        file_name: File name for error messages
        provider_profile: Provider profile for MIME validation

    Raises:
        GeminiValidationError: If MIME type is not supported
    """
    # Select MIME whitelists based on provider
    if provider_profile == ProviderProfile.VERTEX_AI:
        allowed_image_mimes = ALLOWED_IMAGE_MIMES_VERTEX
        allowed_document_mimes = ALLOWED_DOCUMENT_MIMES_VERTEX
        supported_images = "PNG, JPEG, WEBP"
        supported_docs = "PDF, TXT"
    else:
        allowed_image_mimes = ALLOWED_IMAGE_MIMES_AI_STUDIO
        allowed_document_mimes = ALLOWED_DOCUMENT_MIMES_AI_STUDIO
        supported_images = "PNG, JPEG, WEBP, HEIC, HEIF"
        supported_docs = "PDF, TXT"

    allowed_mimes = allowed_image_mimes | ALLOWED_AUDIO_MIMES | ALLOWED_VIDEO_MIMES | allowed_document_mimes

    canonical_mime = canonicalize_mime(mime_type)
    if not canonical_mime or canonical_mime not in allowed_mimes:
        normalized = canonical_mime or (mime_type.strip().lower() if mime_type else "unknown")
        raise GeminiValidationError(
            f"File '{file_name}' has unsupported MIME type '{mime_type}'. "
            f"Normalized type: '{normalized}'. "
            f"Supported types for {provider_profile.value}: "
            f"images ({supported_images}), "
            f"audio (WAV, MP3, AIFF, AAC, OGG, FLAC), "
            f"video (MP4, MPEG, QuickTime/MOV, AVI, FLV, WEBM, WMV, 3GPP), "
            f"documents ({supported_docs}). "
            f"See: https://ai.google.dev/gemini-api/docs/vision"
        )


def validate_pdf_pages(num_pages: int, file_name: str = "PDF") -> None:
    """Validate PDF page count.

    Reference: https://ai.google.dev/gemini-api/docs/document-processing
    Each PDF file can have up to 1,000 pages (both AI Studio and Vertex AI).

    Args:
        num_pages: Number of pages in PDF
        file_name: File name for error messages

    Raises:
        GeminiValidationError: If PDF has too many pages
    """
    if num_pages > MAX_PDF_PAGES_PER_FILE:
        raise GeminiValidationError(
            f"PDF '{file_name}' has {num_pages} pages, "
            f"exceeds maximum of {MAX_PDF_PAGES_PER_FILE} pages per file. "
            f"See: https://ai.google.dev/gemini-api/docs/document-processing"
        )


def validate_audio_duration(duration_seconds: float, file_name: str = "audio") -> None:
    """Validate audio file duration.

    Reference: https://ai.google.dev/gemini-api/docs/audio
    Note: This validates individual file duration. Total duration is validated
    at the request level (9.5 hours total across all audio files).

    Args:
        duration_seconds: Audio duration in seconds
        file_name: File name for error messages

    Raises:
        GeminiValidationError: If audio duration is invalid
    """
    if duration_seconds <= 0:
        raise GeminiValidationError(f"Audio file '{file_name}' has invalid duration: {duration_seconds}s")


def validate_video_duration(
    duration_seconds: float,
    file_name: str = "video",
    media_resolution: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM",
    context_window: Literal["1M", "2M"] = "1M",
) -> None:
    """Validate video file duration.

    Reference: https://ai.google.dev/gemini-api/docs/video-understanding

    Duration limits vary by context window and resolution:
    - 1M context: 1 hour (MEDIUM/HIGH) or 3 hours (LOW)
    - 2M context: 2 hours (MEDIUM/HIGH) or 6 hours (LOW)

    Args:
        duration_seconds: Video duration in seconds
        file_name: File name for error messages
        media_resolution: Resolution setting (LOW/MEDIUM/HIGH)
        context_window: Model context window size (1M or 2M)

    Raises:
        GeminiValidationError: If video is too long
    """
    # Determine max duration based on resolution and context window
    limits = VIDEO_DURATION_LIMITS.get(context_window, VIDEO_DURATION_LIMITS["1M"])
    max_duration = limits["LOW"] if media_resolution == "LOW" else limits["DEFAULT"]

    if duration_seconds > max_duration:
        duration_minutes = duration_seconds / 60
        max_minutes = max_duration / 60
        raise GeminiValidationError(
            f"Video file '{file_name}' is {duration_minutes:.1f} minutes long, "
            f"exceeds maximum of {max_minutes:.1f} minutes for "
            f"{media_resolution} resolution with {context_window} context window. "
            f"See: https://ai.google.dev/gemini-api/docs/video-understanding"
        )

    # Warn if using inline_data for long videos
    if duration_seconds > RECOMMENDED_VIDEO_INLINE_SECONDS:
        logger.warning(
            f"Video '{file_name}' is {duration_seconds:.0f}s. "
            f"Consider using Files API for videos >{RECOMMENDED_VIDEO_INLINE_SECONDS}s."
        )


def validate_inline_data_size(size_bytes: int, file_name: str = "file") -> None:
    """Validate inline_data payload size before upload.

    Args:
        size_bytes: File size in bytes
        file_name: File name for error messages

    Raises:
        GeminiValidationError: If inline_data exceeds hard limit (20MB)
    """
    if size_bytes < 0:
        raise GeminiValidationError(f"File '{file_name}' has invalid inline data size: {size_bytes} bytes.")

    size_mb = size_bytes / (1024**2)

    if size_mb > INLINE_DATA_HARD_LIMIT_MB:
        raise GeminiValidationError(
            f"File '{file_name}' is {size_mb:.2f}MB, exceeds inline_data hard limit of "
            f"{INLINE_DATA_HARD_LIMIT_MB:.1f}MB. Consider using the Files API."
        )

    if size_mb > INLINE_DATA_SOFT_LIMIT_MB:
        logger.warning(
            f"File '{file_name}' is {size_mb:.2f}MB, approaching inline_data hard limit of "
            f"{INLINE_DATA_HARD_LIMIT_MB:.1f}MB. Consider using the Files API."
        )


# ==============================================================================
# Request Aggregation
# ==============================================================================


@dataclass
class GeminiRequestAggregate:
    """Aggregates file counts and metadata across a single request.

    Used to validate cumulative limits (total audio duration, video count,
    image + PDF page count, etc.)

    Reference:
    - https://ai.google.dev/gemini-api/docs/vision
    - https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-understanding
    """

    # Counters
    image_count: int = 0
    video_count: int = 0
    audio_file_count: int = 0  # Vertex AI: maximum 1 audio file per request
    pdf_page_count: int = 0  # Tracked separately from images (independent quotas)

    # Accumulators
    total_audio_duration_seconds: float = 0.0
    total_inline_bytes: int = 0  # Cumulative inline_data size (raw bytes × 4/3 for Base64)
    # Note: Official documentation does NOT specify a cumulative video duration limit.
    # Only individual video duration limits exist (based on context window and resolution).
    # Reference: https://ai.google.dev/gemini-api/docs/video-understanding

    # Configuration
    provider_profile: ProviderProfile = ProviderProfile.AI_STUDIO
    model_name: str = ""  # Used to determine video count limit

    # File tracking
    files_processed: list[str] = field(default_factory=list)

    def add_image(self, file_name: str, size_bytes: int = 0) -> None:
        """Add an image to the aggregate."""
        self.image_count += 1
        if size_bytes > 0:
            self.total_inline_bytes += calculate_base64_size(size_bytes)
        self.files_processed.append(file_name)

    def add_pdf(self, file_name: str, num_pages: int, size_bytes: int = 0) -> None:
        """Add a PDF to the aggregate.

        Note: PDFs and images have separate quotas in both AI Studio and Vertex AI.
        Reference: https://ai.google.dev/gemini-api/docs/document-processing
        """
        self.pdf_page_count += num_pages
        if size_bytes > 0:
            self.total_inline_bytes += calculate_base64_size(size_bytes)
        self.files_processed.append(file_name)

    def add_audio(self, file_name: str, duration_seconds: float, size_bytes: int = 0) -> None:
        """Add an audio file to the aggregate."""
        self.audio_file_count += 1
        self.total_audio_duration_seconds += duration_seconds
        if size_bytes > 0:
            self.total_inline_bytes += calculate_base64_size(size_bytes)
        self.files_processed.append(file_name)

    def add_video(self, file_name: str, size_bytes: int = 0) -> None:
        """Add a video file to the aggregate.

        Note: Individual video duration is validated in validate_video_duration().
        No cumulative duration limit is specified in official documentation.
        Reference: https://ai.google.dev/gemini-api/docs/video-understanding
        """
        self.video_count += 1
        if size_bytes > 0:
            self.total_inline_bytes += calculate_base64_size(size_bytes)
        self.files_processed.append(file_name)

    def validate_limits(self) -> None:
        """Validate all aggregate limits.

        Reference:
        - AI Studio: https://ai.google.dev/gemini-api/docs/vision
        - Vertex AI: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-understanding

        Raises:
            GeminiValidationError: If any limit is exceeded
        """
        # Determine provider-specific limits
        max_image_count = (
            MAX_IMAGE_COUNT_AI_STUDIO if self.provider_profile == ProviderProfile.AI_STUDIO else MAX_IMAGE_COUNT_VERTEX
        )

        # Check image count (images and PDFs are separate quotas)
        # Reference:
        # - AI Studio: 3,600 images per request (separate from PDF quota)
        # - Vertex AI: 3,000 images per request (separate from document quota)
        # Both providers treat images and documents as independent limits
        if self.image_count > max_image_count:
            raise GeminiValidationError(
                f"Request contains {self.image_count} images, "
                f"exceeds maximum of {max_image_count} for {self.provider_profile.value}. "
                f"See: https://ai.google.dev/gemini-api/docs/vision"
            )

        # Check video count (unified limit for both providers)
        # Vertex AI: Official limit of 10 videos per request
        # AI Studio: No official hard limit found; using 10 to align with Vertex
        # Reference (AI Studio): https://ai.google.dev/gemini-api/docs/video-understanding
        # Reference (Vertex): https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models/gemini-2-0-flash
        if self.video_count > MAX_VIDEO_COUNT:
            raise GeminiValidationError(
                f"Request contains {self.video_count} videos, "
                f"exceeds maximum of {MAX_VIDEO_COUNT} videos per request. "
                f"See: https://ai.google.dev/gemini-api/docs/video-understanding"
            )

        # Check audio file count (Vertex AI only)
        # Reference: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/audio-understanding
        if self.provider_profile == ProviderProfile.VERTEX_AI and self.audio_file_count > 1:
            raise GeminiValidationError(
                f"Request contains {self.audio_file_count} audio files, "
                f"Vertex AI allows maximum 1 audio file per request. "
                f"See: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/audio-understanding"
            )

        # Check audio duration (different limits for AI Studio vs Vertex AI)
        # AI Studio: 9.5 hours | Vertex AI: 8.4 hours (~1M tokens)
        # Reference: https://ai.google.dev/gemini-api/docs/audio
        # Reference: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/audio-understanding
        max_audio_hours = 8.4 if self.provider_profile == ProviderProfile.VERTEX_AI else MAX_AUDIO_DURATION_HOURS
        max_audio_seconds = max_audio_hours * 3600

        if self.total_audio_duration_seconds > max_audio_seconds:
            total_hours = self.total_audio_duration_seconds / 3600
            raise GeminiValidationError(
                f"Request contains {total_hours:.2f} hours of audio total, "
                f"exceeds maximum of {max_audio_hours} hours per request for {self.provider_profile.value}. "
                f"See: https://ai.google.dev/gemini-api/docs/audio"
            )

        # Check total inline_data size (cumulative across all files with Base64 inflation)
        # Reference: 20MB total request size limit
        if self.total_inline_bytes > 0:
            total_mb = self.total_inline_bytes / (1024**2)
            if total_mb > INLINE_DATA_HARD_LIMIT_MB:
                raise GeminiValidationError(
                    f"Request total inline_data is {total_mb:.2f}MB (after Base64 encoding), "
                    f"exceeds hard limit of {INLINE_DATA_HARD_LIMIT_MB:.1f}MB. "
                    f"Consider using the Files API for large files."
                )
            if total_mb > INLINE_DATA_SOFT_LIMIT_MB:
                logger.warning(
                    f"Request total inline_data is {total_mb:.2f}MB, "
                    f"approaching hard limit of {INLINE_DATA_HARD_LIMIT_MB:.1f}MB. "
                    f"Consider using the Files API."
                )

        logger.debug(
            f"Gemini request validation passed: "
            f"{len(self.files_processed)} files, "
            f"{self.image_count} images, "
            f"{self.video_count} videos, "
            f"{self.audio_file_count} audio files, "
            f"{self.pdf_page_count} PDF pages, "
            f"{self.total_audio_duration_seconds:.1f}s audio, "
            f"{self.total_inline_bytes / (1024**2):.2f}MB inline_data, "
            f"provider={self.provider_profile.value}"
        )
