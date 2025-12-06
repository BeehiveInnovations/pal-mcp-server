"""Shared Gemini token estimation utilities.

This module provides reusable token estimation logic for Gemini models,
enabling accurate token counting for both direct Gemini API and OpenRouter-proxied calls.

The estimators follow official Gemini API specifications:
- Text: LocalTokenizer (SentencePiece) with character-based fallback
- Images: 258 tokens (small/old models) or tile-based (Gemini 2.0+)
- PDFs: 258 tokens per page
- Videos: ~300 tokens/sec (default) or ~100 tokens/sec (LOW resolution)
- Audio: 32 tokens per second
"""

import logging
import math

import imagesize
import pypdf
from tinytag import TinyTag

logger = logging.getLogger(__name__)

# Fallback values for token estimation when metadata is unavailable
FALLBACK_PDF_PAGE_COUNT = 10  # Conservative estimate for corrupted/unreadable PDFs
FALLBACK_MEDIA_DURATION_SECONDS = 10.0  # Conservative estimate for audio/video without duration metadata
FALLBACK_VIDEO_TOKENS = 3000  # Fallback for corrupted video (10 sec * 300 tokens/sec)
FALLBACK_AUDIO_TOKENS = 320  # Fallback for corrupted audio (10 sec * 32 tokens/sec)

# Optional: LocalTokenizer for accurate text token counting
# This is the only optional dependency (requires google-genai[local-tokenizer])
try:
    from google.genai.local_tokenizer import LocalTokenizer

    _HAS_LOCAL_TOKENIZER = True
except ImportError:
    _HAS_LOCAL_TOKENIZER = False


def is_gemini_model(model_name: str) -> bool:
    """Check if a model name refers to a Gemini model.

    Handles both direct Gemini names (gemini-2.5-pro) and OpenRouter
    proxied names (google/gemini-2.5-pro).

    Args:
        model_name: Model name to check

    Returns:
        True if model is Gemini, False otherwise
    """
    model_lower = model_name.lower()
    # Direct Gemini models
    if model_lower.startswith("gemini-") or model_lower.startswith("gemini"):
        return True
    # OpenRouter's Gemini models (google/gemini-*)
    if model_lower.startswith("google/gemini"):
        return True
    return False


def is_pre_gemini_2_model(model_name: str) -> bool:
    """Check if model is pre-Gemini 2.0 (1.0 or 1.5 series).

    Pre-2.0 models use fixed 258 token count for images instead of tiling.

    Args:
        model_name: The model name to check

    Returns:
        True if model is Gemini 1.x, False otherwise
    """
    # Strip provider prefix (e.g., "google/")
    clean_name = model_name.replace("google/", "").lower()

    # Check if it's a 1.x versioned model
    if clean_name.startswith("gemini-1."):
        return True

    # Legacy aliases (gemini-pro, gemini-pro-vision) map to 1.0
    if clean_name in {"gemini-pro", "gemini-pro-vision"}:
        return True

    return False


def calculate_text_tokens(model_name: str, content: str) -> int:
    """Calculate text token count using LocalTokenizer.

    Uses Gemini's official offline tokenizer (SentencePiece) when available,
    with fallback to conservative character-based estimation.

    Args:
        model_name: The model to count tokens for (may include provider prefix)
        content: Text content

    Returns:
        Token count
    """
    if not content:
        return 0

    # Strip provider prefix for LocalTokenizer (e.g., "google/gemini-2.5-pro" → "gemini-2.5-pro")
    tokenizer_model = model_name.replace("google/", "")

    if _HAS_LOCAL_TOKENIZER:
        try:
            tokenizer = LocalTokenizer(model_name=tokenizer_model)
            result = tokenizer.count_tokens(content)
            return result.total_tokens
        except Exception as e:
            logger.debug("LocalTokenizer failed for %s: %s, using fallback", model_name, e)

    # Fallback: Conservative character-based estimation (1 token ≈ 4 chars)
    return len(content) // 4


