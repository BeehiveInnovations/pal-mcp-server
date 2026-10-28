"""DIAL (Data & AI Layer) model provider implementation."""

import logging
import threading
from typing import ClassVar, Optional

from utils.env import get_env

from .openai_compatible import OpenAICompatibleProvider
from .registries.dial import DialModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ModelResponse, ProviderType

logger = logging.getLogger(__name__)


class DIALModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Client for the DIAL (Data & AI Layer) aggregation service.

    DIAL exposes several third-party models behind a single OpenAI-compatible
    endpoint.  This provider wraps the service, publishes capability metadata
    for the known deployments, and centralises retry/backoff settings tailored
    to DIAL's latency characteristics.
    """

    FRIENDLY_NAME = "DIAL"

    REGISTRY_CLASS = DialModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    # Retry configuration for API calls
    MAX_RETRIES = 4
    RETRY_DELAYS = [1, 3, 5, 8]  # seconds

    def __init__(self, api_key: str, **kwargs):
        """Initialize DIAL provider with API key and host.

        Args:
            api_key: DIAL API key for authentication
            **kwargs: Additional configuration options
        """
        self._ensure_registry()
        # Get DIAL API host from environment or kwargs
        dial_host = kwargs.get("base_url") or get_env("DIAL_API_HOST") or "https://core.dialx.ai"

        # DIAL uses /openai endpoint for OpenAI-compatible API
        if not dial_host.endswith("/openai"):
            dial_host = f"{dial_host.rstrip('/')}/openai"

        kwargs["base_url"] = dial_host

        # Get API version from environment or use default
        self.api_version = get_env("DIAL_API_VERSION", "2024-12-01-preview") or "2024-12-01-preview"

        # Add DIAL-specific headers
        # DIAL uses Api-Key header instead of Authorization: Bearer
        # Reference: https://dialx.ai/dial_api#section/Authorization
        self.DEFAULT_HEADERS = {
            "Api-Key": api_key,
        }

        # Store the actual API key for use in Api-Key header
        self._dial_api_key = api_key

        # Pass a placeholder API key to OpenAI client - we'll override the auth header in httpx
        # The actual authentication happens via the Api-Key header in the httpx client
        super().__init__("placeholder-not-used", **kwargs)

        # Cache for deployment-specific clients to avoid recreating them on each request
        self._deployment_clients = {}
        # Lock to ensure thread-safe client creation
        self._client_lock = threading.Lock()

        # Create a SINGLE shared httpx client for the provider instance
        import httpx

        # Create custom event hooks to remove Authorization header
        def remove_auth_header(request):
            """Remove Authorization header that OpenAI client adds."""
            # httpx headers are case-insensitive, so we need to check all variations
            headers_to_remove = []
            for header_name in request.headers:
                if header_name.lower() == "authorization":
                    headers_to_remove.append(header_name)

            for header_name in headers_to_remove:
                del request.headers[header_name]

        self._http_client = httpx.Client(
            timeout=self.timeout_config,
            verify=True,
            follow_redirects=True,
            headers=self.DEFAULT_HEADERS.copy(),  # Include DIAL headers including Api-Key
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0,
            ),
            event_hooks={"request": [remove_auth_header]},
        )

        logger.info(f"Initialized DIAL provider with host: {dial_host} and api-version: {self.api_version}")

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.DIAL

    def _get_deployment_client(self, deployment: str):
        """Get or create a cached client for a specific deployment.

        This avoids recreating OpenAI clients on every request, improving performance.
        Reuses the shared HTTP client for connection pooling.

        Args:
            deployment: The deployment/model name

        Returns:
            OpenAI client configured for the specific deployment
        """
        # Check if client already exists without locking for performance
        if deployment in self._deployment_clients:
            return self._deployment_clients[deployment]

        # Use lock to ensure thread-safe client creation
        with self._client_lock:
            # Double-check pattern: check again inside the lock
            if deployment not in self._deployment_clients:
                from openai import OpenAI

                # Build deployment-specific URL
                base_url = str(self.client.base_url)
                if base_url.endswith("/"):
                    base_url = base_url[:-1]

                # Remove /openai suffix if present to reconstruct properly
                if base_url.endswith("/openai"):
                    base_url = base_url[:-7]

                deployment_url = f"{base_url}/openai/deployments/{deployment}"

                # Create and cache the client, REUSING the shared http_client
                # Use placeholder API key - Authorization header will be removed by http_client event hook
                self._deployment_clients[deployment] = OpenAI(
                    api_key="placeholder-not-used",
                    base_url=deployment_url,
                    http_client=self._http_client,  # Pass the shared client with Api-Key header
                    default_query={"api-version": self.api_version},  # Add api-version as query param
                )

        return self._deployment_clients[deployment]

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
        images: Optional[list[str]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using DIAL's deployment-specific endpoint.

        DIAL uses Azure OpenAI-style deployment endpoints:
        /openai/deployments/{deployment}/chat/completions

        Args:
            prompt: The main user prompt/query to send to the model
            model_name: Model name or alias (e.g., "o3", "sonnet-4.1", "gemini-2.5-pro")
            system_prompt: Optional system instructions to prepend to the prompt for context/behavior
            temperature: Sampling temperature for randomness (0.0=deterministic, 1.0=creative), default 0.3
                        Note: O3/O4 models don't support temperature and will ignore this parameter
            max_output_tokens: Optional maximum number of tokens to generate in the response
            images: Optional list of image paths or data URLs to include with the prompt (for vision-capable models)
            **kwargs: Additional OpenAI-compatible parameters (top_p, frequency_penalty, presence_penalty, seed, stop)

        Returns:
            ModelResponse: Contains the generated content, token usage stats, model metadata, and finish reason
        """
        # Validate model name against allow-list
        if not self.validate_model_name(model_name):
            raise ValueError(f"Model '{model_name}' not in allowed models list. Allowed models: {self.allowed_models}")

        # Validate parameters and fetch capabilities
        self.validate_parameters(model_name, temperature)
        capabilities = self.get_capabilities(model_name)

        # Prepare messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        # Build user message content
        user_message_content = []
        if prompt:
            user_message_content.append({"type": "text", "text": prompt})

        if images and capabilities.supports_images:
            for img_path in images:
                processed_image = self._process_image(img_path)
                if processed_image:
                    user_message_content.append(processed_image)
        elif images:
            logger.warning(f"Model {model_name} does not support images, ignoring {len(images)} image(s)")

        # Add user message. If only text, content will be a string, otherwise a list.
        if len(user_message_content) == 1 and user_message_content[0]["type"] == "text":
            messages.append({"role": "user", "content": prompt})
        else:
            messages.append({"role": "user", "content": user_message_content})

        # Guardrail: redact credentials/PII at the send boundary (fail-open, per-call restore map)
        from providers.router import outbound

        messages, _mask_ctx = outbound.prepare(messages, model_name)
        from providers.router import guardrail

        # Resolve model name
        resolved_model = self._resolve_model_name(model_name)

        # Build completion parameters
        completion_params = {
            "model": resolved_model,
            "messages": messages,
            "stream": False,
        }

        # Determine temperature support from capabilities
        supports_temperature = capabilities.supports_temperature

        # Add temperature parameter if supported
        if supports_temperature:
            completion_params["temperature"] = temperature

        # Add max tokens if specified and model supports it
        if max_output_tokens and supports_temperature:
            completion_params["max_tokens"] = max_output_tokens

        # Add additional parameters
        for key, value in kwargs.items():
            if key in ["top_p", "frequency_penalty", "presence_penalty", "seed", "stop", "stream"]:
                if not supports_temperature and key in ["top_p", "frequency_penalty", "presence_penalty", "stream"]:
                    continue
                completion_params[key] = value

        # DIAL-specific: Get cached client for deployment endpoint
        deployment_client = self._get_deployment_client(resolved_model)

        attempt_counter = {"value": 0}

        def _attempt() -> ModelResponse:
            attempt_counter["value"] += 1
            response = deployment_client.chat.completions.create(**completion_params)

            content = response.choices[0].message.content
            usage = self._extract_usage(response)

            return ModelResponse(
                content=content,
                usage=usage,
                model_name=model_name,
                friendly_name=self.FRIENDLY_NAME,
                provider=self.get_provider_type(),
                metadata={
                    "finish_reason": response.choices[0].finish_reason,
                    "model": response.model,
                    "id": response.id,
                    "created": response.created,
                },
            )

        try:
            return guardrail.guard_response(
                self._run_with_retries(
                    operation=_attempt,
                    max_attempts=self.MAX_RETRIES,
                    delays=self.RETRY_DELAYS,
                    log_prefix=f"DIAL API ({resolved_model})",
                ),
                _mask_ctx,
            )
        except Exception as exc:
            attempts = max(attempt_counter["value"], 1)
            if attempts == 1:
                raise ValueError(f"DIAL API error for model {resolved_model}: {exc}") from exc

            raise ValueError(f"DIAL API error for model {resolved_model} after {attempts} attempts: {exc}") from exc

    def close(self) -> None:
        """Clean up HTTP clients when provider is closed."""
        logger.info("Closing DIAL provider HTTP clients...")

        # Clear the deployment clients cache
        # Note: We don't need to close individual OpenAI clients since they
        # use the shared httpx.Client which we close separately
        self._deployment_clients.clear()

        # Close the shared HTTP client
        if hasattr(self, "_http_client"):
            try:
                self._http_client.close()
                logger.debug("Closed shared HTTP client")
            except Exception as e:
                logger.warning(f"Error closing shared HTTP client: {e}")

        # Also close the client created by the superclass (OpenAICompatibleProvider)
        # as it holds its own httpx.Client instance that is not used by DIAL's generate_content
        if hasattr(self, "client") and self.client and hasattr(self.client, "close"):
            try:
                self.client.close()
                logger.debug("Closed superclass's OpenAI client")
            except Exception as e:
                logger.warning(f"Error closing superclass's OpenAI client: {e}")
