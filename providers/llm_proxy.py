"""LLM Proxy adapter using its official, optional Python client."""

from dataclasses import replace
from typing import Optional

from utils.env import get_env

from .base import ModelProvider
from .registries.llm_proxy import LLMProxyModelRegistry
from .shared import ModelCapabilities, ModelResponse, ProviderType


class LLMProxyProvider(ModelProvider):
    """Expose explicitly configured tenant models through PAL's provider API."""

    FRIENDLY_NAME = "LLM Proxy"

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        # Other providers remain usable without this SDK (or Python 3.11+).
        try:
            from llm_proxy_client import Client, ClientConfig
        except ImportError as exc:
            raise ValueError("LLM Proxy requires its official Python client; see docs/llm_proxy.md") from exc

        self._client = Client(
            ClientConfig(
                base_url=get_env("LLM_PROXY_BASE_URL", "") or "",
                secret=api_key,
                provider=get_env("LLM_PROXY_PROVIDER", "") or "",
            )
        )
        try:
            self._request_timeout_seconds = int(get_env("LLM_PROXY_REQUEST_TIMEOUT_SECONDS", "") or "")
        except ValueError as exc:
            raise ValueError("LLM_PROXY_REQUEST_TIMEOUT_SECONDS must be a positive integer") from exc
        if self._request_timeout_seconds <= 0:
            raise ValueError("LLM_PROXY_REQUEST_TIMEOUT_SECONDS must be a positive integer")

        registry = LLMProxyModelRegistry()
        if not registry.model_map:
            raise ValueError("Configure LLM Proxy models in conf/llm_proxy_models.json or LLM_PROXY_MODELS_CONFIG_PATH")
        # This adapter exposes text completions only. The SDK returns plain text,
        # not usage data, and has no temperature field in its messages request.
        self.MODEL_CAPABILITIES = {
            name: replace(
                caps,
                supports_images=False,
                supports_temperature=False,
                supports_streaming=False,
                supports_function_calling=False,
                supports_json_mode=False,
                allow_code_generation=False,
            )
            for name, caps in registry.model_map.items()
        }

    def get_provider_type(self) -> ProviderType:
        return ProviderType.LLM_PROXY

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        from llm_proxy_client import ClientMessage, ClientMessagesRequest

        capabilities: ModelCapabilities = self.get_capabilities(model_name)
        if kwargs.get("images"):
            raise ValueError("LLM Proxy's PAL adapter supports text only")
        messages = []
        if system_prompt:
            messages.append(ClientMessage(role="system", content=system_prompt))
        messages.append(ClientMessage(role="user", content=prompt))
        request = ClientMessagesRequest(
            messages=messages,
            model=capabilities.model_name,
            max_tokens=max_output_tokens if max_output_tokens is not None else capabilities.max_output_tokens or None,
            reasoning_effort=capabilities.default_reasoning_effort,
            request_timeout_seconds=self._request_timeout_seconds,
        )
        content = self._client.post_messages(request)
        return ModelResponse(
            content=content,
            model_name=capabilities.model_name,
            friendly_name=capabilities.friendly_name,
            provider=self.get_provider_type(),
        )