def estimate_image_tokens(file_path: str, model_name: str) -> int:
    """Estimate image token count per Gemini API specification.

    Reference: https://ai.google.dev/gemini-api/docs/tokens

    Formula:
    - Small images (width AND height ≤384px): 258 tokens
    - Gemini 1.5 and earlier: Fixed 258 tokens (no tiling)
    - Gemini 2.0+: Fixed 768×768 tiles, tiles=ceil(w/768)×ceil(h/768), tokens=258*tiles

    Args:
        file_path: Path to the image file
        model_name: Model name for version-specific calculation

    Returns:
        Estimated token count

    Raises:
        ValueError: If file cannot be accessed (not found, permission denied, etc.)
    """
    try:
        width, height = imagesize.get(file_path)

        # Small images: 258 tokens
        if width <= 384 and height <= 384:
            return 258

        # Gemini 1.5 and earlier: Fixed 258 tokens
        if is_pre_gemini_2_model(model_name):
            return 258

        # Gemini 2.0+: Tile-based calculation (768×768 tiles)
        tiles_x = math.ceil(width / 768)
        tiles_y = math.ceil(height / 768)
        return 258 * tiles_x * tiles_y

    except (FileNotFoundError, PermissionError, OSError) as e:
        # File access errors should be raised with specific messages
        if isinstance(e, FileNotFoundError):
            raise ValueError(f"Image file not found for token estimation: {file_path}") from e
        elif isinstance(e, PermissionError):
            raise ValueError(f"Permission denied accessing image file: {file_path}") from e
        else:
            raise ValueError(f"Cannot access image file {file_path}: {e}") from e
    except Exception as e:
        # Other errors (parsing issues, corrupted image) - use fallback
        logger.warning("Image token estimation failed for %s: %s, using fallback", file_path, e)
        return 258


def estimate_pdf_tokens(file_path: str) -> int:
    """Estimate PDF token count per Gemini API specification.

    Reference: https://ai.google.dev/gemini-api/docs/document-processing

    Formula: 258 tokens per page

    Args:
        file_path: Path to the PDF file

    Returns:
        Estimated token count

    Raises:
        ValueError: If file cannot be accessed (not found, permission denied, etc.)
    """
    try:
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            num_pages = len(reader.pages)
        return 258 * num_pages

    except (FileNotFoundError, PermissionError, OSError) as e:
        # File access errors should be raised with specific messages
        if isinstance(e, FileNotFoundError):
            raise ValueError(f"PDF file not found for token estimation: {file_path}") from e
        elif isinstance(e, PermissionError):
            raise ValueError(f"Permission denied accessing PDF file: {file_path}") from e
        else:
            raise ValueError(f"Cannot access PDF file {file_path}: {e}") from e
    except Exception as e:
        # Other errors (parsing issues, corrupted PDF) - use fallback
        logger.warning("PDF token estimation failed for %s: %s, using fallback", file_path, e)
        return 258 * FALLBACK_PDF_PAGE_COUNT  # Conservative fallback


def estimate_video_tokens(file_path: str, media_resolution: str = "MEDIUM") -> int:
    """Estimate video token count per Gemini API specification.

    Formula:
    - LOW resolution: ~100 tokens/sec
    - MEDIUM/HIGH resolution: ~300 tokens/sec

    Args:
        file_path: Path to the video file
        media_resolution: Media resolution setting ("LOW", "MEDIUM", or "HIGH")

    Returns:
        Estimated token count

    Raises:
        ValueError: If file cannot be accessed (not found, permission denied, etc.)
    """
    try:
        tag = TinyTag.get(file_path)
        duration_seconds = tag.duration

        if duration_seconds is None:
            logger.warning("Could not extract video duration from %s", file_path)
            duration_seconds = FALLBACK_MEDIA_DURATION_SECONDS  # Fallback

        # Determine tokens per second based on media resolution
        if media_resolution.upper() == "LOW":
            tokens_per_second = 100
        else:
            tokens_per_second = 300

        return int(duration_seconds * tokens_per_second)

    except (FileNotFoundError, PermissionError, OSError) as e:
        # File access errors should be raised with specific messages
        if isinstance(e, FileNotFoundError):
            raise ValueError(f"Video file not found for token estimation: {file_path}") from e
        elif isinstance(e, PermissionError):
            raise ValueError(f"Permission denied accessing video file: {file_path}") from e
        else:
            raise ValueError(f"Cannot access video file {file_path}: {e}") from e
    except Exception as e:
        # Other errors (corrupted video, unsupported codec) - use fallback
        logger.warning("Video token estimation failed for %s: %s, using fallback", file_path, e)
        return FALLBACK_VIDEO_TOKENS  # Conservative fallback


