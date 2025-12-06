"""Gemini model provider implementation."""

import base64
import logging
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Optional, Union

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from google import genai
from google.genai import types

# LocalTokenizer import kept for backward compatibility with tests
# Token estimation logic has been refactored to utils/gemini_token_estimator.py
try:
    from google.genai.local_tokenizer import LocalTokenizer  # noqa: F401

    _HAS_LOCAL_TOKENIZER = True
except ImportError:
    _HAS_LOCAL_TOKENIZER = False

# Optional dependencies kept for backward compatibility with tests
try:
    import imagesize  # noqa: F401

    _HAS_IMAGESIZE = True
except ImportError:
    _HAS_IMAGESIZE = False

try:
    import pypdf  # noqa: F401

    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False

try:
    from tinytag import TinyTag  # noqa: F401

    _HAS_TINYTAG = True
except ImportError:
    _HAS_TINYTAG = False

from config import GEMINI_MEDIA_RESOLUTION
from utils import gemini_token_estimator
from utils.env import get_env
from utils.gemini_validators import (
    MAX_PDF_SIZE_VERTEX_MB,
    GeminiRequestAggregate,
    GeminiValidationError,
    ProviderProfile,
    canonicalize_mime,
    validate_audio_duration,
    validate_inline_data_size,
    validate_mime_type,
    validate_pdf_pages,
    validate_video_duration,
)
from utils.image_utils import validate_image

from .base import ModelProvider
from .registries.gemini import GeminiModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ModelResponse, ProviderType

logger = logging.getLogger(__name__)


