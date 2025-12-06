"""Helper functions for HTTP transport injection in tests."""

from tests.http_transport_recorder import TransportFactory


def inject_transport(monkeypatch, cassette_path: str):
    """Inject HTTP transport into OpenAI providers for testing.

    This helper simplifies the monkey patching pattern used across tests
    to inject custom HTTP transports for recording/replaying API calls.

    Supports both Chat Completions API (OpenAICompatibleProvider) and
    Responses API (OpenAIResponsesProvider). The cassette path should be
    dynamically selected based on model configuration using get_cassette_for_model().

    Also ensures OpenAI provider is properly registered for tests that need it.

    Args:
        monkeypatch: pytest monkeypatch fixture
        cassette_path: Path to cassette file for recording/replay
                      (e.g., "chat.json" for Chat API or "chat_responses.json" for Responses API)

    Returns:
        The created transport instance

    Example:
        # Dynamic cassette selection based on model config
        cassette = get_cassette_for_model("chat_gpt5", "gpt-5")
        transport = inject_transport(monkeypatch, cassette)
    """
    # Ensure OpenAI provider is registered - always needed for transport injection
    from providers.openai import OpenAIModelProvider
    from providers.openai_compatible import OpenAICompatibleProvider
    from providers.openai_responses import OpenAIResponsesProvider
    from providers.registry import ModelProviderRegistry
    from providers.shared import ProviderType

    # Always register OpenAI provider for transport tests (API key might be dummy)
    ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

    # Create transport for the specified cassette path
    transport = TransportFactory.create_transport(str(cassette_path))

    # Helper to patch a provider class's client property
    def _patch_client(provider_class):
        original_client_property = provider_class.client

        def patched_client_getter(self):
            if self._client is None:
                self._test_transport = transport
            return original_client_property.fget(self)

        monkeypatch.setattr(provider_class, "client", property(patched_client_getter))

    # Inject transport into both Chat API and Responses API providers
    # Model configuration determines which provider actually gets used
    _patch_client(OpenAICompatibleProvider)
    _patch_client(OpenAIResponsesProvider)

    return transport
