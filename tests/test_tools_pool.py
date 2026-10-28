"""Phase 6: multi tool-capable model pool -- capability/availability/refusal/
rate/context/blocklist filtering, primary/fallback env overrides, role
assignment. Qwen must not be the sole/privileged tool_executor."""

from __future__ import annotations

import pytest

from providers.router import tools_pool


def _avail(*names):
    s = set(names)
    return lambda m: m in s


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in (
        "PAL_TOOLS_MODELS",
        "PAL_TOOLS_PRIMARY_MODEL",
        "PAL_TOOLS_FALLBACK_MODELS",
        "PAL_TOOLS_BLOCKLIST",
        "PAL_CHAT_TOOLS_MODEL",
    ):
        monkeypatch.delenv(k, raising=False)
    yield


def test_tool_executor_requires_known_tool_format():
    avail = _avail("qwen3", "gpt-oss-120b", "some-untooled-model")
    pool = tools_pool.select_pool("tool_executor", "", is_available=avail)
    assert "some-untooled-model" not in pool
    assert set(pool) <= {"qwen3", "gpt-oss-120b"}


def test_qwen_not_sole_or_privileged():
    """Multiple tool-format-capable models available -> pool has more than
    just qwen3, and qwen3 need not be first (bandit/order can demote it)."""
    avail = _avail("qwen3", "gpt-oss-120b", "gpt-oss-20b")
    pool = tools_pool.select_pool("tool_executor", "", is_available=avail)
    assert len(pool) > 1
    assert "gpt-oss-120b" in pool and "gpt-oss-20b" in pool


def test_primary_model_env_overrides_order(monkeypatch):
    monkeypatch.setenv("PAL_TOOLS_PRIMARY_MODEL", "gpt-oss-120b")
    avail = _avail("qwen3", "gpt-oss-120b")
    pool = tools_pool.select_pool("tool_executor", "", is_available=avail)
    assert pool[0] == "gpt-oss-120b"


def test_legacy_chat_tools_model_env_still_works(monkeypatch):
    monkeypatch.setenv("PAL_CHAT_TOOLS_MODEL", "gpt-oss-120b")
    avail = _avail("qwen3", "gpt-oss-120b")
    pool = tools_pool.select_pool("tool_executor", "", is_available=avail)
    assert pool[0] == "gpt-oss-120b"


def test_blocklist_removes_model(monkeypatch):
    monkeypatch.setenv("PAL_TOOLS_BLOCKLIST", "qwen3")
    avail = _avail("qwen3", "gpt-oss-120b")
    pool = tools_pool.select_pool("tool_executor", "", is_available=avail)
    assert "qwen3" not in pool
    assert pool == ["gpt-oss-120b"]


def test_explicit_pool_and_fallback_models(monkeypatch):
    monkeypatch.setenv("PAL_TOOLS_MODELS", "gemini-3.6-flash,qwen3")
    monkeypatch.setenv("PAL_TOOLS_FALLBACK_MODELS", "gpt-oss-120b")
    avail = _avail("gemini-3.6-flash", "qwen3", "gpt-oss-120b")
    pool = tools_pool.select_pool("tool_executor", "", is_available=avail)
    assert pool == ["gemini-3.6-flash", "qwen3", "gpt-oss-120b"]


def test_unavailable_model_dropped():
    avail = _avail("qwen3")  # gpt-oss-120b not "available"
    pool = tools_pool.select_pool("tool_executor", "", is_available=avail)
    assert pool == ["qwen3"]


def test_role_without_tool_format_requirement_is_looser(monkeypatch):
    """reviewer/reasoner/fallback don't require a known tool-call format --
    a plain-text model only reaches the candidate list via PAL_TOOLS_MODELS
    (the pool is curated, not "any available model")."""
    monkeypatch.setenv("PAL_TOOLS_MODELS", "some-plain-text-model")
    avail = _avail("some-plain-text-model")
    pool = tools_pool.select_pool("fallback", "", is_available=avail)
    assert pool == ["some-plain-text-model"]


def test_empty_role_pool_widens_to_fallback(monkeypatch):
    monkeypatch.setenv("PAL_TOOLS_MODELS", "some-plain-text-model")
    avail = _avail("some-plain-text-model")  # not tool-format-capable
    assert tools_pool.select_pool("reviewer", "", is_available=avail) == ["some-plain-text-model"]


def test_tool_executor_never_widens_to_incompatible_format(monkeypatch):
    monkeypatch.setenv("PAL_TOOLS_MODELS", "some-plain-text-model")
    avail = _avail("some-plain-text-model")
    assert tools_pool.select_pool("tool_executor", "", is_available=avail) == []


def test_incompatible_declared_format_is_filtered(monkeypatch):
    monkeypatch.setenv("PAL_TOOLS_MODELS", "qwen3,xml-only-model,mystery-model,hermes-ok")
    monkeypatch.setenv("PAL_TOOLS_FORMATS", "xml-only-model=anthropic_xml,hermes-ok=hermes")
    avail = _avail("qwen3", "xml-only-model", "mystery-model", "hermes-ok")
    pool = tools_pool.select_pool("tool_executor", "", is_available=avail)
    assert "xml-only-model" not in pool  # declared, but react.py can't parse it
    assert "mystery-model" not in pool  # unknown format
    assert set(pool) == {"qwen3", "hermes-ok"}
    assert tools_pool.declared_tool_format("qwen3") == "hermes"


def test_catalog_tools_true_without_format_is_not_enough(monkeypatch):
    from types import SimpleNamespace

    entry = SimpleNamespace(model="cat-model", aliases=[], tools=True)
    monkeypatch.setattr("providers.router.catalog.routing_catalog", lambda: SimpleNamespace(entries=[entry]))
    assert not tools_pool.is_tool_format_capable("cat-model")
    entry.tool_format = "openai"
    assert tools_pool.is_tool_format_capable("cat-model")


def test_assign_roles_labels_pool():
    labels = tools_pool.assign_roles(["m1", "m2", "m3", "m4", "m5"])
    assert labels == {
        "tool_executor": "m1",
        "reviewer": "m2",
        "reasoner": "m3",
        "fallback": "m4",
    }


def test_pick_returns_first_of_pool(monkeypatch):
    monkeypatch.setenv("PAL_TOOLS_PRIMARY_MODEL", "gpt-oss-120b")
    avail = _avail("qwen3", "gpt-oss-120b")
    assert tools_pool.pick("tool_executor", "", is_available=avail) == "gpt-oss-120b"


def test_no_available_models_returns_empty():
    avail = _avail()  # nothing available
    assert tools_pool.select_pool("tool_executor", "", is_available=avail) == []
