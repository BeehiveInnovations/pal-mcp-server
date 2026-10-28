"""Tests for providers.router.key_pool multi-key rotation."""

import json

import pytest

from providers.router import key_pool


@pytest.fixture
def two_key_pool(tmp_path, monkeypatch):
    kf = tmp_path / "keys.json"
    kf.write_text(
        json.dumps(
            {
                "groq": {"keys": ["gsk_AAAAAAAAAAAAAAAA", "gsk_BBBBBBBBBBBBBBBB"]},
                "openrouter": ["sk-or-ONEONEONEONEONE", "sk-or-TWOTWOTWOTWOTWO"],
            }
        )
    )
    monkeypatch.setenv("PAL_KEYS_FILE", str(kf))
    monkeypatch.setenv("PAL_KEY_ROTATE", "1")
    monkeypatch.setenv("PAL_KEY_COOLDOWN", "60")
    key_pool._reset()
    yield
    key_pool._reset()


def test_keys_for_and_current(two_key_pool):
    assert key_pool.keys_for("groq") == ["gsk_AAAAAAAAAAAAAAAA", "gsk_BBBBBBBBBBBBBBBB"]
    assert key_pool.current("groq") == "gsk_AAAAAAAAAAAAAAAA"


def test_unknown_provider_is_empty(two_key_pool):
    assert key_pool.keys_for("does-not-exist") == []
    assert key_pool.current("does-not-exist") is None


def test_rotate_returns_second_and_cools_first(two_key_pool):
    first = key_pool.current("groq")
    nxt = key_pool.rotate("groq", first, "429")
    assert nxt == "gsk_BBBBBBBBBBBBBBBB"
    # first key is now cooling, so current() skips it
    assert key_pool.current("groq") == "gsk_BBBBBBBBBBBBBBBB"


def test_cooldown_expiry_readmits(two_key_pool, monkeypatch):
    first = key_pool.current("groq")
    key_pool.rotate("groq", first, "429")
    assert first[:16] in key_pool._cool
    # expire the cooldown
    key_pool._cool[first[:16]] = 0.0
    healthy = key_pool._healthy("groq")
    assert first in healthy


def test_mark_ok_clears_cooldown(two_key_pool):
    first = key_pool.current("groq")
    key_pool.rotate("groq", first, "429")
    key_pool.mark_ok("groq", first)
    assert first[:16] not in key_pool._cool


def test_rate_error_classification():
    assert key_pool.is_rate_or_credit_error("Error code: 429 rate_limit_exceeded")
    assert key_pool.is_rate_or_credit_error("402 insufficient credit")
    assert key_pool.is_rate_or_credit_error("output tokens per minute (OTPM)")
    assert not key_pool.is_rate_or_credit_error("model produced invalid JSON")


def test_name_for_type_maps_custom_groq(monkeypatch):
    monkeypatch.setenv("CUSTOM_API_URL", "https://api.groq.com/openai/v1")
    assert key_pool.name_for_type("custom") == "groq"
    assert key_pool.name_for_type("openrouter") == "openrouter"
    assert key_pool.name_for_type("google") == "gemini"


def test_disabled_when_flag_off(tmp_path, monkeypatch):
    monkeypatch.setenv("PAL_KEY_ROTATE", "0")
    assert key_pool.is_enabled() is False


def test_missing_file_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("PAL_KEYS_FILE", str(tmp_path / "nope.json"))
    key_pool._reset()
    assert key_pool.keys_for("groq") == []
    assert key_pool.stats() == {}


def test_stats_never_contains_key_values(two_key_pool):
    st = key_pool.stats()
    assert st["groq"]["keys"] == 2
    blob = json.dumps(st)
    assert "gsk_" not in blob and "sk-or" not in blob
