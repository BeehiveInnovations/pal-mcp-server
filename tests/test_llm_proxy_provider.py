"""Exercise the official client at a local HTTP boundary; no paid calls."""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from providers.llm_proxy import LLMProxyProvider
from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from utils import model_restrictions

pytestmark = pytest.mark.no_mock_provider


@pytest.fixture
def proxy_config(monkeypatch, tmp_path):
    for name in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "XAI_API_KEY",
        "DIAL_API_KEY",
        "OPENROUTER_API_KEY",
        "CUSTOM_API_URL",
        "LLM_PROXY_SECRET",
        "LLM_PROXY_BASE_URL",
        "LLM_PROXY_PROVIDER",
        "LLM_PROXY_ALLOWED_MODELS",
    ):
        monkeypatch.delenv(name, raising=False)
    catalog = tmp_path / "models.json"
    catalog.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "model_name": "tenant-model",
                        "aliases": ["proxy-test"],
                        "context_window": 32000,
                        "max_output_tokens": 2000,
                        "default_reasoning_effort": "high",
                        "supports_images": True,
                    }
                ]
            }
        )
    )
    monkeypatch.setenv("LLM_PROXY_MODELS_CONFIG_PATH", str(catalog))
    monkeypatch.setenv("LLM_PROXY_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("LLM_PROXY_SECRET", "test-tenant-secret")
    monkeypatch.setenv("LLM_PROXY_REQUEST_TIMEOUT_SECONDS", "120")
    monkeypatch.setattr(model_restrictions, "_restriction_service", None)
    previous_registry = ModelProviderRegistry._instance
    ModelProviderRegistry.reset_for_testing()
    yield catalog
    ModelProviderRegistry._instance = previous_registry


@pytest.fixture
def sdk():
    return pytest.importorskip("llm_proxy_client", reason="Install optional SDK as described in docs/llm_proxy.md")


@pytest.fixture
def endpoint(monkeypatch):
    captured = {"status": 200, "response": "Consensus: proceed. ✓", "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            captured["requests"].append(
                {
                    "url": urlsplit(self.path),
                    "headers": self.headers,
                    "body": json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                }
            )
            self.send_response(captured["status"])
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(captured["response"].encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    monkeypatch.setenv("LLM_PROXY_BASE_URL", f"http://127.0.0.1:{server.server_port}/gateway")
    yield captured
    server.shutdown()
    server.server_close()
    thread.join()


def test_official_client_request_and_response(proxy_config, sdk, endpoint, monkeypatch):
    monkeypatch.setenv("LLM_PROXY_PROVIDER", "anthropic")
    provider = LLMProxyProvider("test-tenant-secret")
    result = provider.generate_content(
        "Review this plan ✓", "PROXY-TEST", system_prompt="Be concise", max_output_tokens=42
    )
    request = endpoint["requests"][0]
    assert request["url"].path == "/gateway/v2"
    assert parse_qs(request["url"].query) == {
        "key": ["test-tenant-secret"],
        "format": ["text/plain"],
        "provider": ["anthropic"],
    }
    assert request["headers"]["X-LLM-Proxy-Request-Timeout-Seconds"] == "120"
    assert request["body"] == {
        "messages": [{"role": "system", "content": "Be concise"}, {"role": "user", "content": "Review this plan ✓"}],
        "model": "tenant-model",
        "max_tokens": 42,
        "reasoning_effort": "high",
        "web_search": False,
    }
    assert result.content == "Consensus: proceed. ✓"
    assert result.provider == ProviderType.LLM_PROXY
    assert result.model_name == "tenant-model"
    assert result.usage == {}
    assert provider.validate_model_name("proxy-test")
    assert not provider.get_capabilities("proxy-test").supports_images
    assert not provider.get_capabilities("proxy-test").supports_temperature


def test_delegated_routing_and_catalog_output_limit(proxy_config, sdk, endpoint):
    LLMProxyProvider("test-tenant-secret").generate_content("Hello", "tenant-model")
    request = endpoint["requests"][0]
    assert "provider" not in parse_qs(request["url"].query)
    assert request["body"]["max_tokens"] == 2000
    assert request["body"]["messages"] == [{"role": "user", "content": "Hello"}]


@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_errors_propagate_without_retry(proxy_config, sdk, endpoint, status):
    endpoint.update(status=status, response="proxy rejected request")
    with pytest.raises(sdk.LLMProxyHTTPError) as error:
        LLMProxyProvider("test-tenant-secret").generate_content("Hello", "tenant-model")
    assert error.value.status_code == status
    assert "test-tenant-secret" not in str(error.value)
    assert len(endpoint["requests"]) == 1


def test_transport_failure(proxy_config, sdk):
    with pytest.raises(sdk.LLMProxyTransportError):
        LLMProxyProvider("test-tenant-secret").generate_content("Hello", "tenant-model")


@pytest.mark.parametrize("budget", ["", "0", "-1", "1.5", "abc"])
def test_invalid_budget_fails_before_request(proxy_config, sdk, monkeypatch, budget):
    monkeypatch.setenv("LLM_PROXY_REQUEST_TIMEOUT_SECONDS", budget)
    with pytest.raises(ValueError, match="positive integer"):
        LLMProxyProvider("test-tenant-secret")


def test_empty_catalog_fails(proxy_config, sdk):
    proxy_config.write_text('{"models": []}')
    with pytest.raises(ValueError, match="Configure LLM Proxy models"):
        LLMProxyProvider("test-tenant-secret")


def test_unknown_restricted_and_image_requests_never_dispatch(proxy_config, sdk, endpoint, monkeypatch):
    provider = LLMProxyProvider("test-tenant-secret")
    with pytest.raises(ValueError, match="Unsupported model"):
        provider.generate_content("Hello", "unknown")
    with pytest.raises(ValueError, match="text only"):
        provider.generate_content("Hello", "proxy-test", images=["image.png"])
    monkeypatch.setenv("LLM_PROXY_ALLOWED_MODELS", "other-model")
    monkeypatch.setattr(model_restrictions, "_restriction_service", None)
    assert provider.list_models() == []
    with pytest.raises(ValueError, match="not allowed"):
        provider.generate_content("Hello", "proxy-test")
    assert endpoint["requests"] == []


def test_missing_sdk_is_actionable(proxy_config, monkeypatch):
    monkeypatch.setitem(sys.modules, "llm_proxy_client", None)
    with pytest.raises(ValueError, match="official Python client"):
        LLMProxyProvider("test-tenant-secret")


def test_proxy_only_startup_and_routing(proxy_config, sdk):
    from server import configure_providers

    configure_providers()
    assert ModelProviderRegistry.get_available_providers() == [ProviderType.LLM_PROXY]
    provider = ModelProviderRegistry.get_provider_for_model("proxy-test")
    assert isinstance(provider, LLMProxyProvider)
    assert ModelProviderRegistry.get_provider(ProviderType.LLM_PROXY) is provider
    assert ModelProviderRegistry.get_available_models()["tenant-model"] == ProviderType.LLM_PROXY
    selected = ModelProviderRegistry.get_preferred_fallback_model()
    assert provider.get_capabilities(selected).model_name == "tenant-model"


def test_existing_provider_keeps_priority_but_proxy_alias_selects_proxy(proxy_config, sdk, monkeypatch):
    from providers.base import ModelProvider
    from providers.shared import ModelCapabilities
    from server import configure_providers

    class NativeProvider(ModelProvider):
        MODEL_CAPABILITIES = {
            "tenant-model": ModelCapabilities(
                model_name="tenant-model", friendly_name="Native model", provider=ProviderType.OPENAI
            )
        }

        def get_provider_type(self):
            return ProviderType.OPENAI

        def generate_content(self, *args, **kwargs):
            raise AssertionError("No model calls expected")

    configure_providers()
    monkeypatch.setenv("OPENAI_API_KEY", "test-native-key")
    ModelProviderRegistry.register_provider(ProviderType.OPENAI, NativeProvider)
    assert isinstance(ModelProviderRegistry.get_provider_for_model("tenant-model"), NativeProvider)
    assert isinstance(ModelProviderRegistry.get_provider_for_model("proxy-test"), LLMProxyProvider)


@pytest.mark.parametrize("url", ["", "ftp://proxy.example.com", "https://"])
def test_invalid_connection_config(proxy_config, sdk, monkeypatch, url):
    monkeypatch.setenv("LLM_PROXY_BASE_URL", url)
    with pytest.raises(sdk.LLMProxyClientError):
        LLMProxyProvider("test-tenant-secret")


@pytest.mark.parametrize("missing", ["LLM_PROXY_SECRET", "LLM_PROXY_BASE_URL"])
def test_partial_config_fails_startup(proxy_config, monkeypatch, missing):
    from server import configure_providers

    monkeypatch.delenv(missing)
    with pytest.raises(ValueError, match="requires both"):
        configure_providers()


def test_disabled_proxy_does_not_require_sdk(proxy_config, monkeypatch):
    from server import configure_providers

    monkeypatch.delenv("LLM_PROXY_SECRET")
    monkeypatch.delenv("LLM_PROXY_BASE_URL")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setitem(sys.modules, "llm_proxy_client", None)
    configure_providers()
    assert ModelProviderRegistry.get_available_providers() == [ProviderType.OPENAI]


@pytest.mark.asyncio
async def test_listmodels_reports_proxy(proxy_config, sdk):
    from server import configure_providers
    from tools.listmodels import ListModelsTool

    configure_providers()
    result = await ListModelsTool().execute({})
    assert "LLM Proxy ✅" in result[0].text
    assert "tenant-model" in result[0].text
