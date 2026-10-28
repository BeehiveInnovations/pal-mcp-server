"""Unit tests for providers/router/fallback_chain.py."""

from __future__ import annotations

import json

import pytest

from providers.router import fallback_chain as fc


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch, tmp_path):
    """Fresh env.json + cleared category cache per test."""
    env_file = tmp_path / "env.json"
    env_file.write_text(
        json.dumps(
            {
                "categories": {
                    "long_context_bulk": ["nemotron", "or-free", "gemini-3.6-flash"],
                    "security_permissive": ["grok-4-fast", "or-free", "gemini-3-pro-preview"],
                    "long_form_prose": ["gpt-oss-120b", "openai/gpt-oss-120b"],
                }
            }
        )
    )
    monkeypatch.setenv("PAL_ENV_JSON", str(env_file))
    monkeypatch.setenv("PAL_FALLBACK", "1")
    monkeypatch.delenv("PAL_FALLBACK_MAX", raising=False)
    fc.reset_cache()
    yield
    fc.reset_cache()


# ----- should_fallback --------------------------------------------------------
@pytest.mark.parametrize("code", [402, 413, 429, 503])
def test_should_fallback_on_trigger_codes(code):
    assert fc.should_fallback(code, "") is True


def test_should_fallback_ignores_ok_codes():
    assert fc.should_fallback(200, "hello") is False
    assert fc.should_fallback(None, "hello") is False


@pytest.mark.parametrize(
    "text",
    [
        "Response blocked or incomplete. Finish reason: Unknown",
        "content_filter triggered",
        "safety block on request",
        "response was blocked by policy",
    ],
)
def test_should_fallback_on_silent_block_markers(text):
    assert fc.should_fallback(None, text) is True


# ----- chain_for --------------------------------------------------------------
def test_chain_for_returns_rotated_peers():
    chain = fc.chain_for("nemotron")
    assert chain == ["or-free", "gemini-3.6-flash"]


def test_chain_for_empty_when_uncategorized():
    assert fc.chain_for("some/random-model") == []


def test_category_for_maps_correctly():
    assert fc.category_for("grok-4-fast") == "security_permissive"
    assert fc.category_for("gpt-oss-120b") == "long_form_prose"
    assert fc.category_for("ghost-model") is None


# ----- call_with_fallback -----------------------------------------------------
def test_first_model_succeeds_no_fallback():
    calls: list[str] = []

    def call(m: str):
        calls.append(m)
        return "ok"

    assert fc.call_with_fallback(call, "nemotron") == "ok"
    assert calls == ["nemotron"]


def test_413_triggers_fallback_to_next_peer():
    calls: list[str] = []

    class HTTPError(Exception):
        pass

    def call(m: str):
        calls.append(m)
        if m == "nemotron":
            raise HTTPError("Error code: 413 — request too large")
        return f"served by {m}"

    result = fc.call_with_fallback(call, "nemotron")
    assert result == "served by or-free"
    assert calls == ["nemotron", "or-free"]


def test_silent_block_in_result_triggers_fallback():
    calls: list[str] = []

    def call(m: str):
        calls.append(m)
        if m == "nemotron":
            return "Response blocked or incomplete. Finish reason: Unknown"
        return "clean answer"

    result = fc.call_with_fallback(call, "nemotron")
    assert result == "clean answer"
    assert calls == ["nemotron", "or-free"]


def test_whole_chain_exhausted_raises_last_exception():
    class HTTPError(Exception):
        pass

    def call(m: str):
        raise HTTPError(f"429 rate limited on {m}")

    with pytest.raises(HTTPError) as exc_info:
        fc.call_with_fallback(call, "nemotron")
    assert "gemini-3.6-flash" in str(exc_info.value)


def test_non_trigger_exception_propagates_immediately():
    calls: list[str] = []

    class WeirdError(RuntimeError):
        pass

    def call(m: str):
        calls.append(m)
        raise WeirdError("some unrelated bug")

    with pytest.raises(WeirdError):
        fc.call_with_fallback(call, "nemotron")
    assert calls == ["nemotron"]  # did NOT try next model


def test_on_switch_callback_fires():
    events: list[tuple[str, str, str]] = []

    def call(m: str):
        if m == "nemotron":
            raise RuntimeError("413 too big")
        return "ok"

    fc.call_with_fallback(
        call,
        "nemotron",
        on_switch=lambda prev, nxt, reason: events.append((prev, nxt, reason)),
    )
    assert len(events) == 1
    assert events[0][0] == "nemotron"
    assert events[0][1] == "or-free"
    assert "413" in events[0][2]


def test_disabled_env_bypasses_fallback(monkeypatch):
    monkeypatch.setenv("PAL_FALLBACK", "0")
    calls: list[str] = []

    def call(m: str):
        calls.append(m)
        raise RuntimeError("413 nope")

    with pytest.raises(RuntimeError):
        fc.call_with_fallback(call, "nemotron")
    assert calls == ["nemotron"]  # no fallback attempted


def test_max_attempts_caps_chain(monkeypatch):
    monkeypatch.setenv("PAL_FALLBACK_MAX", "2")
    calls: list[str] = []

    def call(m: str):
        calls.append(m)
        raise RuntimeError("413")

    with pytest.raises(RuntimeError):
        fc.call_with_fallback(call, "nemotron")
    # capped at 2 attempts total (nemotron + or-free) even though chain has 3
    assert calls == ["nemotron", "or-free"]


def test_describe_chain_shows_full_attempt_list():
    assert list(fc.describe_chain("nemotron")) == ["nemotron", "or-free", "gemini-3.6-flash"]


def test_uncategorized_model_no_fallback_attempted():
    calls: list[str] = []

    def call(m: str):
        calls.append(m)
        raise RuntimeError("429")

    with pytest.raises(RuntimeError):
        fc.call_with_fallback(call, "some/random-model")
    assert calls == ["some/random-model"]  # no peers to try
