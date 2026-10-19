"""Unit tests for the native Anthropic (Claude) provider."""

import dataclasses
import importlib
import logging
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from providers.anthropic import AnthropicModelProvider
from providers.shared import ProviderType
from tools.models import ToolModelCategory


def _provider():
    return AnthropicModelProvider("test-key")


class TestAnthropicCatalog:
    def test_provider_type(self):
        assert _provider().get_provider_type() == ProviderType.ANTHROPIC

    def test_models_and_scores(self):
        caps = _provider().get_all_model_capabilities()
        assert caps["claude-opus-5-5"].intelligence_score == 20
        assert caps["claude-opus-5"].intelligence_score == 18
        assert caps["claude-fable-5"].intelligence_score == 18
        assert caps["claude-fable-5-1"].intelligence_score == 19
        assert caps["claude-sonnet-5-5"].intelligence_score == 18
        assert caps["claude-sonnet-5"].intelligence_score == 14
        assert caps["claude-haiku-4-5-20251001"].intelligence_score == 10
        assert caps["claude-opus-5"].context_window == 1_000_000
        assert caps["claude-opus-5"].supports_extended_thinking
        assert caps["claude-opus-5"].allow_code_generation

    def test_alias_resolution(self):
        p = _provider()
        # Bare "opus" points at the newest Opus (5.5); "opus-5" still addresses Opus 5.
        assert p._resolve_model_name("opus") == "claude-opus-5-5"
        assert p._resolve_model_name("opus-5.5") == "claude-opus-5-5"
        assert p._resolve_model_name("opus-5") == "claude-opus-5"
        # Bare "fable" now points at the newest Fable (5.1); "fable-5" still addresses Fable 5.
        assert p._resolve_model_name("fable") == "claude-fable-5-1"
        assert p._resolve_model_name("fable-5.1") == "claude-fable-5-1"
        assert p._resolve_model_name("fable-5") == "claude-fable-5"
        # Bare "sonnet" points at the newest Sonnet (5.5); "sonnet-5" still addresses Sonnet 5.
        assert p._resolve_model_name("sonnet") == "claude-sonnet-5-5"
        assert p._resolve_model_name("sonnet-5") == "claude-sonnet-5"
        # Bare "haiku" points at the newest Haiku (5.5); "haiku-4.5" still addresses Haiku 4.5.
        assert p._resolve_model_name("haiku") == "claude-haiku-5-5"
        assert p._resolve_model_name("haiku-4.5") == "claude-haiku-4-5-20251001"
        assert p._resolve_model_name("claude-haiku-4.5") == "claude-haiku-4-5-20251001"
        # Case-insensitive
        assert p._resolve_model_name("OPUS") == "claude-opus-5-5"

    def test_preferred_model_by_category(self):
        p = _provider()
        allowed = list(p.get_all_model_capabilities())
        # Opus 5.5 (AA 58), Sonnet 5.5 (AA 56) and Fable 5.1 (AA 53) all sit at 20, the top of the 1-20
        # scale. The raw aa_index orders the tie, so Opus 5.5 wins on its Index value; without it, the
        # name tie-break would pick Sonnet 5.5.
        assert p.get_preferred_model(ToolModelCategory.EXTENDED_REASONING, allowed) == "claude-opus-5-5"
        assert p.get_preferred_model(ToolModelCategory.BALANCED, allowed) == "claude-opus-5-5"
        assert p.get_preferred_model(ToolModelCategory.FAST_RESPONSE, allowed) == "claude-haiku-5-5"

    def test_score_orders_the_top_models(self):
        # At the high-effort anchor the top Claude models no longer tie: Opus 5.5 (AA 54) 20,
        # Fable 5.1 (51) 19, Sonnet 5.5 (47) 18.
        p = _provider()
        top = ["claude-fable-5-1", "claude-sonnet-5-5", "claude-opus-5-5"]
        assert p.get_preferred_model(ToolModelCategory.BALANCED, top) == "claude-opus-5-5"
        assert p.get_preferred_model(ToolModelCategory.BALANCED, top[:2]) == "claude-fable-5-1"

    def test_aa_index_orders_a_score_tie(self, monkeypatch):
        # Force a tie in which the name order and the AA order disagree: by name, haiku sorts after
        # fable, but Fable 5.1 has the higher aa_index (51 vs 38), so it must win.
        p = _provider()
        caps = dict(p.get_all_model_capabilities())
        for name in ("claude-fable-5-1", "claude-haiku-5-5"):
            caps[name] = dataclasses.replace(caps[name], intelligence_score=19)
        monkeypatch.setattr(p, "get_all_model_capabilities", lambda: caps)
        assert p.get_preferred_model(ToolModelCategory.BALANCED, ["claude-haiku-5-5", "claude-fable-5-1"]) == (
            "claude-fable-5-1"
        )

    def test_preferred_model_handles_unknown_allowed(self):
        # allowed_models with no canonical entries must not raise (regression: KeyError on
        # capability_map[m] in the EXTENDED_REASONING filter). It falls through to a best-effort
        # return like the sibling gemini provider — the point is that it does not crash.
        p = _provider()
        result = p.get_preferred_model(ToolModelCategory.EXTENDED_REASONING, ["nonexistent-model"])
        assert result == "nonexistent-model"


