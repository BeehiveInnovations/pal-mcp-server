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


def test_size_guard_sees_post_headroom_size(monkeypatch):
    from providers.router import outbound, size_guard

    nmap = "Starting Nmap 7.94\n" + "\n".join(f"{i}/tcp open svc{i}" for i in range(20000))
    msgs = [{"role": "tool", "content": nmap}]
    seen = {}
    real = size_guard.check_payload

    def spy(model, payload):
        seen["len"] = len(size_guard.payload_text(payload))
        return real(model, payload)

    monkeypatch.setattr(size_guard, "check_payload", spy)
    monkeypatch.setattr(size_guard, "cap_for", lambda m: 10**9)
    outbound.prepare(msgs, "m")[0]
    assert seen["len"] < len(nmap) // 2  # guard measured the compressed payload


def test_oversize_after_compression_raises_413(monkeypatch):
    import pytest

    from providers.router import outbound, size_guard

    prose = "word " * 10000
    monkeypatch.setattr(size_guard, "cap_for", lambda m: 100)
    with pytest.raises(size_guard.PayloadTooLarge) as ei:
        outbound.prepare([{"role": "user", "content": prose}], "m")
    assert ei.value.status_code == 413
