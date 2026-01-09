"""SAIA AI model provider implementation with API key rotation.

SAIA is an OpenAI-compatible API hosted by GWDG Academic Cloud.
This provider implements intelligent API key rotation to balance usage across multiple keys.

Documentation: https://docs.hpc.gwdg.de/services/saia/
Base URL: https://chat-ai.academiccloud.de/v1
"""

import logging
from typing import TYPE_CHECKING, Optional

from .openai_compatible import OpenAICompatibleProvider
from .api_key_rotator import APIKeyRotator, RateLimitHeaders, RotationStrategy
from .shared import ModelCapabilities, ModelResponse
from .shared.provider_type import ProviderType
from utils.env import get_env

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

logger = logging.getLogger(__name__)


class SAIAProvider(OpenAICompatibleProvider):
    """
    SAIA AI provider with automatic API key rotation.

    Features:
    - OpenAI-compatible API (chat/completions, completions, embeddings, models)
    - Thread-safe API key rotation with multiple strategies
    - Per-key rate limit tracking from response headers
    - Automatic backoff when keys hit rate limits
    - Retry with different keys on 429/500 errors
    - Model aliases for SAIA-specific models

    Supported Models:
        - meta-llama-3.1-8b-instruct
        - openai-gpt-oss-120b
        - meta-llama-3.1-8b-rag (Arcana)
        - llama-3.1-sauerkrautlm-70b-instruct
        - llama-3.3-70b-instruct
        - gemma-3-27b-it
        - medgemma-27b-it
        - teuken-7b-instruct-research
        - mistral-large-instruct
        - qwen3-32b
        - qwen3-235b-a22b (reasoning)
        - qwen2.5-coder-32b-instruct (code)
        - codestral-22b (code)
        - internvl2.5-8b (text, image)
        - qwen2.5-vl-72b-instruct (text, image)
        - qwq-32b (reasoning)
        - deepseek-r1 (reasoning)
        - e5-mistral-7b-instruct (embeddings)
        - multilingual-e5-large-instruct (embeddings)
        - qwen3-embedding-4b (embeddings)
    """

    FRIENDLY_NAME = "SAIA AI"
    DEFAULT_HEADERS = {
        "User-Agent": "PAL MCP Server - SAIA Provider",
    }

    SAIA_BASE_URL = "https://chat-ai.academiccloud.de/v1"

    # Model capabilities for SAIA models
    MODEL_CAPABILITIES = {
        # Text models
        "meta-llama-3.1-8b-instruct": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="meta-llama-3.1-8b-instruct",
            friendly_name="SAIA: Meta Llama 3.1 8B Instruct",
            intelligence_score=6,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["llama-3.1", "llama-instruct"],
        ),
        "openai-gpt-oss-120b": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="openai-gpt-oss-120b",
            friendly_name="SAIA: OpenAI GPT OSS 120B",
            intelligence_score=5,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["gpt-oss-120b"],
        ),
        "meta-llama-3.1-8b-rag": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="meta-llama-3.1-8b-rag",
            friendly_name="SAIA: Meta Llama 3.1 8B RAG (Arcana)",
            intelligence_score=7,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["llama-rag", "arcana"],
        ),
        "llama-3.1-sauerkrautlm-70b-instruct": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="llama-3.1-sauerkrautlm-70b-instruct",
            friendly_name="SAIA: Llama 3.1 SaUerkRauTLM 70B Instruct",
            intelligence_score=7,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["sauerkrautlm", "sauerk"],
        ),
        "llama-3.3-70b-instruct": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="llama-3.3-70b-instruct",
            friendly_name="SAIA: Llama 3.3 70B Instruct",
            intelligence_score=8,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["llama-3.3"],
        ),
        "gemma-3-27b-it": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="gemma-3-27b-it",
            friendly_name="SAIA: Gemma 3 27B IT",
            intelligence_score=8,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["gemma-3.27"],
        ),
        "medgemma-27b-it": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="medgemma-27b-it",
            friendly_name="SAIA: MedGemma 27B IT",
            intelligence_score=7,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["medgemma", "gemma-27b"],
        ),
        "teuken-7b-instruct-research": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="teuken-7b-instruct-research",
            friendly_name="SAIA: Teuken 7B Research",
            intelligence_score=7,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["teuken"],
        ),
        "mistral-large-instruct": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="mistral-large-instruct",
            friendly_name="SAIA: Mistral Large",
            intelligence_score=9,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["mistral-large"],
        ),
        "qwen3-32b": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="qwen3-32b",
            friendly_name="SAIA: Qwen 3 32B",
            intelligence_score=7,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["qwen-3", "qwen32"],
        ),
        "qwen3-235b-a22b": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="qwen3-235b-a22b",
            friendly_name="SAIA: Qwen 3 235B A22B (Reasoning)",
            intelligence_score=9,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["qwen-235b", "qwen-a22b", "qwen-reasoning"],
        ),
        "qwen2.5-coder-32b-instruct": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="qwen2.5-coder-32b-instruct",
            friendly_name="SAIA: Qwen 2.5 Coder 32B",
            intelligence_score=8,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["qwen-coder", "qwen2.5-coder"],
        ),
        "codestral-22b": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="codestral-22b",
            friendly_name="SAIA: Codestral 22B",
            intelligence_score=8,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["codestral"],
        ),
        "internvl2.5-8b": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="internvl2.5-8b",
            friendly_name="SAIA: InternVL 2.5 8B",
            intelligence_score=7,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["internvl"],
        ),
        "qwen2.5-vl-72b-instruct": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="qwen2.5-vl-72b-instruct",
            friendly_name="SAIA: Qwen 2.5 VL 72B",
            intelligence_score=8,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["qwen-vl", "qwen-vl72"],
        ),
        "qwq-32b": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="qwq-32b",
            friendly_name="SAIA: QwQ 32B",
            intelligence_score=10,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["qwq"],
        ),
        "deepseek-r1": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="deepseek-r1",
            friendly_name="SAIA: DeepSeek R1",
            intelligence_score=10,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["deepseek"],
        ),
        "e5-mistral-7b-instruct": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="e5-mistral-7b-instruct",
            friendly_name="SAIA: E5 Mistral 7B",
            intelligence_score=8,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["e5"],
        ),
        "multilingual-e5-large-instruct": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="multilingual-e5-large-instruct",
            friendly_name="SAIA: Multilingual E5 Large",
            intelligence_score=9,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["e5-large", "e5-multilingual"],
        ),
        "qwen3-embedding-4b": ModelCapabilities(
            provider=ProviderType.SAIA,
            model_name="qwen3-embedding-4b",
            friendly_name="SAIA: Qwen 3 Embedding 4B",
            intelligence_score=7,
            context_window=32_768,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            temperature_constraint=None,
            aliases=["qwen-embed"],
        ),
    }

    def __init__(self, api_keys: list[str], **kwargs):
        """
        Initialize SAIA provider with API key rotation.

        Args:
            api_keys: List of SAIA API keys to rotate through
            **kwargs: Additional configuration options:
                - strategy: Rotation strategy (round_robin, least_used, random)
                - backoff_seconds: Backoff duration for exhausted keys (default 60)
        """
        if not api_keys or not any(api_keys):
            raise ValueError("At least one SAIA API key is required")

        # Extract rotation configuration
        strategy = kwargs.get("strategy", RotationStrategy.ROUND_ROBIN)
        backoff_seconds = kwargs.get("backoff_seconds", 60)

        # Initialize API key rotator
        self.key_rotator = APIKeyRotator(api_keys, strategy=strategy, backoff_seconds=backoff_seconds)

        # Set SAIA-specific default headers
        custom_headers = {**self.DEFAULT_HEADERS}
        if "headers" in kwargs:
            custom_headers.update(kwargs["headers"])

        # Initialize parent class with first key
        # We'll override api_key in generate_content to use rotation
        first_key, _ = self.key_rotator.get_next_key()
        logger.info(f"Initializing SAIA provider with {len(api_keys)} API keys, strategy: {strategy}")

        super().__init__(
            api_key=first_key,  # Placeholder, actual key selected at runtime
            base_url=self.SAIA_BASE_URL,
            **kwargs,
        )

    def get_provider_type(self):
        """Return SAIA provider type."""
        from .shared import ProviderType

        # Will need to add SAIA to ProviderType enum
        # For now return a string until the enum is updated
        return ProviderType.SAIA if hasattr(ProviderType, "SAIA") else "saia"

    def _lookup_capabilities(
        self,
        canonical_name: str,
        requested_name: str | None = None,
    ) -> ModelCapabilities | None:
        """Look up SAIA capabilities from MODEL_CAPABILITIES."""
        return self.MODEL_CAPABILITIES.get(canonical_name)

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_output_tokens: int | None = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Generate content using SAIA API with automatic key rotation.

        Args:
            prompt: The user prompt to send
            model_name: Model to use (from SAIA catalog)
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-2.0)
            max_output_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            ModelResponse with generated content and usage metadata
        """
        import httpx

        # Select API key with rotation
        selected_key, rate_limit_info = self.key_rotator.get_next_key(skip_exhausted=False)

        # Override parent's api_key with selected key
        self.api_key = selected_key

        try:
            # Prepare request
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Build request payload
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
            }

            if max_output_tokens:
                payload["max_tokens"] = max_output_tokens

            # Add optional parameters
            if "top_p" in kwargs:
                payload["top_p"] = kwargs["top_p"]

            # Configure HTTP client
            if not self.client:
                timeout_config = self.timeout_config if hasattr(self, "timeout_config") else httpx.Timeout(30.0)
                http_client = httpx.Client(
                    timeout=timeout_config,
                    follow_redirects=True,
                )
                self._client = http_client

            # Make request with selected API key
            response = self._client.post(
                f"{self.SAIA_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    **self.DEFAULT_HEADERS,
                },
            )

            # Check for rate limit headers
            rate_limit_info = self.key_rotator._parse_rate_limit_headers(dict(response.headers))

            if rate_limit_info:
                # Update usage tracking for this key
                self.key_rotator._update_key_usage(self.api_key, dict(response.headers))

                logger.debug(
                    f"Rate limit headers - limit: {rate_limit_info.limit_minute}/min, "
                    f"remaining: {rate_limit_info.remaining_minute}/min"
                )

            # Parse response
            if response.status_code == 200:
                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    content = choice.get("message", {}).get("content", "")

                    return ModelResponse(
                        content=content,
                        usage=data.get("usage", {}).get("total_tokens", 0),
                        model_name=model_name,
                        friendly_name=f"{self.FRIENDLY_NAME}",
                        provider=self.get_provider_type(),
                        metadata={
                            "rate_limit_info": rate_limit_info.model_dump() if rate_limit_info else None,
                            "api_key_used": f"{self.api_key[:10]}...",
                            "finish_reason": choice.get("finish_reason"),
                        },
                    )
                else:
                    raise ValueError(f"Invalid SAIA response: {data}")
            elif response.status_code == 429:
                # Rate limit hit - mark key as exhausted and retry with next key
                logger.warning(f"Rate limit hit (429) for key {self.api_key[:10]}... - marking exhausted and rotating")
                self.key_rotator.mark_key_exhausted(self.api_key)

                # Retry with next key (skip exhausted keys)
                new_key, new_rate_limit_info = self.key_rotator.get_next_key(skip_exhausted=True)

                # Override API key and retry
                self.api_key = new_key

                logger.info(f"Rotating to new key {new_key[:10]}... for retry (strategy: {self.key_rotator.strategy})")

                # Retry the request with new key
                response = self._client.post(
                    f"{self.SAIA_BASE_URL}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        **self.DEFAULT_HEADERS,
                    },
                )

                # Parse retry response
                if response.status_code == 200:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        content = choice.get("message", {}).get("content", "")

                        # Update usage tracking for new key
                        if new_rate_limit_info:
                            self.key_rotator._update_key_usage(self.api_key, dict(response.headers))

                        return ModelResponse(
                            content=content,
                            usage=data.get("usage", {}).get("total_tokens", 0),
                            model_name=model_name,
                            friendly_name=f"{self.FRIENDLY_NAME}",
                            provider=self.get_provider_type(),
                            metadata={
                                "rate_limit_info": new_rate_limit_info.model_dump() if new_rate_limit_info else None,
                                "api_key_used": f"{self.api_key[:10]}...",
                                "finish_reason": choice.get("finish_reason"),
                                "rotation_performed": True,
                            },
                        )
                else:
                    raise ValueError(f"Invalid SAIA response: {data}")

            elif response.status_code >= 500:
                # Server error - try next key
                logger.warning(
                    f"Server error ({response.status_code}) for key {self.api_key[:10]}... - rotating to next key"
                )
                new_key, _ = self.key_rotator.get_next_key(skip_exhausted=True)
                self.api_key = new_key

                response = self._client.post(
                    f"{self.SAIA_BASE_URL}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        **self.DEFAULT_HEADERS,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        content = choice.get("message", {}).get("content", "")

                        return ModelResponse(
                            content=content,
                            usage=data.get("usage", {}).get("total_tokens", 0),
                            model_name=model_name,
                            friendly_name=f"{self.FRIENDLY_NAME}",
                            provider=self.get_provider_type(),
                            metadata={
                                "rate_limit_info": rate_limit_info.model_dump() if rate_limit_info else None,
                                "api_key_used": f"{self.api_key[:10]}...",
                                "finish_reason": choice.get("finish_reason"),
                                "server_error_retry": True,
                            },
                        )

                else:
                    raise ValueError(f"Invalid SAIA response after server error retry: {data}")

            else:
                # Other errors
                raise ValueError(f"SAIA API error: {response.status_code} - {response.text}")

        except Exception as exc:
            logger.error(f"SAIA API request failed: {exc}")

            # Check if should retry with different key
            if self._is_retryable_error(exc):
                logger.info("Error is retryable, rotating API key...")

                # Mark current key as potentially exhausted
                self.key_rotator.mark_key_exhausted(self.api_key)

                # Try with next key
                new_key, _ = self.key_rotator.get_next_key(skip_exhausted=True)
                self.api_key = new_key

                # Recursive retry call
                return self.generate_content(
                    prompt=prompt,
                    model_name=model_name,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    **kwargs,
                )
            else:
                raise

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if error warrants retry with key rotation.

        Args:
            error: The exception to check

        Returns:
            True if error is retryable with key rotation, False otherwise
        """
        error_str = str(error).lower()

        # Retry on these errors with key rotation
        retryable_errors = [
            "rate limit",
            "429",
            "quota exceeded",
            "exceeded",
            "timeout",
            "connection",
            "503",
            "502",
            "500",
            "internal server error",
        ]

        return any(indicator in error_str for indicator in retryable_errors)

    def get_rotation_stats(self) -> dict:
        """
        Get rotation statistics for monitoring and debugging.

        Returns:
            Dictionary with rotation statistics
        """
        return self.key_rotator.get_usage_stats()