def _fake_response(text="hello", input_tokens=10, output_tokens=5):
    block = SimpleNamespace(type="text", text=text)
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(content=[block], usage=usage, stop_reason="end_turn")


class TestAnthropicGenerateContent:
    def _provider_with_mock(self):
        # Requests are streamed (messages.stream(...) as a context manager, then get_final_message()).
        p = _provider()
        mock_client = MagicMock()
        stream = mock_client.messages.stream.return_value.__enter__.return_value
        stream.get_final_message.return_value = _fake_response()
        p._client = mock_client
        return p, mock_client

    @staticmethod
    def _sent(client):
        return client.messages.stream.call_args.kwargs

    def test_current_model_uses_adaptive_thinking_and_effort(self):
        p, client = self._provider_with_mock()
        resp = p.generate_content(
            prompt="hi", model_name="opus", system_prompt="sys", temperature=0.2, thinking_mode="high"
        )
        assert resp.content == "hello"
        assert resp.usage["total_tokens"] == 15
        assert resp.provider == ProviderType.ANTHROPIC
        assert resp.metadata["reasoning_effort"] == "high"
        kwargs = self._sent(client)
        assert kwargs["model"] == "claude-opus-5-5"
        assert kwargs["system"] == "sys"
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert kwargs["extra_body"] == {"output_config": {"effort": "high"}}
        # Current models reject sampling parameters and fixed thinking budgets with HTTP 400.
        assert "temperature" not in kwargs
        assert "temperature" not in kwargs["extra_body"]
        assert "budget_tokens" not in kwargs["thinking"]
        assert kwargs["max_tokens"] == 128000
        client.messages.create.assert_not_called()

    def test_effort_is_clamped_to_the_model_levels(self):
        p, client = self._provider_with_mock()
        p.generate_content(prompt="hi", model_name="sonnet", thinking_mode="minimal")
        assert self._sent(client)["extra_body"]["output_config"] == {"effort": "low"}
        p.generate_content(prompt="hi", model_name="sonnet", thinking_mode="max")
        assert self._sent(client)["extra_body"]["output_config"] == {"effort": "max"}
        p.generate_content(prompt="hi", model_name="sonnet", thinking_mode=None)
        assert self._sent(client)["extra_body"]["output_config"] == {"effort": "medium"}

    def test_haiku_keeps_the_budget_path(self):
        p, client = self._provider_with_mock()
        resp = p.generate_content(prompt="hi", model_name="haiku-4.5", temperature=0.2, thinking_mode="high")
        kwargs = self._sent(client)
        assert resp.metadata["reasoning_effort"] is None
        assert "output_config" not in kwargs["extra_body"]
        # Thinking on -> temperature forced to 1.0, budget >= Anthropic floor. Temperature rides in
        # extra_body: the 1.x SDK rejects it as a keyword argument.
        assert "temperature" not in kwargs
        assert kwargs["extra_body"]["temperature"] == 1.0
        assert kwargs["thinking"]["type"] == "enabled"
        assert kwargs["thinking"]["budget_tokens"] >= 1024
        assert kwargs["thinking"]["budget_tokens"] < kwargs["max_tokens"]

    def test_haiku_minimal_thinking_disables_reasoning(self):
        p, client = self._provider_with_mock()
        p.generate_content(prompt="hi", model_name="haiku-4.5", temperature=0.3, thinking_mode="minimal")
        kwargs = self._sent(client)
        # Minimal maps below Anthropic's floor -> no thinking, caller temperature preserved
        assert "thinking" not in kwargs
        assert kwargs["extra_body"] == {"temperature": 0.3}
        assert kwargs["max_tokens"] == 64000  # haiku's advertised ceiling

    def test_foundry_deployment_names_resolve_and_pick_their_thinking_path(self):
        # Foundry deployment names equal the model IDs, so the canonical name is what PAL sends.
        p, client = self._provider_with_mock()
        p.generate_content(prompt="hi", model_name="claude-opus-4-8", thinking_mode="high")
        kwargs = self._sent(client)
        assert kwargs["model"] == "claude-opus-4-8"
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert kwargs["extra_body"] == {"output_config": {"effort": "high"}}

        # Sonnet 4.5 predates effort: budget thinking, temperature allowed.
        p.generate_content(prompt="hi", model_name="claude-sonnet-4-5", temperature=0.4, thinking_mode="minimal")
        kwargs = self._sent(client)
        assert kwargs["model"] == "claude-sonnet-4-5"
        assert "thinking" not in kwargs
        assert kwargs["extra_body"] == {"temperature": 0.4}
        assert kwargs["max_tokens"] == 64000

    def test_haiku_thinking_budget_preserves_output_headroom(self):
        # A caller asking for a small visible output while requesting high thinking must still get
        # its output room on top of the thinking budget (Anthropic counts thinking against max_tokens).
        p, client = self._provider_with_mock()
        p.generate_content(prompt="hi", model_name="haiku-4.5", max_output_tokens=2000, thinking_mode="high")
        kwargs = self._sent(client)
        budget = kwargs["thinking"]["budget_tokens"]
        assert kwargs["max_tokens"] - budget >= 2000


