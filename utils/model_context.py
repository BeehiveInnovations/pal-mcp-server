"""
Model context management for dynamic token allocation.

This module provides a clean abstraction for model-specific token management,
ensuring that token limits are properly calculated based on the current model
being used, not global constants.

CONVERSATION MEMORY INTEGRATION:
This module works closely with the conversation memory system to provide
optimal token allocation for multi-turn conversations:

1. DUAL PRIORITIZATION STRATEGY SUPPORT:
   - Provides separate token budgets for conversation history vs. files
   - Enables the conversation memory system to apply newest-first prioritization
   - Ensures optimal balance between context preservation and new content

2. MODEL-SPECIFIC ALLOCATION:
   - Dynamic allocation based on model capabilities (context window size)
   - Conservative allocation for smaller models (O3: 200K context)
   - Generous allocation for larger models (Gemini: 1M+ context)
   - Adapts token distribution ratios based on model capacity

3. CROSS-TOOL CONSISTENCY:
   - Provides consistent token budgets across different tools
   - Enables seamless conversation continuation between tools
   - Supports conversation reconstruction with proper budget management
"""

import logging
import mimetypes
import os
from dataclasses import dataclass
from typing import Any, Optional

from config import DEFAULT_MODEL
from providers import ModelCapabilities, ModelProviderRegistry

logger = logging.getLogger(__name__)


@dataclass
class TokenAllocation:
    """Token allocation strategy for a model."""

    total_tokens: int
    content_tokens: int
    response_tokens: int
    file_tokens: int
    history_tokens: int

    @property
    def available_for_prompt(self) -> int:
        """Tokens available for the actual prompt after allocations."""
        return self.content_tokens - self.file_tokens - self.history_tokens


