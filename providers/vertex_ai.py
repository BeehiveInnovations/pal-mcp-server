"""Google Vertex AI model provider implementation."""

import dataclasses
import logging

import google.auth
import google.auth.exceptions
import google.genai as genai
import google.genai.types as genai_types

from .gemini import GeminiModelProvider
from .shared import ModelCapabilities, ModelResponse, ProviderType, TemperatureConstraint

logger = logging.getLogger(__name__)


class VertexAIProvider(GeminiModelProvider):
    """Google Vertex AI model provider implementation."""

    # Inherit thinking budgets from parent
    THINKING_BUDGETS = GeminiModelProvider.THINKING_BUDGETS

    # Vertex AI specific model configurations
    # Note: Base Gemini models are inherited via get_capabilities() method override
    # Only truly Vertex AI specific models are defined here
    VERTEX_SPECIFIC_MODELS = {
        "gemini-2.5-flash-lite-preview-06-17": ModelCapabilities(
            provider=ProviderType.VERTEX_AI,
            model_name="gemini-2.5-flash-lite-preview-06-17",
            friendly_name="Vertex AI",
            context_window=1_048_576,  # 1M tokens
            max_output_tokens=65_536,
            supports_extended_thinking=True,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # Vision capability
            max_image_size_mb=20.0,  # Conservative 20MB limit for reliability
            supports_temperature=True,
            temperature_constraint=TemperatureConstraint.create("range"),
            max_thinking_tokens=24576,  # Flash 2.5 thinking budget limit
            description="Gemini 2.5 Flash Lite (Preview) - Vertex AI deployment",
        ),
        "gemini-2.5-pro-preview-06-05": ModelCapabilities(
            provider=ProviderType.VERTEX_AI,
            model_name="gemini-2.5-pro-preview-06-05",
            friendly_name="Vertex AI",
            context_window=1_048_576,  # 1M tokens
            max_output_tokens=65_536,
            supports_extended_thinking=True,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # Vision capability
            max_image_size_mb=32.0,  # Higher limit for Pro model
            supports_temperature=True,
            temperature_constraint=TemperatureConstraint.create("range"),
            max_thinking_tokens=32768,  # Pro 2.5 thinking budget limit
            description="Gemini 2.5 Pro (Preview) - Vertex AI deployment",
        ),
    }

    # Vertex AI specific aliases that extend the parent Gemini aliases
    VERTEX_ALIASES = {
        "gemini-3-pro-preview": ["vertex-3-pro", "vertex-3.0-pro", "vertex-gemini3"],
        "gemini-2.5-pro": ["vertex-pro", "vertex-2.5-pro"],  # vertex-pro = stable pro model
        "gemini-2.5-flash": ["vertex-flash", "vertex-2.5-flash"],
        "gemini-2.5-flash-lite-preview-06-17": ["vertex-lite", "vertex-2.5-flash-lite", "gemini-2.5-flash-lite"],
        "gemini-2.0-flash": ["vertex-2.0-flash"],
    }

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

    def get_all_model_capabilities(self) -> dict[str, ModelCapabilities]:
        """Get all model capabilities for Vertex AI, merging parent Gemini models with Vertex-specific ones.

        Returns:
            Dictionary mapping model names to their capabilities, including both inherited
            Gemini models (with Vertex-specific aliases added) and Vertex-specific models.
        """
        if self._merged_capabilities is not None:
            return self._merged_capabilities

        # Get parent Gemini capabilities from registry
        parent_capabilities = super().get_all_model_capabilities()

        # Start with a copy of parent capabilities
        merged = {}
        for model_name, capabilities in parent_capabilities.items():
            # Check if this model has Vertex-specific aliases to add
            if model_name in self.VERTEX_ALIASES:
                # Get existing aliases from the capabilities
                existing_aliases = list(capabilities.aliases) if capabilities.aliases else []

                # Merge with Vertex-specific aliases (deduplicate)
                combined_aliases = list(dict.fromkeys(existing_aliases + self.VERTEX_ALIASES[model_name]))

                # Create a new capabilities object with merged aliases
                merged[model_name] = dataclasses.replace(capabilities, aliases=combined_aliases)
            else:
                # No Vertex-specific aliases, use as-is
                merged[model_name] = capabilities

        # Add Vertex-specific models (also apply alias merging)
        for model_name, capabilities in self.VERTEX_SPECIFIC_MODELS.items():
            # Check if this Vertex-specific model has aliases to add
            if model_name in self.VERTEX_ALIASES:
                # Get existing aliases from the capabilities (if any)
                existing_aliases = list(capabilities.aliases) if capabilities.aliases else []

                # Merge with Vertex-specific aliases (deduplicate)
                combined_aliases = list(dict.fromkeys(existing_aliases + self.VERTEX_ALIASES[model_name]))

                # Create a new capabilities object with merged aliases
                merged[model_name] = dataclasses.replace(capabilities, aliases=combined_aliases)
            else:
                # No Vertex-specific aliases, use as-is
                merged[model_name] = capabilities

        # Cache the merged capabilities
        self._merged_capabilities = merged
        return merged

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
                "finish_reason": (
                    getattr(response.candidates[0], "finish_reason", "STOP") if response.candidates else "STOP"
                ),
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
            # Resolve the model name first in case it's an alias
            resolved_name = self._resolve_model_name(model_name)

            # Get capabilities for the resolved model
            capabilities = self.get_capabilities(resolved_name)

            return capabilities.supports_extended_thinking
        except ValueError:
            # If model is not found or not supported, return False
            return False

    def count_tokens(self, text: str, model_name: str) -> int:
        """Estimate token usage for text using character-based heuristic.

        Uses pure chars // 4 formula to match Gemini's token counting behavior.

        Args:
            text: Text to count tokens for
            model_name: Model name (not used for estimation)

        Returns:
            Estimated token count (chars // 4)
        """
        if not text:
            return 0

        return len(text) // 4
