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

        Args:
            project_id: GCP project ID
            region: Vertex AI region (default: us-central1)
            **kwargs: Additional arguments passed to parent class

        Raises:
            ValueError: If project_id is empty or a placeholder, or if region is empty

        Note: Unlike other providers, Vertex AI doesn't use an API key.
        It uses Application Default Credentials (ADC) or service account credentials.
        Actual validation of project_id format and region availability is performed
        by Google Cloud APIs during authentication and client initialization.
        """
        # Initialize with empty api_key to satisfy parent class
        super().__init__("", **kwargs)

        # Minimal validation - reject empty values and obvious placeholders
        self.project_id = self._validate_not_placeholder(project_id, "VERTEX_PROJECT_ID")
        self.region = self._validate_not_empty(region, "VERTEX_REGION")

        self._credentials = None
        self._client = None
        self._merged_capabilities = None

    def _validate_not_placeholder(self, value: str, field_name: str) -> str:
        """Validate that a field is not empty or a placeholder value.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages

        Returns:
            Normalized value (stripped, lowercase)

        Raises:
            ValueError: If value is empty or a known placeholder

        Note:
            GCP project IDs are strictly lowercase. This method normalizes input
            to lowercase to prevent runtime API errors from case mismatches.
        """
        # Normalize to stripped lowercase (GCP project IDs are case-insensitive but stored lowercase)
        normalized = value.strip().lower() if value else ""

        if not normalized:
            raise ValueError(f"{field_name} is required for Vertex AI provider. " f"Please set it in your .env file.")

        # Reject common placeholder values
        invalid_placeholders = {
            "your_vertex_project_id_here",
            "your-gcp-project-id",
            "your_gcp_project_id",
        }
        if normalized in invalid_placeholders:
            raise ValueError(
                f"{field_name} '{normalized}' appears to be a placeholder. "
                f"Please replace it with your actual GCP project ID."
            )

        return normalized

    def _validate_not_empty(self, value: str, field_name: str) -> str:
        """Validate that a field is not empty.

        Args:
            value: Value to validate
            field_name: Name of the field for error messages

        Returns:
            Normalized value (stripped, lowercase)

        Raises:
            ValueError: If value is empty
        """
        # Normalize to stripped lowercase
        normalized = value.strip().lower() if value else ""

        if not normalized:
            raise ValueError(f"{field_name} cannot be empty.")

        return normalized

    @property
    def credentials(self):
        """Lazy initialization of Google credentials.

        Returns:
            Google credentials object

        Raises:
            ValueError: If credentials cannot be initialized with helpful recovery instructions
        """
        if self._credentials is None:
            try:
                self._credentials, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/generative-language"]
                )
            except google.auth.exceptions.DefaultCredentialsError as e:
                logger.error(f"Failed to initialize Google credentials (DefaultCredentialsError): {e}")
                raise ValueError(
                    f"Could not initialize Google Cloud credentials: {e}\n\n"
                    "To fix this, try one of the following:\n"
                    "1. Run: gcloud auth application-default login\n"
                    "2. Set GOOGLE_APPLICATION_CREDENTIALS to your service account key path\n"
                    "3. Ensure your GCP project is properly configured\n\n"
                    "See: https://cloud.google.com/docs/authentication/application-default-credentials"
                ) from e
            except google.auth.exceptions.RefreshError as e:
                logger.error(f"Failed to refresh Google credentials (RefreshError): {e}")
                raise ValueError(
                    f"Google Cloud credentials exist but could not be refreshed: {e}\n\n"
                    "This usually means your credentials have expired or are invalid.\n"
                    "To fix this, run: gcloud auth application-default login"
                ) from e
            except OSError as e:
                # Handle file-related errors (e.g., service account key file not found)
                logger.error(f"File system error during credential initialization: {e}")
                raise ValueError(
                    f"File system error while loading credentials: {e}\n\n"
                    "If using GOOGLE_APPLICATION_CREDENTIALS, ensure:\n"
                    "1. The file path is correct and accessible\n"
                    "2. The service account key file exists and has proper permissions\n"
                    "3. The JSON file is valid and not corrupted"
                ) from e
            except ValueError as e:
                # Handle JSON parsing errors or invalid credential formats
                logger.error(f"Invalid credential format: {e}")
                raise ValueError(
                    f"Invalid credential file format: {e}\n\n"
                    "The service account key file may be corrupted or invalid.\n"
                    "Download a new key from GCP Console and update GOOGLE_APPLICATION_CREDENTIALS."
                ) from e
            except Exception as e:
                logger.error(f"Unexpected error during Google credentials initialization: {e}")
                raise ValueError(
                    f"Unexpected error while initializing Google Cloud credentials: {e}\n\n"
                    "For debugging, check:\n"
                    "1. GCP project ID is correct\n"
                    "2. Vertex AI API is enabled in your project\n"
                    "3. Your account has necessary permissions"
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

    def _build_contents(self, parts: list[dict]) -> list[dict]:
        """Build contents structure for Vertex AI API - requires role field.

        Overrides parent class method to add required "role" field for Vertex AI.
        This is a concrete implementation of the template method pattern.

        Note: While Vertex AI supports system/model roles, the current architecture
        concatenates system prompts with user messages, which works effectively
        for most use cases while maintaining compatibility with the parent class.

        Args:
            parts: List of content parts (text, images, etc.)

        Returns:
            List of content dictionaries with required Vertex AI structure
        """
        return [{"role": "user", "parts": parts}]

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
        # Build the base response using the parent's implementation
        model_response = super()._build_response(
            response=response,
            model_name=model_name,
            thinking_mode=thinking_mode,
            capabilities=capabilities,
            usage=usage,
            finish_reason=finish_reason,
            is_blocked_by_safety=is_blocked_by_safety,
            safety_feedback=safety_feedback,
        )

        # Override Vertex AI-specific fields
        model_response.friendly_name = "Vertex AI"
        model_response.provider = ProviderType.VERTEX_AI
        model_response.metadata["project_id"] = self.project_id
        model_response.metadata["region"] = self.region

        return model_response

    def list_all_known_models(self) -> list[str]:
        """Return a list of all known model names, including both actual models and aliases.

        This includes:
        - Inherited Gemini models (gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash, etc.)
        - All inherited Gemini aliases (pro, flash, flashlite, etc.)

        Returns:
            List of all model names and their aliases
        """
        # Rely on the base class implementation for listing models, which correctly
        # uses the overridden get_all_model_capabilities() method.
        return sorted(super().list_models(respect_restrictions=False, include_aliases=True, unique=True))

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
