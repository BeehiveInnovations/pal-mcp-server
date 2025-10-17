"""Tests covering model restriction-aware error messaging in auto mode."""

import asyncio
import importlib
import json

import pytest

import utils.env as env_config
import utils.model_restrictions as model_restrictions
from providers.gemini import GeminiModelProvider
from providers.openai import OpenAIModelProvider
from providers.openrouter import OpenRouterProvider
from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from providers.xai import XAIModelProvider
from tools.shared.exceptions import ToolExecutionError


def _extract_available_models(message: str) -> list[str]:
    """Parse the available model list from the error message."""

    marker = "Available models: "
    if marker not in message:
        raise AssertionError(f"Expected '{marker}' in message: {message}")

    start = message.index(marker) + len(marker)
    end = message.find(". Suggested", start)
    if end == -1:
        end = len(message)

    available_segment = message[start:end].strip()
    if not available_segment:
        return []

    return [item.strip() for item in available_segment.split(",")]


@pytest.fixture
def reset_registry():
    """Ensure registry and restriction service state is isolated."""

    ModelProviderRegistry.reset_for_testing()
    model_restrictions._restriction_service = None
    env_config.reload_env()
    yield
    ModelProviderRegistry.reset_for_testing()
    model_restrictions._restriction_service = None


def _register_core_providers(*, include_xai: bool = False):
    ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
    ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
    ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)
    if include_xai:
        ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)


@pytest.mark.no_mock_provider
def test_error_listing_respects_env_restrictions(monkeypatch, reset_registry):
    """Error payload should surface only the allowed models for each provider."""

    monkeypatch.setenv("DEFAULT_MODEL", "auto")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    # Ensure Azure provider stays disabled regardless of developer workstation env
    for azure_var in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_ALLOWED_MODELS",
        "AZURE_MODELS_CONFIG_PATH",
    ):
        monkeypatch.delenv(azure_var, raising=False)
    monkeypatch.setenv("ZEN_MCP_FORCE_ENV_OVERRIDE", "false")
    env_config.reload_env({"ZEN_MCP_FORCE_ENV_OVERRIDE": "false"})
    try:
        import dotenv

        monkeypatch.setattr(dotenv, "dotenv_values", lambda *_args, **_kwargs: {"ZEN_MCP_FORCE_ENV_OVERRIDE": "false"})
    except ModuleNotFoundError:
        pass

    monkeypatch.setenv("GOOGLE_ALLOWED_MODELS", "gemini-2.5-pro")
    monkeypatch.setenv("OPENAI_ALLOWED_MODELS", "gpt-5")
    monkeypatch.setenv("OPENROUTER_ALLOWED_MODELS", "gpt5nano")
    monkeypatch.setenv("XAI_ALLOWED_MODELS", "")

    import config

    importlib.reload(config)

    _register_core_providers()

    import server

    importlib.reload(server)

    # Reload may have re-applied .env overrides; enforce our test configuration
    for key, value in (
        ("DEFAULT_MODEL", "auto"),
        ("GEMINI_API_KEY", "test-gemini"),
        ("OPENAI_API_KEY", "test-openai"),
        ("OPENROUTER_API_KEY", "test-openrouter"),
        ("GOOGLE_ALLOWED_MODELS", "gemini-2.5-pro"),
        ("OPENAI_ALLOWED_MODELS", "gpt-5"),
        ("OPENROUTER_ALLOWED_MODELS", "gpt5nano"),
        ("XAI_ALLOWED_MODELS", ""),
    ):
        monkeypatch.setenv(key, value)

    for var in ("XAI_API_KEY", "CUSTOM_API_URL", "CUSTOM_API_KEY", "DIAL_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    for azure_var in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_ALLOWED_MODELS",
        "AZURE_MODELS_CONFIG_PATH",
    ):
        monkeypatch.delenv(azure_var, raising=False)

    ModelProviderRegistry.reset_for_testing()
    model_restrictions._restriction_service = None
    server.configure_providers()

    with pytest.raises(ToolExecutionError) as exc_info:
        asyncio.run(
            server.handle_call_tool(
                "chat",
                {
                    "model": "gpt5mini",
                    "prompt": "Tell me about your strengths",
                },
            )
        )

    payload = json.loads(exc_info.value.payload)
    assert payload["status"] == "error"

    available_models = _extract_available_models(payload["content"])
    assert set(available_models) == {"gemini-2.5-pro", "gpt-5", "gpt5nano", "openai/gpt-5-nano"}


@pytest.mark.no_mock_provider
def test_error_listing_without_restrictions_shows_full_catalog(monkeypatch, reset_registry):
    """When no restrictions are set, the full high-capability catalogue should appear."""

    monkeypatch.setenv("DEFAULT_MODEL", "auto")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("XAI_API_KEY", "test-xai")
    monkeypatch.setenv("ZEN_MCP_FORCE_ENV_OVERRIDE", "false")
    for azure_var in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_ALLOWED_MODELS",
        "AZURE_MODELS_CONFIG_PATH",
    ):
        monkeypatch.delenv(azure_var, raising=False)
    env_config.reload_env({"ZEN_MCP_FORCE_ENV_OVERRIDE": "false"})
    try:
        import dotenv

        monkeypatch.setattr(dotenv, "dotenv_values", lambda *_args, **_kwargs: {"ZEN_MCP_FORCE_ENV_OVERRIDE": "false"})
    except ModuleNotFoundError:
        pass

    for var in (
        "GOOGLE_ALLOWED_MODELS",
        "OPENAI_ALLOWED_MODELS",
        "OPENROUTER_ALLOWED_MODELS",
        "XAI_ALLOWED_MODELS",
        "DIAL_ALLOWED_MODELS",
    ):
        monkeypatch.delenv(var, raising=False)

    import config

    importlib.reload(config)

    _register_core_providers(include_xai=True)

    import server

    importlib.reload(server)

    for key, value in (
        ("DEFAULT_MODEL", "auto"),
        ("GEMINI_API_KEY", "test-gemini"),
        ("OPENAI_API_KEY", "test-openai"),
        ("OPENROUTER_API_KEY", "test-openrouter"),
    ):
        monkeypatch.setenv(key, value)

    for var in (
        "GOOGLE_ALLOWED_MODELS",
        "OPENAI_ALLOWED_MODELS",
        "OPENROUTER_ALLOWED_MODELS",
        "XAI_ALLOWED_MODELS",
        "DIAL_ALLOWED_MODELS",
        "CUSTOM_API_URL",
        "CUSTOM_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)

    ModelProviderRegistry.reset_for_testing()
    model_restrictions._restriction_service = None
    server.configure_providers()

    with pytest.raises(ToolExecutionError) as exc_info:
        asyncio.run(
            server.handle_call_tool(
                "chat",
                {
                    "model": "dummymodel",
                    "prompt": "Hi there",
                },
            )
        )

    payload = json.loads(exc_info.value.payload)
    assert payload["status"] == "error"

    available_models = _extract_available_models(payload["content"])
    assert "gemini-2.5-pro" in available_models
    assert "gpt-5" in available_models
    assert "grok-4" in available_models
    assert len(available_models) >= 5