class GeminiModelProvider(RegistryBackedProviderMixin, ModelProvider):
    """First-party Gemini integration built on the official Google SDK.

    The provider advertises detailed thinking-mode budgets, handles optional
    custom endpoints, and performs image pre-processing before forwarding a
    request to the Gemini APIs.
    """

    REGISTRY_CLASS = GeminiModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    # Media resolution mapping for video token estimation
    _RESOLUTION_MAP = {
        "LOW": types.MediaResolution.MEDIA_RESOLUTION_LOW,
        "MEDIUM": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
        "HIGH": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
    }

    # Legacy model aliases without version numbers (map to 1.0)
    _LEGACY_MODEL_ALIASES = {"gemini-pro", "gemini-pro-vision"}

    # Thinking mode configurations - percentages of model's max_thinking_tokens
    # These percentages work across all models that support thinking
    THINKING_BUDGETS = {
        "minimal": 0.005,  # 0.5% of max - minimal thinking for fast responses
        "low": 0.08,  # 8% of max - light reasoning tasks
        "medium": 0.33,  # 33% of max - balanced reasoning (default)
        "high": 0.67,  # 67% of max - complex analysis
        "max": 1.0,  # 100% of max - full thinking budget
    }

    # Retry configuration for API calls
    MAX_RETRIES = 4
    RETRY_DELAYS = [1, 3, 5, 8]  # seconds

    def __init__(self, api_key: str, **kwargs):
        """Initialize Gemini provider with API key and optional base URL."""
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._client = None
        self._token_counters = {}  # Cache for token counting
        self._base_url = kwargs.get("base_url", None)  # Optional custom endpoint
        self._provider_profile = self._detect_provider_profile(
            profile_hint=kwargs.get("provider_profile"),
        )
        self._timeout_override = self._resolve_http_timeout()
        self._invalidate_capability_cache()

    # ------------------------------------------------------------------
    # Capability surface
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Client access
    # ------------------------------------------------------------------

    @property
    def client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None:
            http_options_kwargs: dict[str, object] = {}
            if self._base_url:
                http_options_kwargs["base_url"] = self._base_url
            if self._timeout_override is not None:
                http_options_kwargs["timeout"] = self._timeout_override

            if http_options_kwargs:
                http_options = types.HttpOptions(**http_options_kwargs)
                logger.debug(
                    "Initializing Gemini client with options: base_url=%s timeout=%s",
                    http_options_kwargs.get("base_url"),
                    http_options_kwargs.get("timeout"),
                )
                self._client = genai.Client(api_key=self.api_key, http_options=http_options)
            else:
                self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _resolve_http_timeout(self) -> Optional[float]:
        """Compute timeout override from shared custom timeout environment variables."""

        timeouts: list[float] = []
        for env_var in [
            "CUSTOM_CONNECT_TIMEOUT",
            "CUSTOM_READ_TIMEOUT",
            "CUSTOM_WRITE_TIMEOUT",
            "CUSTOM_POOL_TIMEOUT",
        ]:
            raw_value = get_env(env_var)
            if raw_value:
                try:
                    timeouts.append(float(raw_value))
                except (TypeError, ValueError):
                    logger.warning("Invalid %s value '%s'; ignoring.", env_var, raw_value)

        if timeouts:
            # Use the largest timeout to best approximate long-running requests
            resolved = max(timeouts)
            logger.debug("Using custom Gemini HTTP timeout: %ss", resolved)
            return resolved

        return None

    def _detect_provider_profile(
        self,
        profile_hint: Optional[Union[str, ProviderProfile]] = None,
    ) -> ProviderProfile:
        """Infer the Gemini provider profile (AI Studio vs Vertex AI).

        Priority order:
        1. Explicit profile_hint parameter
        2. GEMINI_ENDPOINT_TYPE environment variable
        3. Default: AI Studio

        Args:
            profile_hint: Optional profile override (string or ProviderProfile enum)

        Returns:
            ProviderProfile: Detected or default provider profile
        """
        # 1. Explicit profile hint
        if isinstance(profile_hint, ProviderProfile):
            return profile_hint

        if isinstance(profile_hint, str):
            try:
                return ProviderProfile(profile_hint.lower())
            except ValueError:
                logger.warning("Unknown Gemini provider_profile '%s'; defaulting to AI Studio limits.", profile_hint)

        # 2. Environment variable
        env_profile = get_env("GEMINI_ENDPOINT_TYPE")
        if env_profile:
            try:
                return ProviderProfile(env_profile.lower())
            except ValueError:
                logger.warning("Invalid GEMINI_ENDPOINT_TYPE '%s'; defaulting to AI Studio limits.", env_profile)

        # 3. Default: AI Studio
        return ProviderProfile.AI_STUDIO

    # ------------------------------------------------------------------
    # Request execution
    # ------------------------------------------------------------------

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_output_tokens: Optional[int] = None,
        thinking_mode: str = "medium",
        images: Optional[list[str]] = None,
        files: Optional[list[Union[str, dict[str, str]]]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Generate content using Gemini model.

        Args:
            prompt: The main user prompt/query to send to the model
            model_name: Canonical model name or its alias (e.g., "gemini-2.5-pro", "flash", "pro")
            system_prompt: Optional system instructions to prepend to the prompt for context/behavior
            temperature: Controls randomness in generation (0.0=deterministic, 1.0=creative), default 0.3
            max_output_tokens: Optional maximum number of tokens to generate in the response
            thinking_mode: Thinking budget level for models that support it ("minimal", "low", "medium", "high", "max"), default "medium"
            images: Optional list of image paths or data URLs to include with the prompt (for vision models)
            files: Optional list of file paths or descriptors to inline upload (PDF, audio, video)
            **kwargs: Additional keyword arguments (reserved for future use)

        Returns:
            ModelResponse: Contains the generated content, token usage stats, model metadata, and safety information
        """
        # Validate parameters and fetch capabilities
        self.validate_parameters(model_name, temperature)
        capabilities = self.get_capabilities(model_name)
        capability_map = self.get_all_model_capabilities()

        resolved_model_name = self._resolve_model_name(model_name)

        # Detect media resolution for video duration validation
        media_resolution = kwargs.get("media_resolution") or GEMINI_MEDIA_RESOLUTION
        resolution_key = (
            media_resolution.upper() if isinstance(media_resolution, str) and media_resolution else "MEDIUM"
        )

        # Determine provider profile (AI Studio vs Vertex AI)
        provider_profile = self._provider_profile
        runtime_profile_hint = kwargs.get("provider_profile")
        if runtime_profile_hint:
            provider_profile = self._detect_provider_profile(runtime_profile_hint)

        # Determine context window from capability registry (not string matching)
        context_tokens = capabilities.context_window or 0
        context_window_label = "2M" if context_tokens >= 2 * 1024 * 1024 else "1M"

        # Create request aggregate for tracking cumulative limits
        # Video limits depend on provider and model version
        # Reference: https://ai.google.dev/gemini-api/docs/video-understanding
        request_aggregate = GeminiRequestAggregate(
            provider_profile=provider_profile,
            model_name=resolved_model_name,
        )

        # Prepare content parts (text and potentially images)
        parts = []

        # Add system and user prompts as text
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        parts.append({"text": full_prompt})

        # Process files (PDF, audio, video) if provided
        file_parts: list[dict] = []
        if files:
            for file_entry in files:
                file_parts.append(
                    self._process_file(
                        file_entry,
                        aggregate=request_aggregate,
                        context_window_label=context_window_label,
                        media_resolution=resolution_key,
                        provider_profile=provider_profile,
                    )
                )
            # Validate cumulative limits after processing all files
            request_aggregate.validate_limits()
            parts.extend(file_parts)

        # Add images if provided and model supports vision
        if images and capabilities.supports_images:
            for image_path in images:
                try:
                    # Calculate size for aggregate tracking
                    # For data URLs: use Base64 length directly (already encoded)
                    # For file paths: use raw file size (will be encoded later)
                    size_bytes = 0
                    if image_path.startswith("data:"):
                        # For data URLs, the data is already Base64 encoded
                        # data URL format: data:image/png;base64,iVBORw0KG...
                        # Use the Base64 length directly for accurate total_inline_bytes tracking
                        if "," in image_path:
                            _, data = image_path.split(",", 1)
                            size_bytes = len(data)  # Direct Base64 length
                    else:
                        from pathlib import Path

                        img_path = Path(image_path).expanduser()
                        if img_path.exists():
                            size_bytes = img_path.stat().st_size

                    # Add to aggregate for validation
                    # Note: data URLs pass Base64 size directly; file paths pass raw size
                    # add_image() will calculate Base64 size for file paths
                    is_data_url = image_path.startswith("data:")
                    request_aggregate.add_image(
                        Path(image_path).name if not is_data_url else "data-url-image",
                        size_bytes=size_bytes if not is_data_url else 0,  # File path: raw size
                    )
                    # For data URLs, add Base64 size directly to total_inline_bytes
                    if is_data_url and size_bytes > 0:
                        request_aggregate.total_inline_bytes += size_bytes

                    # Process image
                    image_part = self._process_image(image_path, provider_profile=provider_profile)
                    if image_part:
                        parts.append(image_part)
                except Exception as e:
                    logger.warning(f"Failed to process image {image_path}: {e}")
                    # Continue with other images and text
                    continue

            # Validate cumulative limits after processing all images
            request_aggregate.validate_limits()
        elif images and not capabilities.supports_images:
            logger.warning(f"Model {resolved_model_name} does not support images, ignoring {len(images)} image(s)")

        # Create contents structure
        contents = [{"parts": parts}]

        # Gemini 3 Pro Preview currently rejects medium thinking budgets; bump to high.
        effective_thinking_mode = thinking_mode
        if resolved_model_name == "gemini-3-pro-preview" and thinking_mode == "medium":
            logger.debug(
                "Overriding thinking mode 'medium' with 'high' for %s due to launch limitation",
                resolved_model_name,
            )
            effective_thinking_mode = "high"

        # Prepare generation config
        generation_config = types.GenerateContentConfig(
            temperature=temperature,
            candidate_count=1,
        )

        # Add max output tokens if specified
        if max_output_tokens:
            generation_config.max_output_tokens = max_output_tokens

        # Add thinking configuration for models that support it
        if capabilities.supports_extended_thinking and effective_thinking_mode in self.THINKING_BUDGETS:
            # Get model's max thinking tokens and calculate actual budget
            model_config = capability_map.get(resolved_model_name)
            if model_config and model_config.max_thinking_tokens > 0:
                max_thinking_tokens = model_config.max_thinking_tokens
                actual_thinking_budget = int(max_thinking_tokens * self.THINKING_BUDGETS[effective_thinking_mode])
                generation_config.thinking_config = types.ThinkingConfig(thinking_budget=actual_thinking_budget)

        # Add media resolution configuration
        # Supports LOW (saves 62-75% tokens), MEDIUM (default), HIGH (quality)
        resolution_enum = self._RESOLUTION_MAP.get(resolution_key)
        if resolution_enum:
            generation_config.media_resolution = resolution_enum

        # Retry logic with progressive delays
        attempt_counter = {"value": 0}

        def _attempt() -> ModelResponse:
            attempt_counter["value"] += 1
            response = self.client.models.generate_content(
                model=resolved_model_name,
                contents=contents,
                config=generation_config,
            )

            usage = self._extract_usage(response)

            finish_reason_str = "UNKNOWN"
            is_blocked_by_safety = False
            safety_feedback_details = None

            if response.candidates:
                candidate = response.candidates[0]

                try:
                    finish_reason_enum = candidate.finish_reason
                    if finish_reason_enum:
                        try:
                            finish_reason_str = finish_reason_enum.name
                        except AttributeError:
                            finish_reason_str = str(finish_reason_enum)
                    else:
                        finish_reason_str = "STOP"
                except AttributeError:
                    finish_reason_str = "STOP"

                if not response.text:
                    try:
                        safety_ratings = candidate.safety_ratings
                        if safety_ratings:
                            for rating in safety_ratings:
                                try:
                                    if rating.blocked:
                                        is_blocked_by_safety = True
                                        category_name = "UNKNOWN"
                                        probability_name = "UNKNOWN"

                                        try:
                                            category_name = rating.category.name
                                        except (AttributeError, TypeError):
                                            pass

                                        try:
                                            probability_name = rating.probability.name
                                        except (AttributeError, TypeError):
                                            pass

                                        safety_feedback_details = (
                                            f"Category: {category_name}, Probability: {probability_name}"
                                        )
                                        break
                                except (AttributeError, TypeError):
                                    continue
                    except (AttributeError, TypeError):
                        pass

            elif response.candidates is not None and len(response.candidates) == 0:
                is_blocked_by_safety = True
                finish_reason_str = "SAFETY"
                safety_feedback_details = "Prompt blocked, reason unavailable"

                try:
                    prompt_feedback = response.prompt_feedback
                    if prompt_feedback and prompt_feedback.block_reason:
                        try:
                            block_reason_name = prompt_feedback.block_reason.name
                        except AttributeError:
                            block_reason_name = str(prompt_feedback.block_reason)
                        safety_feedback_details = f"Prompt blocked, reason: {block_reason_name}"
                except (AttributeError, TypeError):
                    pass

            return ModelResponse(
                content=response.text,
                usage=usage,
                model_name=resolved_model_name,
                friendly_name="Gemini",
                provider=ProviderType.GOOGLE,
                metadata={
                    "thinking_mode": effective_thinking_mode if capabilities.supports_extended_thinking else None,
                    "finish_reason": finish_reason_str,
                    "is_blocked_by_safety": is_blocked_by_safety,
                    "safety_feedback": safety_feedback_details,
                },
            )

        try:
            return self._run_with_retries(
                operation=_attempt,
                max_attempts=self.MAX_RETRIES,
                delays=self.RETRY_DELAYS,
                log_prefix=f"Gemini API ({resolved_model_name})",
            )
        except Exception as exc:
            attempts = max(attempt_counter["value"], 1)
            error_msg = (
                f"Gemini API error for model {resolved_model_name} after {attempts} attempt"
                f"{'s' if attempts > 1 else ''}: {exc}"
            )
            raise RuntimeError(error_msg) from exc

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.GOOGLE

    def _extract_usage(self, response) -> dict[str, int]:
        """Extract token usage from Gemini response."""
        usage = {}

        # Try to extract usage metadata from response
        # Note: The actual structure depends on the SDK version and response format
        try:
            metadata = response.usage_metadata
            if metadata:
                # Extract token counts with explicit None checks
                input_tokens = None
                output_tokens = None

                try:
                    value = metadata.prompt_token_count
                    if value is not None:
                        input_tokens = value
                        usage["input_tokens"] = value
                except (AttributeError, TypeError):
                    pass

                try:
                    value = metadata.candidates_token_count
                    if value is not None:
                        output_tokens = value
                        usage["output_tokens"] = value
                except (AttributeError, TypeError):
                    pass

                # Calculate total only if both values are available and valid
                if input_tokens is not None and output_tokens is not None:
                    usage["total_tokens"] = input_tokens + output_tokens
        except (AttributeError, TypeError):
            # response doesn't have usage_metadata
            pass

        return usage

    def _is_error_retryable(self, error: Exception) -> bool:
        """Determine if an error should be retried based on structured error codes.

        Uses Gemini API error structure instead of text pattern matching for reliability.

        Args:
            error: Exception from Gemini API call

        Returns:
            True if error should be retried, False otherwise
        """
        error_str = str(error).lower()

        # Check for 429 errors first - these need special handling
        if "429" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
            # For Gemini, check for specific non-retryable error indicators
            # These typically indicate permanent failures or quota/size limits
            non_retryable_indicators = [
                "quota exceeded",
                "resource exhausted",
                "context length",
                "token limit",
                "request too large",
                "invalid request",
                "quota_exceeded",
                "resource_exhausted",
            ]

            # Also check if this is a structured error from Gemini SDK
            try:
                # Try to access error details if available
                error_details = None
                try:
                    error_details = error.details
                except AttributeError:
                    try:
                        error_details = error.reason
                    except AttributeError:
                        pass

                if error_details:
                    error_details_str = str(error_details).lower()
                    # Check for non-retryable error codes/reasons
                    if any(indicator in error_details_str for indicator in non_retryable_indicators):
                        logger.debug(f"Non-retryable Gemini error: {error_details}")
                        return False
            except Exception:
                pass

            # Check main error string for non-retryable patterns
            if any(indicator in error_str for indicator in non_retryable_indicators):
                logger.debug(f"Non-retryable Gemini error based on message: {error_str[:200]}...")
                return False

            # If it's a 429/quota error but doesn't match non-retryable patterns, it might be retryable rate limiting
            logger.debug(f"Retryable Gemini rate limiting error: {error_str[:100]}...")
            return True

        # For non-429 errors, check if they're retryable
        retryable_indicators = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "unavailable",
            "retry",
            "internal error",
            "408",  # Request timeout
            "500",  # Internal server error
            "502",  # Bad gateway
            "503",  # Service unavailable
            "504",  # Gateway timeout
            "ssl",  # SSL errors
            "handshake",  # Handshake failures
        ]

        return any(indicator in error_str for indicator in retryable_indicators)

    def _process_image(self, image_path: str, provider_profile: Optional[ProviderProfile] = None) -> Optional[dict]:
        """Process an image for Gemini API.

        Args:
            image_path: Path to image file or data URL
            provider_profile: Provider profile for format validation (AI Studio supports HEIC/HEIF, Vertex does not)

        Returns:
            Image part dict for Gemini API, or None on error
        """
        try:
            # Determine if HEIC/HEIF should be allowed (AI Studio only)
            allow_heic_heif = provider_profile == ProviderProfile.AI_STUDIO if provider_profile else False

            # Use base class validation with provider-specific format support
            image_bytes, mime_type = validate_image(image_path, allow_heic_heif=allow_heic_heif)

            # For data URLs, extract the base64 data directly
            if image_path.startswith("data:"):
                # Extract base64 data from data URL
                _, data = image_path.split(",", 1)
                return {"inline_data": {"mime_type": mime_type, "data": data}}
            else:
                # For file paths, encode the bytes
                image_data = base64.b64encode(image_bytes).decode()
                return {"inline_data": {"mime_type": mime_type, "data": image_data}}

        except ValueError as e:
            logger.warning(str(e))
            return None
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            return None

    def _process_file(
        self,
        file_entry: Union[str, dict[str, str]],
        *,
        aggregate: GeminiRequestAggregate,
        context_window_label: str,
        media_resolution: str,
        provider_profile: ProviderProfile,
    ) -> dict:
        """Validate and convert a local file to Gemini inline_data.

        Args:
            file_entry: File path string or dict with 'path' and optional 'mime_type'
            aggregate: Request aggregate for tracking cumulative limits
            context_window_label: Context window size ("1M" or "2M") for video validation
            media_resolution: Media resolution key ("LOW", "MEDIUM", "HIGH")
            provider_profile: Provider profile (AI_STUDIO or VERTEX_AI)

        Returns:
            Dict with inline_data format: {"inline_data": {"mime_type": "...", "data": "base64..."}}

        Raises:
            GeminiValidationError: If validation fails
            FileNotFoundError: If file doesn't exist
        """
        # Extract file path and optional MIME hint
        if isinstance(file_entry, dict):
            file_path = file_entry.get("path")
            mime_hint = file_entry.get("mime_type")
        else:
            file_path = file_entry
            mime_hint = None

        if not file_path:
            raise GeminiValidationError("File descriptor must include a 'path'.")

        # Resolve and validate path
        path = Path(file_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Gemini file '{path}' does not exist.")
        if not path.is_file():
            raise GeminiValidationError(f"Gemini file '{path}' is not a regular file.")

        # Detect and canonicalize MIME type
        mime_type = mime_hint or mimetypes.guess_type(str(path))[0] or ""
        canonical_mime = canonicalize_mime(mime_type)
        validate_mime_type(canonical_mime, file_name=path.name, provider_profile=provider_profile)

        # Validate inline_data size (18MB soft warning, 20MB hard limit)
        size_bytes = path.stat().st_size
        validate_inline_data_size(size_bytes, file_name=path.name)

        # Vertex AI specific: 50MB PDF limit
        if canonical_mime == "application/pdf" and provider_profile == ProviderProfile.VERTEX_AI:
            size_mb = size_bytes / (1024**2)
            if size_mb > MAX_PDF_SIZE_VERTEX_MB:
                raise GeminiValidationError(
                    f"PDF '{path.name}' is {size_mb:.2f}MB which exceeds the {MAX_PDF_SIZE_VERTEX_MB}MB Vertex AI limit."
                )

        # Ensure resolution is valid
        effective_resolution = media_resolution if media_resolution in {"LOW", "MEDIUM", "HIGH"} else "MEDIUM"

        # Handle images via existing _process_image
        if canonical_mime.startswith("image/"):
            aggregate.add_image(path.name, size_bytes=size_bytes)
            image_part = self._process_image(str(path))
            if image_part is None:
                raise GeminiValidationError(f"Failed to process image '{path}'.")
            return image_part

        # Validate PDF
        if canonical_mime == "application/pdf":
            if not _HAS_PYPDF:
                raise RuntimeError("PDF support requires the 'pypdf' package to validate page counts.")
            try:
                import pypdf

                reader = pypdf.PdfReader(str(path))
                page_count = len(reader.pages)
                validate_pdf_pages(page_count, file_name=path.name)
                aggregate.add_pdf(path.name, page_count, size_bytes=size_bytes)
            except Exception as e:
                raise GeminiValidationError(f"Failed to validate PDF '{path.name}': {e}") from e

        # Handle plain text documents (Vertex AI and AI Studio)
        elif canonical_mime == "text/plain":
            # Track size for inline_data limit (exact Base64 size calculation)
            if size_bytes > 0:
                from utils.gemini_validators import calculate_base64_size

                aggregate.total_inline_bytes += calculate_base64_size(size_bytes)
            aggregate.files_processed.append(path.name)
            logger.debug(f"Processing text file {path.name} as document ({size_bytes} bytes)")

        # Validate audio
        elif canonical_mime.startswith("audio/"):
            if not _HAS_TINYTAG:
                raise RuntimeError("Audio validation requires the 'tinytag' package.")
            try:
                from tinytag import TinyTag

                tag = TinyTag.get(str(path))
                duration = getattr(tag, "duration", None)
                if duration is None or duration <= 0:
                    raise GeminiValidationError(f"Audio file '{path.name}' has invalid duration metadata.")
                validate_audio_duration(duration, file_name=path.name)
                aggregate.add_audio(path.name, duration, size_bytes=size_bytes)
            except GeminiValidationError:
                raise
            except Exception as e:
                raise GeminiValidationError(f"Failed to validate audio '{path.name}': {e}") from e

        # Validate video
        elif canonical_mime.startswith("video/"):
            if not _HAS_TINYTAG:
                raise RuntimeError("Video validation requires the 'tinytag' package.")
            try:
                from tinytag import TinyTag

                tag = TinyTag.get(str(path))
                duration = getattr(tag, "duration", None)
                if duration is None or duration <= 0:
                    raise GeminiValidationError(f"Video file '{path.name}' has invalid duration metadata.")
                validate_video_duration(
                    duration,
                    file_name=path.name,
                    media_resolution=effective_resolution,
                    context_window=context_window_label,
                )
                aggregate.add_video(path.name, size_bytes=size_bytes)
            except GeminiValidationError:
                raise
            except Exception as e:
                raise GeminiValidationError(f"Failed to validate video '{path.name}': {e}") from e

        else:
            raise GeminiValidationError(f"Unsupported file MIME type '{canonical_mime}' for Gemini inline upload.")

        # Read and Base64 encode file
        with path.open("rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("utf-8")

        logger.info(f"Processed file {path.name} ({canonical_mime}) via inline_data")
        return {"inline_data": {"mime_type": canonical_mime, "data": encoded}}

    def _calculate_text_tokens(self, model_name: str, content: str) -> int:
        """Delegates to shared gemini_token_estimator utility."""
        return gemini_token_estimator.calculate_text_tokens(model_name, content)

    def _calculate_image_tokens(self, file_path: str, model_name: str = "gemini-2.5-flash") -> int:
        """Delegates to shared gemini_token_estimator utility."""
        return gemini_token_estimator.estimate_image_tokens(file_path, model_name)

    def _calculate_pdf_tokens(self, file_path: str) -> int:
        """Delegates to shared gemini_token_estimator utility."""
        return gemini_token_estimator.estimate_pdf_tokens(file_path)

    def _calculate_video_tokens(self, file_path: str) -> int:
        """Delegates to shared gemini_token_estimator utility."""
        return gemini_token_estimator.estimate_video_tokens(file_path, GEMINI_MEDIA_RESOLUTION)

    def _calculate_audio_tokens(self, file_path: str) -> int:
        """Delegates to shared gemini_token_estimator utility."""
        return gemini_token_estimator.estimate_audio_tokens(file_path)

    def estimate_tokens_for_files(self, model_name: str, files: list[dict]) -> int:
        """Estimate token count for files using offline calculation.

        Delegates to the shared gemini_token_estimator utility for accurate,
        multimodal token counting based on official Gemini API formulas.

        Args:
            model_name: The model to estimate tokens for
            files: List of file dicts with 'path' and 'mime_type' keys

        Returns:
            Estimated token count

        Raises:
            ValueError: If a file cannot be accessed or has an unsupported mime type
        """
        return gemini_token_estimator.estimate_tokens_for_files(model_name, files, GEMINI_MEDIA_RESOLUTION)

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get Gemini's preferred model for a given category from allowed models.

        Args:
            category: The tool category requiring a model
            allowed_models: Pre-filtered list of models allowed by restrictions

        Returns:
            Preferred model name or None
        """
        from tools.models import ToolModelCategory

        if not allowed_models:
            return None

        capability_map = self.get_all_model_capabilities()

        # Helper to find best model from candidates
        def find_best(candidates: list[str]) -> Optional[str]:
            """Return best model from candidates (sorted for consistency)."""
            return sorted(candidates, reverse=True)[0] if candidates else None

        if category == ToolModelCategory.EXTENDED_REASONING:
            # For extended reasoning, prefer models with thinking support
            # First try Pro models that support thinking
            pro_thinking = [
                m
                for m in allowed_models
                if "pro" in m and m in capability_map and capability_map[m].supports_extended_thinking
            ]
            if pro_thinking:
                return find_best(pro_thinking)

            # Then any model that supports thinking
            any_thinking = [
                m for m in allowed_models if m in capability_map and capability_map[m].supports_extended_thinking
            ]
            if any_thinking:
                return find_best(any_thinking)

            # Finally, just prefer Pro models even without thinking
            pro_models = [m for m in allowed_models if "pro" in m]
            if pro_models:
                return find_best(pro_models)

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer Flash models for speed
            flash_models = [m for m in allowed_models if "flash" in m]
            if flash_models:
                return find_best(flash_models)

        # Default for BALANCED or as fallback
        # Prefer Flash for balanced use, then Pro, then anything
        flash_models = [m for m in allowed_models if "flash" in m]
        if flash_models:
            return find_best(flash_models)

        pro_models = [m for m in allowed_models if "pro" in m]
        if pro_models:
            return find_best(pro_models)

        # Ultimate fallback to best available model
        return find_best(allowed_models)


# Load registry data at import time for registry consumers
GeminiModelProvider._ensure_registry()
