"""Tests for starting without an API provider when a CLI client is available.

clink shells out to CLIs that authenticate themselves, so a machine with one of
them installed needs no API key. Hosts that strip the environment before
launching MCP servers rely on this.
"""

import os
from unittest.mock import patch

import pytest

from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType

NO_API_KEYS = {
    "GEMINI_API_KEY": "",
    "GOOGLE_API_KEY": "",
    "OPENAI_API_KEY": "",
    "XAI_API_KEY": "",
    "DIAL_API_KEY": "",
    "OPENROUTER_API_KEY": "",
    "CUSTOM_API_URL": "",
    "AZURE_OPENAI_API_KEY": "",
}


class TestCLIOnlyMode:
    def setup_method(self):
        registry = ModelProviderRegistry()
        self._original_providers = registry._providers.copy()
        ModelProviderRegistry.clear_cache()
        for provider_type in ProviderType:
            ModelProviderRegistry.unregister_provider(provider_type)

    def teardown_method(self):
        registry = ModelProviderRegistry()
        ModelProviderRegistry.clear_cache()
        registry._providers.clear()
        registry._providers.update(self._original_providers)

    def test_starts_without_api_keys_when_a_cli_is_available(self):
        import server

        with patch.dict(os.environ, NO_API_KEYS, clear=True):
            with patch("server.available_cli_clients", return_value=["claude"]):
                with patch.object(server.logger, "warning") as warned:
                    server.configure_providers()

        # The server module configures its own handlers, so assert on the call
        # rather than through caplog.
        # The CLI names are joined into one argument, so match against the
        # rendered message rather than the argument list. Rendering is guarded
        # because unrelated warnings pass pre-formatted strings that may carry
        # a literal % and would otherwise raise here.
        def render(call):
            if len(call.args) > 1:
                try:
                    return str(call.args[0]) % tuple(call.args[1:])
                except (TypeError, ValueError):
                    pass
            return str(call.args[0]) if call.args else ""

        banners = [line for line in map(render, warned.call_args_list) if "CLI-only mode" in line]
        assert len(banners) == 1
        assert "claude" in banners[0]
        assert ModelProviderRegistry.get_available_providers() == []

    def test_cli_discovery_is_skipped_when_a_provider_exists(self):
        from server import configure_providers

        env = dict(NO_API_KEYS)
        env["GEMINI_API_KEY"] = "test-key"
        with patch.dict(os.environ, env, clear=True):
            with patch("server.available_cli_clients") as discover:
                configure_providers()
                discover.assert_not_called()

    def test_cli_discovery_is_skipped_in_strict_mode(self):
        from server import configure_providers

        env = dict(NO_API_KEYS)
        env["PAL_REQUIRE_API_PROVIDER"] = "true"
        with patch.dict(os.environ, env, clear=True):
            with patch("server.available_cli_clients") as discover:
                with pytest.raises(ValueError):
                    configure_providers()
                discover.assert_not_called()

    def test_raises_when_no_api_keys_and_no_cli(self):
        from server import configure_providers

        with patch.dict(os.environ, NO_API_KEYS, clear=True):
            with patch("server.available_cli_clients", return_value=[]):
                with pytest.raises(ValueError, match="At least one API configuration is required"):
                    configure_providers()

    def test_error_mentions_the_cli_only_alternative(self):
        from server import configure_providers

        with patch.dict(os.environ, NO_API_KEYS, clear=True):
            with patch("server.available_cli_clients", return_value=[]):
                with pytest.raises(ValueError, match="CLI-only mode"):
                    configure_providers()

    def test_require_api_provider_restores_strict_behaviour(self):
        from server import configure_providers

        env = dict(NO_API_KEYS)
        env["PAL_REQUIRE_API_PROVIDER"] = "true"
        with patch.dict(os.environ, env, clear=True):
            with patch("server.available_cli_clients", return_value=["claude"]):
                with pytest.raises(ValueError, match="At least one API configuration is required"):
                    configure_providers()

    @pytest.mark.parametrize("flag", ["true", "TRUE", "True"])
    def test_require_api_provider_is_case_insensitive(self, flag):
        from server import configure_providers

        env = dict(NO_API_KEYS)
        env["PAL_REQUIRE_API_PROVIDER"] = flag
        with patch.dict(os.environ, env, clear=True):
            with patch("server.available_cli_clients", return_value=["claude"]):
                with pytest.raises(ValueError, match="At least one API configuration is required"):
                    configure_providers()

    @pytest.mark.parametrize("flag", ["false", "0", "no", "off", ""])
    def test_require_api_provider_other_values_allow_cli_only(self, flag):
        """Matches utils.env.get_env_bool, which treats only "true" as true."""

        from server import configure_providers

        env = dict(NO_API_KEYS)
        env["PAL_REQUIRE_API_PROVIDER"] = flag
        with patch.dict(os.environ, env, clear=True):
            with patch("server.available_cli_clients", return_value=["claude"]):
                configure_providers()

    def test_api_key_still_takes_precedence(self):
        from server import configure_providers

        env = dict(NO_API_KEYS)
        env["GEMINI_API_KEY"] = "test-key"
        with patch.dict(os.environ, env, clear=True):
            with patch("server.available_cli_clients", return_value=[]):
                configure_providers()
                assert ProviderType.GOOGLE in ModelProviderRegistry.get_available_providers()


class TestContinuationWithoutProviders:
    """Follow-up turns must work when no model provider is configured.

    clink offers a continuation id after its first turn, so this is the normal
    path for a CLI-only install rather than an edge case. Thread reconstruction
    builds a token budget for history, which previously demanded a provider the
    tool never needed.
    """

    def setup_method(self):
        registry = ModelProviderRegistry()
        self._original_providers = registry._providers.copy()
        ModelProviderRegistry.clear_cache()
        for provider_type in ProviderType:
            ModelProviderRegistry.unregister_provider(provider_type)

    def teardown_method(self):
        registry = ModelProviderRegistry()
        ModelProviderRegistry.clear_cache()
        registry._providers.clear()
        registry._providers.update(self._original_providers)

    def test_provider_free_context_budgets_tokens(self):
        from utils.model_context import ModelContext

        context = ModelContext.for_tool_without_model()

        assert context.capabilities.context_window > 0
        assert context.calculate_token_allocation().total_tokens > 0

    @pytest.mark.asyncio
    async def test_clink_continuation_reconstructs_without_a_provider(self):
        from server import reconstruct_thread_context
        from utils.conversation_memory import add_turn, create_thread

        thread_id = create_thread("clink", {"prompt": "first turn"})
        add_turn(thread_id, "assistant", "first answer", tool_name="clink")

        arguments = await reconstruct_thread_context(
            {"continuation_id": thread_id, "prompt": "second turn", "cli_name": "agy"}
        )

        # A provider-free context is supplied rather than the continuation failing.
        assert arguments["_resolved_model_name"] == "cli-delegated"
        assert arguments["_model_context"].capabilities.provider == ProviderType.CUSTOM
        assert arguments["_model_context"].capabilities.context_window > 0
        assert "first answer" in arguments["prompt"]