def estimate_audio_tokens(file_path: str) -> int:
    """Estimate audio token count per Gemini API specification.

    Formula: 32 tokens per second

    Args:
        file_path: Path to the audio file

    Returns:
        Estimated token count

    Raises:
        ValueError: If file cannot be accessed (not found, permission denied, etc.)
    """
    try:
        tag = TinyTag.get(file_path)
        duration_seconds = tag.duration

        if duration_seconds is None:
            logger.warning("Could not extract audio duration from %s", file_path)
            duration_seconds = FALLBACK_MEDIA_DURATION_SECONDS  # Fallback

        return int(duration_seconds * 32)

    except (FileNotFoundError, PermissionError, OSError) as e:
        # File access errors should be raised with specific messages
        if isinstance(e, FileNotFoundError):
            raise ValueError(f"Audio file not found for token estimation: {file_path}") from e
        elif isinstance(e, PermissionError):
            raise ValueError(f"Permission denied accessing audio file: {file_path}") from e
        else:
            raise ValueError(f"Cannot access audio file {file_path}: {e}") from e
    except Exception as e:
        # Other errors (corrupted audio, unsupported format) - use fallback
        logger.warning("Audio token estimation failed for %s: %s, using fallback", file_path, e)
        return FALLBACK_AUDIO_TOKENS  # Conservative fallback


def estimate_tokens_for_files(model_name: str, files: list[dict], media_resolution: str = "MEDIUM") -> int:
    """Estimate token count for files using Gemini-specific formulas.

    Supports text, images, PDFs, videos, and audio files with accurate
    per-file-type estimation matching official Gemini API behavior.

    Args:
        model_name: The Gemini model to estimate tokens for
        files: List of file dicts with 'path' and 'mime_type' keys
        media_resolution: Media resolution setting for videos ("LOW", "MEDIUM", or "HIGH")

    Returns:
        Total estimated token count

    Raises:
        ValueError: If a file cannot be accessed or has unsupported mime type
    """
    if not files:
        return 0

    total_tokens = 0
    for file_info in files:
        file_path = file_info.get("path", "")
        mime_type = file_info.get("mime_type", "")

        if not file_path:
            continue

        # Images: version-specific estimation
        if mime_type.startswith("image/"):
            total_tokens += estimate_image_tokens(file_path, model_name)

        # PDFs: 258 tokens per page
        elif mime_type == "application/pdf":
            total_tokens += estimate_pdf_tokens(file_path)

        # Text/code files: use LocalTokenizer
        elif (
            mime_type.startswith("text/")
            or mime_type
            in {
                "application/json",
                "application/xml",
                "application/javascript",
                "application/yaml",
                "text/yaml",
                "application/toml",
            }
            or mime_type.endswith(("+json", "+xml"))
        ):
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                total_tokens += calculate_text_tokens(model_name, content)
            except (FileNotFoundError, PermissionError, OSError) as e:
                raise ValueError(f"Cannot access text file {file_path}: {e}") from e
            except UnicodeDecodeError as e:
                raise ValueError(f"Cannot decode text file {file_path}: {e}") from e
            except Exception as e:
                raise ValueError(f"Failed to process text file {file_path}: {e}") from e

        # Videos: resolution-dependent estimation
        elif mime_type.startswith("video/"):
            total_tokens += estimate_video_tokens(file_path, media_resolution)

        # Audio: 32 tokens per second
        elif mime_type.startswith("audio/"):
            total_tokens += estimate_audio_tokens(file_path)

        # Unknown types: raise error with clear message
        else:
            raise ValueError(
                f"Unsupported mime type '{mime_type}' for file: {file_path}. "
                f"Supported types: text/*, image/*, application/pdf, video/*, audio/*"
            )

    return total_tokens
