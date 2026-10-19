"""Unit tests for the shared Entra ID token helper (providers/azure_entra.py). No network."""

import logging
import sys
import types

import pytest

from providers.azure_entra import COGNITIVE_SERVICES_SCOPE, build_entra_token_provider, redact_auth_headers_in_logs

SECRET = "entra-secret-token-0123456789"


class AzureCliCredential:
    """Stand-in for the credential DefaultAzureCredential reports as the one that produced the token."""


@pytest.fixture
def fake_azure_identity(monkeypatch):
    calls = {"scopes": [], "fetches": 0}

    class DefaultAzureCredential:
        def __init__(self):
            self._successful_credential = None

    def get_bearer_token_provider(credential, *scopes):
        calls["scopes"].extend(scopes)

        def fetch():
            calls["fetches"] += 1
            credential._successful_credential = AzureCliCredential()
            return SECRET

        return fetch

    module = types.ModuleType("azure.identity")
    module.DefaultAzureCredential = DefaultAzureCredential
    module.get_bearer_token_provider = get_bearer_token_provider
    monkeypatch.setitem(sys.modules, "azure.identity", module)
    return calls


def test_token_provider_returns_token_for_cognitive_services_scope(fake_azure_identity):
    provider = build_entra_token_provider(label="Azure OpenAI", endpoint="https://res.openai.azure.com/")

    assert provider() == SECRET
    assert fake_azure_identity["scopes"] == [COGNITIVE_SERVICES_SCOPE]


def test_token_provider_logs_credential_type_and_host_once_never_the_token(fake_azure_identity, caplog):
    provider = build_entra_token_provider(label="Azure OpenAI", endpoint="https://res.openai.azure.com/")

    with caplog.at_level(logging.DEBUG, logger="providers.azure_entra"):
        provider()
        provider()

    messages = [r.getMessage() for r in caplog.records if r.name == "providers.azure_entra"]
    assert messages == ["Azure OpenAI: Entra ID token acquired via AzureCliCredential for res.openai.azure.com"]
    assert SECRET not in caplog.text
    assert fake_azure_identity["fetches"] == 2  # each call asks azure-identity, which caches/refreshes


def test_missing_azure_identity_raises_clear_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "azure.identity", None)

    with pytest.raises(ImportError, match=r"Azure OpenAI Entra ID auth requires the 'azure-identity' package"):
        build_entra_token_provider(label="Azure OpenAI", endpoint="https://res.openai.azure.com/")


def test_redaction_filter_masks_credential_headers(caplog):
    logger_name = "tests.azure_entra.sdk"
    redact_auth_headers_in_logs(logger_name)
    redact_auth_headers_in_logs(logger_name)  # idempotent
    sdk_logger = logging.getLogger(logger_name)
    assert len(sdk_logger.filters) == 1

    options = {
        "method": "post",
        "url": "/v1/messages",
        "headers": {"Authorization": f"Bearer {SECRET}", "x-api-key": SECRET, "api-key": SECRET, "x-other": "kept"},
    }
    with caplog.at_level(logging.DEBUG, logger=logger_name):
        sdk_logger.debug("Request options: %s", options)

    assert SECRET not in caplog.text
    assert "<redacted>" in caplog.text
    assert "kept" in caplog.text
    assert options["headers"]["Authorization"] == f"Bearer {SECRET}"  # the request itself is untouched
