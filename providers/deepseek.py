"""DeepSeek model provider implementation."""

import logging
import time
from typing import TYPE_CHECKING, Optional

from .base import (
    ModelCapabilities,
    ModelResponse,
    ProviderType,
    create_temperature_constraint,
)
from .openai_compatible import OpenAICompatibleProvider

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

logger = logging.getLogger(__name__)


class DeepSeekModelProvider(OpenAICompatibleProvider):
    """Provider for DeepSeek's OpenAI-compatible API."""

    FRIENDLY_NAME = "DeepSeek"

    SUPPORTED_MODELS = {
        "deepseek-chat": ModelCapabilities(
            provider=ProviderType.DEEPSEEK,
            model_name="deepseek-chat",
            friendly_name="DeepSeek (Chat)",
            context_window=128_000,
            max_output_tokens=16_000,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=False,
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            description="DeepSeek V3.1 chat model (non-reasoning mode)",
            aliases=["deepseek", "chat"],
        ),
        "deepseek-reasoner": ModelCapabilities(
            provider=ProviderType.DEEPSEEK,
            model_name="deepseek-reasoner",
            friendly_name="DeepSeek (Reasoner)",
            context_window=128_000,
            max_output_tokens=16_000,
            supports_extended_thinking=True,
            max_thinking_tokens=16_000,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=False,
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            description="DeepSeek V3.1 reasoning model with thinking tokens",
            aliases=["reasoner"],
        ),
    }

    def __init__(self, api_key: str, **kwargs):
        """Initialize DeepSeek provider with API key and optional settings."""
        kwargs.setdefault("base_url", "https://api.deepseek.com")
        super().__init__(api_key, **kwargs)

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.DEEPSEEK

    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific DeepSeek model."""
        if model_name in self.SUPPORTED_MODELS:
            capabilities = self.SUPPORTED_MODELS[model_name]
        else:
            resolved_name = self._resolve_model_name(model_name)
            capabilities = self.SUPPORTED_MODELS.get(resolved_name)
            model_name = resolved_name

        if not capabilities:
            raise ValueError(f"Unsupported DeepSeek model: {model_name}")

        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.DEEPSEEK, capabilities.model_name, model_name):
            raise ValueError(f"DeepSeek model '{model_name}' is not allowed by restriction policy.")

        return capabilities

    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported and allowed."""
        resolved_name = self._resolve_model_name(model_name)
        if resolved_name not in self.SUPPORTED_MODELS:
            return False
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.DEEPSEEK, resolved_name, model_name):
            logger.debug(f"DeepSeek model '{model_name}' -> '{resolved_name}' blocked by restrictions")
            return False
        return True

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.6,  # Official recommended value from DeepSeek V3.1 generation_config.json
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using DeepSeek API with alias resolution and reasoning content support."""
        resolved_model_name = self._resolve_model_name(model_name)

        # For reasoning models, we need to handle reasoning_content specially
        if resolved_model_name == "deepseek-reasoner":
            return self._generate_with_reasoning(
                prompt=prompt,
                model_name=resolved_model_name,
                system_prompt=system_prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                **kwargs,
            )

        return super().generate_content(
            prompt=prompt,
            model_name=resolved_model_name,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            **kwargs,
        )

    def _generate_with_reasoning(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.6,  # Official recommended value from DeepSeek V3.1 generation_config.json
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content with reasoning support for DeepSeek reasoner models."""

        # Get effective temperature for this model
        effective_temperature = self.get_effective_temperature(model_name, temperature)

        # Only validate if temperature is not None (meaning the model supports it)
        if effective_temperature is not None:
            self.validate_parameters(model_name, effective_temperature)

        # Prepare messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # Prepare completion parameters
        completion_params = {
            "model": model_name,
            "messages": messages,
        }

        # Use the effective temperature we calculated earlier
        if effective_temperature is not None:
            completion_params["temperature"] = effective_temperature

        # Add max tokens if specified
        if max_output_tokens:
            completion_params["max_tokens"] = max_output_tokens

        # Add any additional parameters
        for key, value in kwargs.items():
            if key in ["top_p", "frequency_penalty", "presence_penalty", "seed", "stop", "stream"]:
                completion_params[key] = value

        # Retry logic with progressive delays
        max_retries = 4
        retry_delays = [1, 3, 5, 8]
        last_exception = None
        actual_attempts = 0

        for attempt in range(max_retries):
            actual_attempts = attempt + 1
            try:
                # Generate completion
                response = self.client.chat.completions.create(**completion_params)

                # Extract content and reasoning content
                message = response.choices[0].message
                final_answer = message.content or ""
                reasoning_content = getattr(message, "reasoning_content", None) or ""

                # Combine display content (show reasoning process + final answer if reasoning exists)
                if reasoning_content:
                    display_content = (
                        f"**Reasoning Process:**\n\n{reasoning_content}\n\n**Final Answer:**\n\n{final_answer}"
                    )
                else:
                    display_content = final_answer

                # Extract usage information
                usage = self._extract_usage(response)

                return ModelResponse(
                    content=display_content,  # Full content shown to user (reasoning + answer)
                    usage=usage,
                    model_name=model_name,
                    friendly_name=self.FRIENDLY_NAME,
                    provider=self.get_provider_type(),
                    metadata={
                        "finish_reason": response.choices[0].finish_reason,
                        "model": response.model,
                        "id": response.id,
                        "created": response.created,
                        "reasoning_content": reasoning_content,  # Store reasoning content in metadata
                        "final_answer": final_answer,  # Store final answer (for conversation history)
                        "has_reasoning": bool(reasoning_content),
                    },
                )

            except Exception as e:
                last_exception = e

                # Check if this is a retryable error
                is_retryable = self._is_error_retryable(e)

                # If this is the last attempt or not retryable, give up
                if attempt == max_retries - 1 or not is_retryable:
                    break

                # Get progressive delay
                delay = retry_delays[attempt]
                logger.warning(
                    f"DeepSeek reasoning error for model {model_name}, attempt {actual_attempts}/{max_retries}: {str(e)}. Retrying in {delay}s..."
                )

                time.sleep(delay)

        # All retries failed
        error_msg = f"DeepSeek reasoning API error for model {model_name} after {actual_attempts} attempt{'s' if actual_attempts > 1 else ''}: {str(last_exception)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from last_exception

    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if the model supports extended thinking mode."""
        resolved = self._resolve_model_name(model_name)
        capabilities = self.SUPPORTED_MODELS.get(resolved)
        return bool(capabilities and capabilities.supports_extended_thinking)

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get DeepSeek's preferred model for a given category from allowed models.

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
            # Prefer reasoning model for complex analysis
            preferred = find_first(["deepseek-reasoner"])
            return preferred if preferred else allowed_models[0]

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer chat model for faster responses
            preferred = find_first(["deepseek-chat"])
            return preferred if preferred else allowed_models[0]

        else:  # BALANCED or default
            # Prefer chat model for general balanced use
            preferred = find_first(["deepseek-chat", "deepseek-reasoner"])
            return preferred if preferred else allowed_models[0]
