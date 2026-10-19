"""Microsoft Entra ID (Azure AD) bearer-token auth shared by the Azure-hosted providers.

Azure OpenAI (``AZURE_OPENAI_USE_ENTRA``) and Claude on Azure AI Foundry (``ANTHROPIC_USE_ENTRA``) can
authenticate with the caller's Entra identity instead of a static API key. ``DefaultAzureCredential``
resolves that identity (``az login``, a managed identity, workload identity, ...); set
``AZURE_TOKEN_CREDENTIALS=AzureCliCredential`` to pin it to the Azure CLI login.

``azure-identity`` is imported lazily, so PAL starts without it while Entra mode is off. Tokens are never
logged: the provider logs only the credential type that produced the first token and the endpoint host.
"""

from __future__ import annotations

import logging
from typing import Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Data-plane scope for Azure OpenAI and the Foundry-hosted Anthropic endpoint.
COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"

# Request headers that carry credentials. Matched case-insensitively.
_SENSITIVE_HEADERS = frozenset({"authorization", "api-key", "x-api-key"})


def build_entra_token_provider(
    *,
    label: str,
    endpoint: str,
    scope: str = COGNITIVE_SERVICES_SCOPE,
) -> Callable[[], str]:
    """Return a callable that yields a current Entra bearer token for ``scope``.

    The callable caches the token and refreshes it before it expires (``azure-identity`` handles both).

    Args:
        label: Provider name used in log lines and errors, e.g. "Azure OpenAI".
        endpoint: Endpoint the tokens are for. Only its host is logged.
        scope: OAuth scope to request.

    Raises:
        ImportError: ``azure-identity`` is not installed.
    """
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    except ImportError as exc:
        raise ImportError(
            f"{label} Entra ID auth requires the 'azure-identity' package. "
            "Install it with `pip install azure-identity`, or turn Entra mode off."
        ) from exc

    credential = DefaultAzureCredential()
    fetch_token = get_bearer_token_provider(credential, scope)
    host = urlparse(endpoint).hostname or endpoint
    reported = False

    def token_provider() -> str:
        nonlocal reported
        token = fetch_token()
        if not reported:
            # DefaultAzureCredential records which credential in its chain produced the token.
            source = getattr(credential, "_successful_credential", None)
            source_name = type(source).__name__ if source is not None else type(credential).__name__
            logger.info("%s: Entra ID token acquired via %s for %s", label, source_name, host)
            reported = True
        return token

    return token_provider


class _RedactAuthHeadersFilter(logging.Filter):
    """Replace credential headers in an SDK "Request options" debug record with ``<redacted>``."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, dict) and isinstance(args.get("headers"), dict):
            headers = {**args["headers"]}
            for name in headers:
                if str(name).lower() in _SENSITIVE_HEADERS:
                    headers[name] = "<redacted>"
            record.args = {**args, "headers": headers}
        return True


def redact_auth_headers_in_logs(logger_name: str) -> None:
    """Attach the redaction filter to ``logger_name`` once.

    The anthropic SDK logs each request's options, headers included, at DEBUG. Foundry puts the Entra
    bearer token in those headers, and PAL logs at DEBUG by default, so without this filter the token
    would reach logs/mcp_server.log. The openai SDK already redacts these headers itself.
    """
    target = logging.getLogger(logger_name)
    if not any(isinstance(existing, _RedactAuthHeadersFilter) for existing in target.filters):
        target.addFilter(_RedactAuthHeadersFilter())