class ModelContext:
    """
    Encapsulates model-specific information and token calculations.

    This class provides a single source of truth for all model-related
    token calculations, ensuring consistency across the system.
    """

    # MIME type mapping for common file extensions
    _MIME_MAP = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
        ".mp4": "video/mp4",
        ".mpeg": "video/mpeg",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
    }

    def __init__(self, model_name: str, model_option: Optional[str] = None):
        self.model_name = model_name
        self.model_option = model_option  # Store optional model option (e.g., "for", "against", etc.)
        self._provider = None
        self._capabilities = None
        self._token_allocation = None

    @property
    def provider(self):
        """Get the model provider lazily."""
        if self._provider is None:
            self._provider = ModelProviderRegistry.get_provider_for_model(self.model_name)
            if not self._provider:
                available_models = ModelProviderRegistry.get_available_model_names()
                if available_models:
                    available_text = ", ".join(available_models)
                else:
                    available_text = (
                        "No models detected. Configure provider credentials or set DEFAULT_MODEL to a valid option."
                    )

                raise ValueError(
                    f"Model '{self.model_name}' is not available with current API keys. Available models: {available_text}."
                )
        return self._provider

    @property
    def capabilities(self) -> ModelCapabilities:
        """Get model capabilities lazily."""
        if self._capabilities is None:
            self._capabilities = self.provider.get_capabilities(self.model_name)
        return self._capabilities

    def calculate_token_allocation(self, reserved_for_response: Optional[int] = None) -> TokenAllocation:
        """
        Calculate token allocation based on model capacity and conversation requirements.

        This method implements the core token budget calculation that supports the
        dual prioritization strategy used in conversation memory and file processing:

        TOKEN ALLOCATION STRATEGY:
        1. CONTENT vs RESPONSE SPLIT:
           - Smaller models (< 300K): 60% content, 40% response (conservative)
           - Larger models (≥ 300K): 80% content, 20% response (generous)

        2. CONTENT SUB-ALLOCATION:
           - File tokens: 30-40% of content budget for newest file versions
           - History tokens: 40-50% of content budget for conversation context
           - Remaining: Available for tool-specific prompt content

        3. CONVERSATION MEMORY INTEGRATION:
           - History allocation enables conversation reconstruction in reconstruct_thread_context()
           - File allocation supports newest-first file prioritization in tools
           - Remaining budget passed to tools via _remaining_tokens parameter

        Args:
            reserved_for_response: Override response token reservation

        Returns:
            TokenAllocation with calculated budgets for dual prioritization strategy
        """
        total_tokens = self.capabilities.context_window

        # Dynamic allocation based on model capacity
        if total_tokens < 300_000:
            # Smaller context models (O3): Conservative allocation
            content_ratio = 0.6  # 60% for content
            response_ratio = 0.4  # 40% for response
            file_ratio = 0.3  # 30% of content for files
            history_ratio = 0.5  # 50% of content for history
        else:
            # Larger context models (Gemini): More generous allocation
            content_ratio = 0.8  # 80% for content
            response_ratio = 0.2  # 20% for response
            file_ratio = 0.4  # 40% of content for files
            history_ratio = 0.4  # 40% of content for history

        # Calculate allocations
        content_tokens = int(total_tokens * content_ratio)
        response_tokens = reserved_for_response or int(total_tokens * response_ratio)

        # Sub-allocations within content budget
        file_tokens = int(content_tokens * file_ratio)
        history_tokens = int(content_tokens * history_ratio)

        allocation = TokenAllocation(
            total_tokens=total_tokens,
            content_tokens=content_tokens,
            response_tokens=response_tokens,
            file_tokens=file_tokens,
            history_tokens=history_tokens,
        )

        logger.debug(f"Token allocation for {self.model_name}:")
        logger.debug(f"  Total: {allocation.total_tokens:,}")
        logger.debug(f"  Content: {allocation.content_tokens:,} ({content_ratio:.0%})")
        logger.debug(f"  Response: {allocation.response_tokens:,} ({response_ratio:.0%})")
        logger.debug(f"  Files: {allocation.file_tokens:,} ({file_ratio:.0%} of content)")
        logger.debug(f"  History: {allocation.history_tokens:,} ({history_ratio:.0%} of content)")

        return allocation

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text using provider-specific tokenizer when available.

        This method integrates with provider-specific token estimation:
        - OpenAI: Uses tiktoken with model-specific encodings (o200k_base, cl100k_base)
        - Gemini: Uses LocalTokenizer (SentencePiece) with character-based fallback
        - Other providers: Falls back to conservative character-based estimation

        Args:
            text: The text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        # Try provider-specific text tokenization
        if hasattr(self.provider, "_calculate_text_tokens"):
            try:
                return self.provider._calculate_text_tokens(self.model_name, text)
            except Exception as e:
                logger.warning(
                    "Provider tokenization failed for %s: %s, using fallback",
                    self.model_name,
                    e,
                )

        # Fallback: Conservative character-based estimation (1 token ≈ 4 chars)
        return len(text) // 4

    def estimate_file_tokens(self, file_path: str, image_detail: str = None) -> int:
        """
        Estimate token count for a file using provider-specific estimation when available.

        This method enables OpenAI and Gemini models to use their precise token estimation for
        images, PDFs, videos, and audio files. Other providers automatically fall back
        to the conservative file-size-based estimation.

        Integration with conversation memory:
        - Used by conversation_memory.py to estimate tokens for files in history
        - Ensures OpenAI/Gemini models use precise estimation for all file types
        - Maintains backward compatibility with other providers

        Args:
            file_path: Path to the file to estimate tokens for
            image_detail: Detail level for images/PDFs ("low", "high", or "auto").
                          If None, reads from OPENAI_IMAGE_DETAIL env var (defaults to "high")

        Returns:
            Estimated token count for the file
        """
        if not file_path:
            return 0

        # Try provider-specific file token estimation (e.g., OpenAI, Gemini)
        if hasattr(self.provider, "estimate_tokens_for_files"):
            try:
                mime_type = self.detect_mime_type(file_path)
                files = [{"path": file_path, "mime_type": mime_type}]
                tokens = self.provider.estimate_tokens_for_files(self.model_name, files, image_detail=image_detail)
                if tokens is not None:
                    return tokens
            except Exception as e:
                # Check if this is an OpenAI UnsupportedContentTypeError
                # These should propagate up to fail early rather than at API call time
                if e.__class__.__name__ == "UnsupportedContentTypeError":
                    raise  # Re-raise to fail early for unsupported content

                logger.warning(
                    "Provider file tokenization failed for %s: %s, using fallback",
                    self.model_name,
                    e,
                )

        # Fallback: Use file_utils for conservative estimation
        from utils.file_utils import estimate_file_tokens

        return estimate_file_tokens(file_path)

    def detect_mime_type(self, file_path: str) -> str:
        """
        Detect MIME type for a file using standard library and extension mapping.

        This method can be used by tools and other components to determine
        the MIME type needed for provider-specific token estimation.

        Args:
            file_path: Path to the file

        Returns:
            MIME type string (e.g., "image/jpeg", "application/pdf")
        """
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            ext = os.path.splitext(file_path)[1].lower()
            mime_type = self._MIME_MAP.get(ext, "text/plain")
        return mime_type

    @classmethod
    def from_arguments(cls, arguments: dict[str, Any]) -> "ModelContext":
        """Create ModelContext from tool arguments."""
        model_name = arguments.get("model") or DEFAULT_MODEL
        return cls(model_name)