# ---------------------------------------------------------------------------
# Claude on Azure AI Foundry with Entra ID auth (ANTHROPIC_USE_ENTRA)
# ---------------------------------------------------------------------------

FOUNDRY_URL = "https://example-resource.services.ai.azure.com/anthropic"


def _fake_token_provider():
    return "fake-entra-token"


class TestAnthropicFoundryEntra:
    def test_entra_mode_builds_foundry_client_without_api_key(self, monkeypatch):
        import anthropic

        built, captured = {}, {}

        def fake_build(**kwargs):
            built.update(kwargs)
            return _fake_token_provider

        class FakeFoundry:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr("providers.anthropic.build_entra_token_provider", fake_build)
        monkeypatch.setattr(anthropic, "AnthropicFoundry", FakeFoundry)

        p = AnthropicModelProvider("", use_entra=True, foundry_base_url=FOUNDRY_URL)

        assert isinstance(p.client, FakeFoundry)
        assert captured == {"base_url": FOUNDRY_URL, "azure_ad_token_provider": _fake_token_provider}
        assert built == {"label": "Anthropic (Azure AI Foundry)", "endpoint": FOUNDRY_URL}

    def test_entra_settings_read_from_env(self, monkeypatch):
        import anthropic

        captured = {}

        class FakeFoundry:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setenv("ANTHROPIC_USE_ENTRA", "true")
        monkeypatch.setenv("ANTHROPIC_FOUNDRY_BASE_URL", FOUNDRY_URL)
        monkeypatch.setattr("providers.anthropic.build_entra_token_provider", lambda **_: _fake_token_provider)
        monkeypatch.setattr(anthropic, "AnthropicFoundry", FakeFoundry)

        _ = AnthropicModelProvider("").client

        assert captured["base_url"] == FOUNDRY_URL
        assert captured["azure_ad_token_provider"] is _fake_token_provider

    def test_entra_mode_requires_foundry_base_url(self):
        with pytest.raises(ValueError, match="ANTHROPIC_FOUNDRY_BASE_URL"):
            AnthropicModelProvider("", use_entra=True)

    def test_key_mode_is_unchanged_when_flag_off(self, monkeypatch):
        import anthropic

        captured = {}

        class FakeAnthropic:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        def fail_build(**_):
            raise AssertionError("Entra token provider must not be built in key mode")

        monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
        monkeypatch.setattr("providers.anthropic.build_entra_token_provider", fail_build)

        _ = _provider().client

        assert captured == {"api_key": "test-key"}

    def test_entra_mode_without_azure_identity_raises_clear_error(self, monkeypatch):
        # A None entry in sys.modules makes `from azure.identity import ...` raise ImportError.
        monkeypatch.setitem(sys.modules, "azure.identity", None)
        p = AnthropicModelProvider("", use_entra=True, foundry_base_url=FOUNDRY_URL)

        with pytest.raises(ImportError, match="azure-identity"):
            _ = p.client

    def test_entra_mode_with_sdk_lacking_foundry_raises_clear_error(self, monkeypatch):
        import anthropic

        monkeypatch.delattr(anthropic, "AnthropicFoundry", raising=False)
        p = AnthropicModelProvider("", use_entra=True, foundry_base_url=FOUNDRY_URL)

        with pytest.raises(ImportError, match=r"anthropic>=0\.74\.0"):
            _ = p.client

    def test_foundry_bearer_token_is_sent_but_never_logged(self, monkeypatch, caplog):
        # End to end through the real AnthropicFoundry client, with a mock transport instead of the network.
        # The SDK logs each request's headers at DEBUG, and Foundry puts the bearer token there.
        token = "entra-secret-token-0123456789"
        monkeypatch.setattr("providers.anthropic.build_entra_token_provider", lambda **_: (lambda: token))
        p = AnthropicModelProvider("", use_entra=True, foundry_base_url=FOUNDRY_URL)
        client = p.client

        # The SDK's HTTP client subclasses httpx2.Client on anthropic 1.x and httpx.Client on 0.x.
        http_lib = importlib.import_module(
            next(
                cls.__module__.split(".")[0]
                for cls in type(client._client).__mro__
                if cls.__module__.split(".")[0] in ("httpx2", "httpx")
            )
        )
        sent = {}

        def handler(request):
            sent["authorization"] = request.headers.get("authorization")
            sent["url"] = str(request.url)
            return http_lib.Response(
                200,
                json={
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-opus-5",
                    "content": [{"type": "text", "text": "OK"}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            )

        client._client = http_lib.Client(transport=http_lib.MockTransport(handler))

        with caplog.at_level(logging.DEBUG, logger="anthropic"):
            client.messages.create(model="claude-opus-5", max_tokens=5, messages=[{"role": "user", "content": "hi"}])

        assert sent["authorization"] == f"Bearer {token}"
        assert sent["url"] == f"{FOUNDRY_URL}/v1/messages"
        assert "Request options" in caplog.text  # the SDK did log the request headers...
        assert token not in caplog.text  # ...with the token redacted
