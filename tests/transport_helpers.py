"""Helper functions for HTTP transport injection in tests."""

from tests.http_transport_recorder import TransportFactory


def inject_transport(monkeypatch, cassette_path: str):
    """Inject HTTP transport into OpenAICompatibleProvider for testing.

    This helper simplifies the monkey patching pattern used across tests
    to inject custom HTTP transports for recording/replaying API calls.

    Also ensures OpenAI provider is properly registered for tests that need it.

    Args:
        monkeypatch: pytest monkeypatch fixture
        cassette_path: Path to cassette file for recording/replay

    Returns:
        The created transport instance

    Example:
        transport = inject_transport(monkeypatch, "path/to/cassette.json")
    """
    # Ensure OpenAI provider is registered - always needed for transport injection
    from providers.base import ProviderType
    from providers.openai_provider import OpenAIModelProvider
    from providers.registry import ModelProviderRegistry

    # Always register OpenAI provider for transport tests (API key might be dummy)
    ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

    # Create transport
    transport = TransportFactory.create_transport(str(cassette_path))

    # Inject transport using the established pattern
    from providers.openai_compatible import OpenAICompatibleProvider

    original_client_property = OpenAICompatibleProvider.client

    def patched_client_getter(self):
        if self._client is None:
            self._test_transport = transport
        return original_client_property.fget(self)

    monkeypatch.setattr(OpenAICompatibleProvider, "client", property(patched_client_getter))

    return transport
