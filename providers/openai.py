"""OpenAI model provider implementation.

This provider serves as a unified entry point for OpenAI's APIs:
- Chat Completions API (/v1/chat/completions) for most models
- Responses API (/v1/responses) for reasoning models (o3, GPT-5-Pro)
"""

import logging
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import OPENAI_IMAGE_DETAIL
from utils import openai_token_estimator

from .openai_compatible import OpenAICompatibleProvider
from .openai_responses import OpenAIResponsesProvider
from .registries.openai import OpenAIModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ModelResponse, ProviderType

logger = logging.getLogger(__name__)

# Example models that support Responses API (for validation messages)
_RESPONSES_API_EXAMPLES = "gpt-5, gpt-5-pro, gpt-5-codex, o3, o3-pro, gpt-4.1"


class OpenAIModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Unified OpenAI provider that routes to appropriate API endpoint.

    This provider automatically selects between:
    - Chat Completions API: For standard models (GPT-4, GPT-4o, etc.)
    - Responses API: For reasoning models (o3, GPT-5-Pro, etc.)

    The selection is based on model capabilities configuration.
    """

    REGISTRY_CLASS = OpenAIModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        """Initialize OpenAI provider with API key.

        Args:
            api_key: OpenAI API key
            **kwargs: Additional parameters for OpenAICompatibleProvider
        """
        self._ensure_registry()
        # Set default OpenAI base URL, allow override for regions/custom endpoints
        kwargs.setdefault("base_url", "https://api.openai.com/v1")
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

        # Initialize Responses API provider for reasoning models
        self.responses_provider = OpenAIResponsesProvider(api_key=api_key)

    def close(self):
        """Close all clients and release resources."""
        try:
            # Close Responses API provider
            if hasattr(self, "responses_provider") and self.responses_provider is not None:
                self.responses_provider.close()
        except Exception:
            # Suppress errors during cleanup
            pass

        try:
            # Close base OpenAI client from OpenAICompatibleProvider
            # Check _client directly to avoid triggering lazy initialization
            if hasattr(self, "_client") and self._client is not None:
                self._client.close()
                self._client = None
        except Exception:
            # Suppress errors during cleanup
            pass

    def __del__(self):
        """Ensure all clients are closed when provider is garbage collected."""
        try:
            self.close()
        except Exception:
            # Suppress all errors during garbage collection
            pass

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
        images: Optional[list[str]] = None,
        files: Optional[list[str]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using the appropriate API based on model capabilities.

        Automatically routes to:
        - Responses API for models with use_openai_response_api=true
        - Responses API if non-image files are provided (PDF, docs, etc.)
        - Chat Completions API for all other models

        Args:
            prompt: User prompt
            model_name: Model name or alias
            system_prompt: Optional system prompt
            temperature: Sampling temperature (ignored for reasoning models)
            max_output_tokens: Maximum tokens to generate
            images: Optional list of image paths or URLs
            files: Optional list of document file paths (PDF, docs, etc.)
                   Note: Non-image files require Responses API
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with generated content

        Raises:
            ValueError: If files are provided but model doesn't support Responses API
        """
        # Get model capabilities to determine which API to use
        try:
            capabilities = self.get_capabilities(model_name)
        except Exception:
            # If we can't get capabilities, use Chat API as default
            capabilities = None

        # Check if this model should use Responses API
        use_responses_api = False
        if capabilities is not None:
            use_responses_api = getattr(capabilities, "use_openai_response_api", False)

        # Check if files require Responses API
        has_files = files and len(files) > 0
        if has_files:
            if not use_responses_api:
                # Model doesn't support Responses API, but files were provided
                supported_models = [
                    "gpt-5",
                    "gpt-5-pro",
                    "gpt-5-codex",
                    "o3-pro",
                ]
                raise ValueError(
                    f"Model '{model_name}' does not support file attachments. "
                    f"File attachments require the Responses API. "
                    f"Please use one of these models: {', '.join(supported_models)}. "
                    f"Or add 'use_openai_response_api: true' to the model configuration "
                    f"in conf/openai_models.json if this model supports it."
                )
            # Force Responses API for file handling
            use_responses_api = True
            logger.info(f"Using Responses API for {model_name} due to {len(files)} file attachment(s)")

        # Route to appropriate API
        if use_responses_api:
            logger.debug(f"Routing {model_name} to Responses API")

            # Unified priority for reasoning depth:
            # 1. Explicit reasoning_effort parameter (highest)
            # 2. thinking_mode parameter (mapped to reasoning_effort)
            # 3. default_reasoning_effort from capabilities
            # 4. System default (medium) - handled by responses provider
            from utils.reasoning import resolve_reasoning_effort

            default_reasoning = None
            if capabilities is not None:
                default_reasoning = getattr(capabilities, "default_reasoning_effort", None)

            effort = resolve_reasoning_effort(
                reasoning_effort=kwargs.get("reasoning_effort"),
                thinking_mode=kwargs.get("thinking_mode"),
                default_reasoning_effort=default_reasoning,
            )

            if effort:
                kwargs["reasoning_effort"] = effort
                logger.debug(f"Using resolved reasoning_effort={effort}")

            # Remove thinking_mode from kwargs as it's been mapped to reasoning_effort
            kwargs.pop("thinking_mode", None)

            try:
                return self.responses_provider.generate_content(
                    prompt=prompt,
                    model_name=self._resolve_model_name(model_name),
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    images=images,
                    files=files,
                    **kwargs,
                )
            except Exception as e:
                # Check if this is a model-not-supported error
                error_str = str(e).lower()
                is_model_error = any(
                    keyword in error_str
                    for keyword in [
                        "model",
                        "not supported",
                        "invalid model",
                        "does not exist",
                        "not found",
                    ]
                )

                if is_model_error and not has_files:
                    # Auto-fallback to Chat API if model doesn't support Responses
                    logger.warning(
                        f"Responses API failed for {model_name}: {e}. "
                        f"Falling back to Chat Completions API. "
                        f"Consider updating configuration: set 'use_openai_response_api: false' "
                        f"for this model in conf/openai_models.json"
                    )
                    return super().generate_content(
                        prompt=prompt,
                        model_name=model_name,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                        images=images,
                        **kwargs,
                    )
                else:
                    # Re-raise if files were required or it's not a model error
                    if has_files:
                        raise RuntimeError(f"Responses API required for file attachments but failed: {e}") from e
                    raise
        else:
            logger.debug(f"Routing {model_name} to Chat Completions API")
            # Use inherited Chat Completions implementation
            return super().generate_content(
                prompt=prompt,
                model_name=model_name,
                system_prompt=system_prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                images=images,
                **kwargs,
            )

    # ------------------------------------------------------------------
    # Capability surface
    # ------------------------------------------------------------------

    def _lookup_capabilities(
        self,
        canonical_name: str,
        requested_name: Optional[str] = None,
    ) -> Optional[ModelCapabilities]:
        """Look up OpenAI capabilities from built-ins or the custom registry."""

        self._ensure_registry()
        builtin = super()._lookup_capabilities(canonical_name, requested_name)
        if builtin is not None:
            return builtin

        try:
            from .registries.openrouter import OpenRouterModelRegistry

            registry = OpenRouterModelRegistry()
            config = registry.get_model_config(canonical_name)

            if config and config.provider == ProviderType.OPENAI:
                return config

        except Exception as exc:  # pragma: no cover - registry failures are non-critical
            logger.debug(f"Could not resolve custom OpenAI model '{canonical_name}': {exc}")

        return None

    def _finalise_capabilities(
        self,
        capabilities: ModelCapabilities,
        canonical_name: str,
        requested_name: str,
    ) -> ModelCapabilities:
        """Ensure registry-sourced models report the correct provider type."""

        if capabilities.provider != ProviderType.OPENAI:
            capabilities.provider = ProviderType.OPENAI
        return capabilities

    def _raise_unsupported_model(self, model_name: str) -> None:
        raise ValueError(f"Unsupported OpenAI model: {model_name}")

    # ------------------------------------------------------------------
    # Provider identity
    # ------------------------------------------------------------------

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.OPENAI

    # ------------------------------------------------------------------
    # Provider preferences
    # ------------------------------------------------------------------

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get OpenAI's preferred model for a given category from allowed models.

        Args:
            category: The tool category requiring a model
            allowed_models: Pre-filtered list of models allowed by restrictions

        Returns:
            Preferred model name or None
        """
        from tools.models import ToolModelCategory

        if not allowed_models:
            return None

        # Helper to find first available from preference list
        def find_first(preferences: list[str]) -> Optional[str]:
            """Return first available model from preference list."""
            for model in preferences:
                if model in allowed_models:
                    return model
            return None

        if category == ToolModelCategory.EXTENDED_REASONING:
            # Prefer models with extended thinking support
            # GPT-5.1 Codex first for coding tasks
            preferred = find_first(
                [
                    "gpt-5.1-codex",
                    "gpt-5.2",
                    "gpt-5-codex",
                    "gpt-5.2-pro",
                    "o3-pro",
                    "gpt-5",
                    "o3",
                ]
            )
            return preferred if preferred else allowed_models[0]

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer fast, cost-efficient models
            # GPT-5.2 models for speed, GPT-5.1-Codex after (premium pricing but cached)
            preferred = find_first(
                [
                    "gpt-5.2",
                    "gpt-5.1-codex-mini",
                    "gpt-5",
                    "gpt-5-mini",
                    "gpt-5-codex",
                    "o4-mini",
                    "o3-mini",
                ]
            )
            return preferred if preferred else allowed_models[0]

        else:  # BALANCED or default
            # Prefer balanced performance/cost models
            # Include GPT-5.2 family for latest capabilities
            preferred = find_first(
                [
                    "gpt-5.2",
                    "gpt-5.1-codex",
                    "gpt-5",
                    "gpt-5-codex",
                    "gpt-5.2-pro",
                    "gpt-5-mini",
                    "o4-mini",
                    "o3-mini",
                ]
            )
            return preferred if preferred else allowed_models[0]

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    def _calculate_text_tokens(self, model_name: str, content: str) -> int:
        """Calculate text token count using tiktoken.

        Delegates to shared openai_token_estimator utility for accurate
        token counting with OpenAI's official tokenizer.

        Args:
            model_name: The model to count tokens for
            content: Text content

        Returns:
            Token count
        """
        return openai_token_estimator.calculate_text_tokens(model_name, content)

    def _calculate_image_tokens(self, file_path: str, model_name: str, detail: str = "high") -> int:
        """Calculate image token count using OpenAI API formulas.

        Delegates to shared openai_token_estimator utility for accurate
        model-specific image token estimation.

        Args:
            file_path: Path to the image file
            model_name: The model to estimate tokens for
            detail: Detail level ("low" or "high")

        Returns:
            Estimated token count

        Raises:
            ValueError: If file cannot be accessed
        """
        return openai_token_estimator.estimate_image_tokens(file_path, model_name, detail)

    def estimate_tokens_for_files(self, model_name: str, files: list[dict], image_detail: str = None) -> int:
        """Estimate token count for files using offline calculation.

        Delegates to the shared openai_token_estimator utility for accurate,
        multimodal token counting based on official OpenAI API formulas.

        Supports:
        - Text files: tiktoken with model-specific encodings
        - Images:
          * Tile-based (Main models: GPT-4o, GPT-4.1, GPT-5, o3, o4)
          * Patch-based (Small models: mini/nano variants)
        - PDF/Documents: Via Responses API (accurate with MediaBox and aspect ratio)

        Args:
            model_name: The model to estimate tokens for
            files: List of file dicts with 'path' and 'mime_type' keys
            image_detail: Detail level for images ("low", "high", or "auto").
                          If None, uses module-level OPENAI_IMAGE_DETAIL configuration

        Returns:
            Estimated token count

        Raises:
            ValueError: If a file cannot be accessed or has an unsupported mime type
        """
        # Check if model uses Responses API (enables PDF/document support)
        try:
            capabilities = self.get_capabilities(model_name)
            use_responses_api = getattr(capabilities, "use_openai_response_api", False)
        except Exception:
            use_responses_api = False

        # Use explicit parameter or fall back to module-level config (PR 302 pattern)
        detail = image_detail if image_detail is not None else OPENAI_IMAGE_DETAIL

        return openai_token_estimator.estimate_tokens_for_files(
            model_name, files, detail, use_responses_api=use_responses_api
        )


# Load registry data at import time so dependent providers (Azure) can reuse it
OpenAIModelProvider._ensure_registry()
