"""Unit tests for providers/router/size_guard.py."""

from __future__ import annotations

from providers.router.size_guard import (
    MODEL_INPUT_CAPS,
    cap_for,
    check_or_reroute,
    guess_input_tokens,
)


def test_guess_tokens_prompt_only():
    assert guess_input_tokens("a" * 400) == 100


def test_guess_tokens_empty_prompt():
    assert guess_input_tokens("") == 0
    assert guess_input_tokens(None) == 0  # type: ignore[arg-type]


def test_cap_default_for_unknown():
    assert cap_for("some/unknown-model") == 100_000


def test_cap_known_alias():
    assert cap_for("groq") == 7500
    assert cap_for("nemotron") == 900_000


def test_check_or_reroute_fits():
    ok, hint = check_or_reroute("gpt-5-mini", "hi")
    assert ok is True and hint is None


def test_check_or_reroute_oversize_groq_routes_bigger():
    ok, hint = check_or_reroute("groq", "x" * (7500 * 4 + 100))
    assert ok is False
    assert hint and hint.startswith("route:")
    # groq is in long_form_prose; peer is gpt-oss-120b (same cap) so the
    # global fallback should surface nemotron
    assert "nemotron" in hint or "or-free" in hint


def test_check_or_reroute_oversize_unknown_hints_nemotron():
    ok, hint = check_or_reroute("some/random", "y" * (100_000 * 4 + 1000))
    assert ok is False
    assert hint == "route:nemotron"


def test_guess_tokens_missing_file_ok():
    assert guess_input_tokens("hi", ["/no/such/file"]) == 0


def test_caps_dict_has_common_models():
    for m in ("groq", "nemotron", "flash", "gpt-5-mini", "or-free"):
        assert m in MODEL_INPUT_CAPS
