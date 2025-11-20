"""Google Vertex AI model provider implementation."""

from __future__ import annotations

import dataclasses
import logging

import google.auth
import google.auth.exceptions
import google.genai as genai
import google.genai.types as genai_types

from .gemini import GeminiModelProvider
from .shared import ModelCapabilities, ModelResponse, ProviderType

logger = logging.getLogger(__name__)


class VertexAIProvider(GeminiModelProvider):
    """Google Vertex AI model provider implementation."""

    # Inherit thinking budgets from parent
    THINKING_BUDGETS = GeminiModelProvider.THINKING_BUDGETS

    # Note: All Gemini models are inherited from parent GeminiModelProvider
    # There are no Vertex AI exclusive Gemini models - all Gemini models are available
    # in both Google AI Studio and Vertex AI. The purpose of this provider is to:
    # 1. Route requests to Vertex AI (GCP billing) instead of Gemini API (API key billing)
    # 2. Use standard Gemini model names (gemini-2.5-pro, etc.) - credentials determine billing
    # 3. Enable enterprise features (data residency, compliance, MLOps)
    # 4. Access non-Gemini models (MedLM, Computer Use, Model Garden) - not implemented here

    def __init__(self, project_id: str, region: str = "us-central1", **kwargs):
        """Initialize Vertex AI provider with project ID and region.

        Note: Unlike other providers, Vertex AI doesn't use an API key.
        It uses Application Default Credentials (ADC) or service account credentials.
        """
        # Initialize with empty api_key to satisfy parent class
        super().__init__("", **kwargs)
        self.project_id = project_id
        self.region = region
        self._credentials = None
        self._client = None
        self._merged_capabilities = None

    @property
    def credentials(self):
        """Lazy initialization of Google credentials."""
        if self._credentials is None:
            try:
                self._credentials, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/generative-language"]
                )
            except google.auth.exceptions.DefaultCredentialsError as e:
                logger.error(f"Failed to initialize Google credentials (DefaultCredentialsError): {e}")
                raise ValueError(
                    f"Could not initialize Google Cloud credentials: {e}. "
                    "Please run 'gcloud auth application-default login' or set "
                    "GOOGLE_APPLICATION_CREDENTIALS environment variable."
                ) from e
            except Exception as e:
                logger.error(f"An unexpected error occurred during Google credentials initialization: {e}")
                raise ValueError(
                    f"An unexpected error occurred while initializing Google Cloud credentials: {e}"
                ) from e
        return self._credentials

    @property
    def client(self):
        """Lazy initialization of Google GenAI client for Vertex AI."""
        if self._client is None:
            # Create Vertex AI client using credentials instead of API key
            self._client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.region,
                credentials=self.credentials,
            )
        return self._client

    def _invalidate_capability_cache(self):
        """Invalidate both parent and local capability caches.

        This ensures that when the parent provider refreshes capabilities,
        the Vertex AI provider's merged cache is also cleared to prevent
        serving stale model information.
        """
        super()._invalidate_capability_cache()
        self._merged_capabilities = None

    def get_all_model_capabilities(self) -> dict[str, ModelCapabilities]:
        """Get all model capabilities for Vertex AI.

        Returns:
            Dictionary mapping model names to their capabilities. All models are inherited
            from parent GeminiModelProvider with Vertex AI provider type and friendly name.
        """
        if self._merged_capabilities is not None:
            return self._merged_capabilities

        # Get parent Gemini capabilities and override provider metadata
        parent_capabilities = super().get_all_model_capabilities()

        # Override provider type and friendly name for all models
        self._merged_capabilities = {
            model_name: dataclasses.replace(capabilities, provider=ProviderType.VERTEX_AI, friendly_name="Vertex AI")
            for model_name, capabilities in parent_capabilities.items()
        }

        return self._merged_capabilities

    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific Vertex AI model.

        This method resolves model aliases and returns capabilities, overriding
        the provider type to Vertex AI for all models.

        Args:
            model_name: Model name or alias

        Returns:
            ModelCapabilities object with Vertex AI provider type

        Raises:
            ValueError: If the model is not supported
        """
        # Get the base capabilities using parent's logic (which handles resolution)
        capabilities = super().get_capabilities(model_name)

        # Override provider type and friendly name for all models
        return dataclasses.replace(
            capabilities,
            provider=ProviderType.VERTEX_AI,
            friendly_name="Vertex AI",
        )

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.VERTEX_AI

    def _build_contents(self, parts: list[dict], role: str = "user") -> list[dict]:
        """Build contents structure for Vertex AI API - requires role field.

        Overrides parent class method to add required "role" field for Vertex AI.
        This is a concrete implementation of the template method pattern.

        Note: While Vertex AI supports system/model roles, the current architecture
        concatenates system prompts with user messages, which works effectively
        for most use cases while maintaining compatibility with the parent class.

        Args:
            parts: List of content parts (text, images, etc.)
            role: The role for the message ("user", "system", or "model")

        Returns:
            List of content dictionaries with required Vertex AI structure
        """
        return [{"role": role, "parts": parts}]

    def _build_response(
        self,
        response: genai_types.GenerateContentResponse,
        model_name: str,
        thinking_mode: str,
        capabilities: ModelCapabilities,
        usage: dict[str, int],
        finish_reason: str = "STOP",
        is_blocked_by_safety: bool = False,
        safety_feedback: str | None = None,
    ) -> ModelResponse:
        """Build response object for Vertex AI provider.

        Overrides parent class method to customize response metadata for Vertex AI.
        Includes Vertex AI specific information like project_id and region.

        Args:
            response: Vertex AI API response object
            model_name: Name of the model used
            thinking_mode: Thinking mode configuration
            capabilities: Model capabilities object
            usage: Token usage information dictionary
            finish_reason: Reason for response completion (STOP, SAFETY, etc.)
            is_blocked_by_safety: Whether response was blocked by safety filters
            safety_feedback: Details about safety blocking if applicable

        Returns:
            ModelResponse object with Vertex AI specific metadata
        """
        return ModelResponse(
            content=response.text,
            usage=usage,
            model_name=model_name,
            friendly_name="Vertex AI",
            provider=ProviderType.VERTEX_AI,
            metadata={
                "project_id": self.project_id,
                "region": self.region,
                "thinking_mode": (thinking_mode if capabilities.supports_extended_thinking else None),
                "finish_reason": finish_reason,
                "is_blocked_by_safety": is_blocked_by_safety,
                "safety_feedback": safety_feedback,
            },
        )

    def list_all_known_models(self) -> list[str]:
        """Return a list of all known model names, including both actual models and aliases.

        This includes:
        - Vertex AI specific models (gemini-2.5-flash-lite-preview-06-17, etc.)
        - Inherited Gemini models (gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash, etc.)
        - All aliases (vertex-pro, vertex-flash, vertex-lite, pro, flash, etc.)

        Returns:
            List of all model names and their aliases
        """
        # Get all model capabilities
        all_capabilities = self.get_all_model_capabilities()

        # Start with all actual model names
        all_models = set(all_capabilities.keys())

        # Add all aliases from capabilities
        for _model_name, capabilities in all_capabilities.items():
            if capabilities.aliases:
                all_models.update(capabilities.aliases)

        return sorted(all_models)

    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if a model supports extended thinking mode.

        Args:
            model_name: Model name or alias to check

        Returns:
            True if the model supports extended thinking, False otherwise
        """
        try:
            # get_capabilities already handles alias resolution
            capabilities = self.get_capabilities(model_name)
            return capabilities.supports_extended_thinking
        except ValueError:
            # If model is not found or not supported, return False
            return False

    # Note: count_tokens() inherited from base ModelProvider
    # Uses standard heuristic: max(1, len(text) // 4)
