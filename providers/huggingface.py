"""HuggingFace router provider (OpenAI-compatible).

Surfaces HuggingFace's inference router (https://router.huggingface.co/v1)
through the standard OpenAI-compatible path, so org/model ids such as
``meta-llama/Llama-3.1-8B-Instruct`` or ``deepseek-ai/DeepSeek-V4.1-Flash``
are routable like any other provider. Capabilities are generic (org/model
format), mirroring the OpenRouter fallback.
"""

import logging

from .openai_compatible import OpenAICompatibleProvider
from .shared import ModelCapabilities, ProviderType, RangeTemperatureConstraint


class HuggingFaceProvider(OpenAICompatibleProvider):
    FRIENDLY_NAME = "HuggingFace"

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, base_url="https://router.huggingface.co/v1", **kwargs)

    def get_provider_type(self) -> ProviderType:
        return ProviderType.HUGGINGFACE

    def _lookup_capabilities(self, canonical_name: str, requested_name: str | None = None):
        if "/" in canonical_name and ":" not in canonical_name:
            cap = ModelCapabilities(
                provider=ProviderType.HUGGINGFACE,
                model_name=canonical_name,
                friendly_name=self.FRIENDLY_NAME,
                intelligence_score=9,
                context_window=32_768,
                max_output_tokens=8_192,
                supports_extended_thinking=False,
                supports_system_prompts=True,
                supports_streaming=True,
                supports_function_calling=True,
                temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 1.0),
            )
            cap._is_generic = True
            return cap
        logging.debug("HuggingFace: rejecting non org/model id '%s'", canonical_name)
        return None
