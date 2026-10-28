"""Unit tests for the pal-chat tier router and REPL helpers."""

from __future__ import annotations

import json

import pytest

from providers.router import chat_repl, chat_router

AVAIL = {"gpt-oss-20b", "gpt-oss-120b", "gemini-3.6-flash"}


def _av(m):
    return m in AVAIL


@pytest.mark.parametrize(
    "msg,tier",
    [
        ("hi", "cheap"),
        ("hey!!", "cheap"),
        ("thanks", "cheap"),
        ("how are you", "cheap"),
        ("what is 2+2", "cheap"),
        ("why does TCP slow start cause bufferbloat?", "smart"),
        ("write a python quicksort", "smart"),
        ("fix this sql query", "smart"),
        ("design an auth system", "smart"),
        ("test SSRF on this endpoint", "smart"),  # classifier category
        ("```def f(): pass```", "smart"),  # contains code
    ],
)
def test_tier_decisions(msg, tier):
    assert chat_router.route(msg, _av)["tier"] == tier


def test_cheap_and_smart_models_resolve():
    r = chat_router.route("hi", _av)
    assert r["cheap"] == "gpt-oss-20b"
    assert r["smart"] == "gpt-oss-120b"
    assert r["model"] == r["cheap"]


def test_smart_message_uses_smart_model():
    assert chat_router.route("why is the sky blue, explain", _av)["model"] == "gpt-oss-120b"


def test_env_override(monkeypatch):
    monkeypatch.setenv("PAL_CHAT_CHEAP_MODEL", "my-cheap")
    monkeypatch.setenv("PAL_CHAT_SMART_MODEL", "my-smart")
    r = chat_router.route("hi", lambda m: True)
    assert r["cheap"] == "my-cheap" and r["smart"] == "my-smart"


def test_no_models_available_returns_none():
    r = chat_router.route("hi", lambda m: False)
    assert r["model"] is None


def test_empty_prompt_is_cheap():
    assert chat_router.classify_difficulty("")[0] == "cheap"


# ----- REPL helpers ----------------------------------------------------------
class _Item:
    def __init__(self, text):
        self.text = text


def test_clean_strips_agent_boilerplate():
    raw = "Real answer here.\n\n---\nAGENT'S TURN: Evaluate this perspective..."
    assert chat_repl._clean(raw) == "Real answer here."


def test_clean_strips_continuation_note():
    raw = "The answer.\n**Please respond using the continuation_id from this response**"
    assert chat_repl._clean(raw) == "The answer."


def test_extract_plain_text():
    ans, cont = chat_repl._extract([_Item("just text")])
    assert ans == "just text"
    assert cont is None


def test_extract_json_envelope_and_continuation():
    payload = json.dumps({"content": "hello", "continuation_offer": {"continuation_id": "abc123"}})
    ans, cont = chat_repl._extract([_Item(payload)])
    assert ans == "hello"
    assert cont == "abc123"


def test_extract_cleans_boilerplate_in_content():
    payload = json.dumps({"content": "Answer.\nAGENT'S TURN: do stuff"})
    ans, _ = chat_repl._extract([_Item(payload)])
    assert ans == "Answer."


def test_extract_files_required_envelope_humanized():
    payload = json.dumps({
        "status": "files_required_to_continue",
        "mandatory_instructions": "I need src/auth/recon.js",
        "files_needed": ["src/auth/recon.js"],
    })
    ans, _ = chat_repl._extract([_Item(payload)])
    assert "wanted to see files" in ans
    assert "recon.js" in ans
    assert "files_required_to_continue" not in ans  # raw JSON not shown
