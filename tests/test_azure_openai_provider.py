import sys
import types

import pytest

if "openai" not in sys.modules:  # pragma: no cover - test shim for optional dependency
    stub = types.ModuleType("openai")
    stub.AzureOpenAI = object  # Replaced with a mock inside tests
    sys.modules["openai"] = stub

from providers.azure_openai import AzureOpenAIProvider
from providers.shared import ModelCapabilities, ProviderType


class _DummyResponse:
    def __init__(self):
        self.choices = [
            types.SimpleNamespace(
                message=types.SimpleNamespace(content="hello"),
                finish_reason="stop",
            )
        ]
        self.model = "prod-gpt4o"
        self.id = "resp-123"
        self.created = 0
        self.usage = types.SimpleNamespace(
            prompt_tokens=5,
            completion_tokens=3,
            total_tokens=8,
        )


@pytest.fixture
def dummy_azure_client(monkeypatch):
    captured = {}

    class _DummyAzureClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create_completion))
            self.responses = types.SimpleNamespace(create=self._create_response)

        def _create_completion(self, **kwargs):
            captured["request_kwargs"] = kwargs
            return _DummyResponse()

        def _create_response(self, **kwargs):
            captured["responses_kwargs"] = kwargs
            return _DummyResponse()

    monkeypatch.delenv("AZURE_OPENAI_ALLOWED_MODELS", raising=False)
    monkeypatch.setattr("providers.azure_openai.AzureOpenAI", _DummyAzureClient)
    return captured


def test_generate_content_uses_deployment_mapping(dummy_azure_client):
    provider = AzureOpenAIProvider(
        api_key="key",
        azure_endpoint="https://example.openai.azure.com/",
        deployments={"gpt-4o": "prod-gpt4o"},
    )

    result = provider.generate_content("hello", "gpt-4o")

    assert dummy_azure_client["request_kwargs"]["model"] == "prod-gpt4o"
    assert result.model_name == "gpt-4o"
    assert result.provider == ProviderType.AZURE
    assert provider.validate_model_name("prod-gpt4o")


def test_generate_content_accepts_deployment_alias(dummy_azure_client):
    provider = AzureOpenAIProvider(
        api_key="key",
        azure_endpoint="https://example.openai.azure.com/",
        deployments={"gpt-4o-mini": "mini-deployment"},
    )

    # Calling with the deployment alias should still resolve properly.
    result = provider.generate_content("hi", "mini-deployment")

    assert dummy_azure_client["request_kwargs"]["model"] == "mini-deployment"
    assert result.model_name == "gpt-4o-mini"


def test_client_initialization_uses_endpoint_and_version(dummy_azure_client):
    provider = AzureOpenAIProvider(
        api_key="key",
        azure_endpoint="https://example.openai.azure.com/",
        api_version="2024-03-15-preview",
        deployments={"gpt-4o": "prod"},
    )

    _ = provider.client

    assert dummy_azure_client["client_kwargs"]["azure_endpoint"] == "https://example.openai.azure.com"
    assert dummy_azure_client["client_kwargs"]["api_version"] == "2024-03-15-preview"


def test_deployment_overrides_capabilities(dummy_azure_client):
    provider = AzureOpenAIProvider(
        api_key="key",
        azure_endpoint="https://example.openai.azure.com/",
        deployments={
            "gpt-4o": {
                "deployment": "prod-gpt4o",
                "friendly_name": "Azure GPT-4o EU",
                "intelligence_score": 19,
                "supports_temperature": False,
                "temperature_constraint": "fixed",
            }
        },
    )

    caps = provider.get_capabilities("gpt-4o")
    assert caps.friendly_name == "Azure GPT-4o EU"
    assert caps.intelligence_score == 19
    assert not caps.supports_temperature


def test_registry_configuration_merges_capabilities(dummy_azure_client, monkeypatch):
    def fake_registry_entries(self):
        capability = ModelCapabilities(
            provider=ProviderType.AZURE,
            model_name="gpt-4o",
            friendly_name="Azure GPT-4o Registry",
            context_window=500_000,
            max_output_tokens=128_000,
        )
        return {"gpt-4o": {"deployment": "registry-deployment", "capability": capability}}

    monkeypatch.setattr(AzureOpenAIProvider, "_load_registry_entries", fake_registry_entries)

    provider = AzureOpenAIProvider(
        api_key="key",
        azure_endpoint="https://example.openai.azure.com/",
    )

    # Capability should come from registry
    caps = provider.get_capabilities("gpt-4o")
    assert caps.friendly_name == "Azure GPT-4o Registry"
    assert caps.context_window == 500_000

    # API call should use deployment defined in registry
    provider.generate_content("hello", "gpt-4o")
    assert dummy_azure_client["request_kwargs"]["model"] == "registry-deployment"


