"""Anthropic-compatible API provider using Anthropic Messages wire format."""

import logging

import httpx

from .base import ModelProvider
from .shared import (
    ModelResponse,
    ProviderType,
)


class AnthropicCompatibleProvider(ModelProvider):
    """Provider for non-Claude endpoints that accept the Anthropic Messages API wire format."""

    FRIENDLY_NAME = "Anthropic Compatible"

    def __init__(self, api_key: str, base_url: str = None, extra_headers: dict = None, **kwargs):
        super().__init__(api_key, **kwargs)
        if base_url and "anthropic.com" in base_url.lower():
            raise ValueError("AnthropicCompatibleProvider cannot point to api.anthropic.com")
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.extra_headers = extra_headers or {}

    def get_provider_type(self) -> ProviderType:
        return ProviderType.ANTHROPIC_COMPAT

    def validate_model_name(self, model_name: str) -> bool:
        if not model_name:
            return False
        if model_name.lower().startswith("claude"):
            return False
        return True

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str = None,
        temperature: float = 0.3,
        max_output_tokens: int = None,
        tools: list = None,
        **kwargs,
    ) -> ModelResponse:
        if model_name.lower().startswith("claude"):
            raise ValueError(f"Model '{model_name}' starts with 'claude' which is forbidden for non-Claude providers.")

        if not self.base_url:
            raise ValueError("Base URL is required for AnthropicCompatibleProvider")

        url = f"{self.base_url}/v1/messages"

        headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        headers.update(self.extra_headers)

        # Check if any auth header is present
        has_auth = any(
            h.lower() in ["x-api-key", "authorization", "x-ai21-key"] for h in headers
        )
        if not has_auth and self.api_key:
            headers["x-api-key"] = self.api_key

        body = {
            "model": model_name,
            "max_tokens": max_output_tokens or 1024,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if system_prompt:
            body["system"] = system_prompt

        logging.debug(f"Calling Anthropic compatible endpoint {url} with model {model_name}")

        try:
            response = httpx.post(url, headers=headers, json=body, timeout=60.0)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Anthropic compatible endpoint: {e}") from e

        if response.status_code != 200:
            raise RuntimeError(
                f"Anthropic compatible API error ({response.status_code}): {response.text}"
            )

        try:
            resp_json = response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON response from Anthropic compatible endpoint: {e}") from e

        content_blocks = resp_json.get("content", [])
        text = "".join(
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        )

        usage = resp_json.get("usage", {})

        return ModelResponse(
            content=text,
            model_name=model_name,
            friendly_name=self.FRIENDLY_NAME,
            provider=self.get_provider_type(),
            usage=usage,
        )
