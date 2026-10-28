"""Cohere provider via its OpenAI-compatibility endpoint.

Uses https://api.cohere.com/compatibility/v1 (the .com host; .ai redirects and
breaks the custom httpx client). Exposes command-* models with generic
capabilities.
"""

import logging

from .openai_compatible import OpenAICompatibleProvider
from .shared import ModelCapabilities, ProviderType, RangeTemperatureConstraint


class CohereProvider(OpenAICompatibleProvider):
    FRIENDLY_NAME = "Cohere"

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, base_url="https://api.cohere.com/compatibility/v1", **kwargs)

    def get_provider_type(self) -> ProviderType:
        return ProviderType.COHERE

    def _lookup_capabilities(self, canonical_name: str, requested_name: str | None = None):
        if canonical_name.startswith("command"):
            cap = ModelCapabilities(
                provider=ProviderType.COHERE,
                model_name=canonical_name,
                friendly_name=self.FRIENDLY_NAME,
                intelligence_score=9,
                context_window=128_000,
                max_output_tokens=4_096,
                supports_extended_thinking=False,
                supports_system_prompts=True,
                supports_streaming=True,
                supports_function_calling=True,
                temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 1.0),
            )
            cap._is_generic = True
            return cap
        logging.debug("Cohere: empty model name rejected")
        return None

    def generate_content(self, prompt, model_name, system_prompt=None, temperature=0.3,
                         max_output_tokens=None, **kwargs):
        # Cohere command-* models cap output at 4096.
        if max_output_tokens is None or max_output_tokens > 4096:
            max_output_tokens = 4096
        return super().generate_content(
            prompt, model_name, system_prompt, temperature,
            max_output_tokens=max_output_tokens, **kwargs
        )