# ---------------------------------------------------------------------------
# Entra ID (AZURE_OPENAI_USE_ENTRA) auth
# ---------------------------------------------------------------------------


def _fake_token_provider():
    return "fake-entra-token"


def test_entra_mode_uses_token_provider_without_api_key(dummy_azure_client, monkeypatch):
    built = {}

    def fake_build(**kwargs):
        built.update(kwargs)
        return _fake_token_provider

    monkeypatch.setattr("providers.azure_openai.build_entra_token_provider", fake_build)
    provider = AzureOpenAIProvider(
        api_key="",
        azure_endpoint="https://example.openai.azure.com/",
        deployments={"gpt-4o": "prod"},
        use_entra=True,
    )

    _ = provider.client

    client_kwargs = dummy_azure_client["client_kwargs"]
    assert client_kwargs["azure_ad_token_provider"] is _fake_token_provider
    assert "api_key" not in client_kwargs
    assert client_kwargs["azure_endpoint"] == "https://example.openai.azure.com"
    assert built == {"label": "Azure OpenAI", "endpoint": "https://example.openai.azure.com"}


def test_entra_flag_read_from_env(dummy_azure_client, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_USE_ENTRA", "true")
    monkeypatch.setattr("providers.azure_openai.build_entra_token_provider", lambda **_: _fake_token_provider)
    provider = AzureOpenAIProvider(
        api_key="", azure_endpoint="https://example.openai.azure.com/", deployments={"gpt-4o": "prod"}
    )

    _ = provider.client

    assert dummy_azure_client["client_kwargs"]["azure_ad_token_provider"] is _fake_token_provider


def test_entra_mode_does_not_warn_about_missing_key(dummy_azure_client, monkeypatch, caplog):
    monkeypatch.setattr("providers.azure_openai.build_entra_token_provider", lambda **_: _fake_token_provider)
    with caplog.at_level("WARNING"):
        AzureOpenAIProvider(
            api_key="", azure_endpoint="https://example.openai.azure.com/", deployments={"gpt-4o": "p"}, use_entra=True
        )
    assert "without API key" not in caplog.text


def test_key_mode_is_unchanged_when_flag_off(dummy_azure_client, monkeypatch):
    def fail_build(**_):
        raise AssertionError("Entra token provider must not be built in key mode")

    monkeypatch.setattr("providers.azure_openai.build_entra_token_provider", fail_build)
    provider = AzureOpenAIProvider(
        api_key="key", azure_endpoint="https://example.openai.azure.com/", deployments={"gpt-4o": "prod"}
    )

    _ = provider.client

    client_kwargs = dummy_azure_client["client_kwargs"]
    assert client_kwargs["api_key"] == "key"
    assert "azure_ad_token_provider" not in client_kwargs


def test_entra_mode_without_azure_identity_raises_clear_error(dummy_azure_client, monkeypatch):
    # A None entry in sys.modules makes `from azure.identity import ...` raise ImportError.
    monkeypatch.setitem(sys.modules, "azure.identity", None)
    provider = AzureOpenAIProvider(
        api_key="", azure_endpoint="https://example.openai.azure.com/", deployments={"gpt-4o": "p"}, use_entra=True
    )

    with pytest.raises(ImportError, match="azure-identity"):
        _ = provider.client


def test_reasoning_deployment_sends_max_completion_tokens(dummy_azure_client):
    # GPT-5.x deployments reject max_tokens with HTTP 400 ("Use 'max_completion_tokens' instead").
    provider = AzureOpenAIProvider(
        api_key="key",
        azure_endpoint="https://example.openai.azure.com/",
        deployments={"gpt-5.4": {"deployment": "gpt54", "supports_extended_thinking": True}},
    )

    provider.generate_content("hi", "gpt-5.4", max_output_tokens=20)

    request = dummy_azure_client["request_kwargs"]
    assert request["max_completion_tokens"] == 20
    assert "max_tokens" not in request


def test_non_reasoning_deployment_keeps_max_tokens(dummy_azure_client):
    provider = AzureOpenAIProvider(
        api_key="key", azure_endpoint="https://example.openai.azure.com/", deployments={"gpt-4o": "prod"}
    )

    provider.generate_content("hi", "gpt-4o", max_output_tokens=20)

    request = dummy_azure_client["request_kwargs"]
    assert request["max_tokens"] == 20
    assert "max_completion_tokens" not in request
