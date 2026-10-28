"""Tests for the capability-aware model catalog (Phase 5) and `pal models`."""

from __future__ import annotations

import json

import pytest

import cli
from providers.router import catalog, catalog_cli

ALL_KEYS = (
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "XAI_API_KEY",
    "OPENROUTER_API_KEY",
    "DIAL_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "CUSTOM_API_URL",
    "CUSTOM_API_KEY",
)


@pytest.fixture(autouse=True)
def _iso(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "CACHE_PATH", tmp_path / "model_catalog.json")
    monkeypatch.setattr("providers.router.quota_probe.STATS_PATH", tmp_path / "stats.jsonl")
    monkeypatch.delenv("PAL_CATALOG_ROUTING", raising=False)
    for k in ALL_KEYS:
        monkeypatch.setenv(k, "")
    catalog.reset_memo()
    yield
    catalog.reset_memo()


def _groq(monkeypatch):
    monkeypatch.setenv("CUSTOM_API_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("CUSTOM_API_KEY", "gsk_test_secret")


class Fetcher:
    def __init__(self, ids=("openai/gpt-oss-120b", "openai/gpt-oss-20b", "whisper-large-v3"), fail=False):
        self.ids, self.fail, self.calls, self.headers = list(ids), fail, 0, []

    def __call__(self, url, headers):
        self.calls += 1
        self.headers.append(headers)
        if self.fail:
            raise OSError("boom")
        return {"data": [{"id": i, "context_window": 131072} for i in self.ids]}


def _by_model(cat, model):
    return next(e for e in cat.entries if e.model == model)


# --- provider exposure ------------------------------------------------------
def test_only_authenticated_real_providers_exposed(monkeypatch):
    _groq(monkeypatch)
    # vendors with keys but no adapter must never show up
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setenv("MISTRAL_API_KEY", "x")
    cat = catalog.build(discover=False)
    assert {e.provider for e in cat.entries} == {"groq"}
    assert all(e.adapter == "custom" for e in cat.entries)


def test_placeholder_keys_are_not_auth(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "your_openai_api_key_here")
    assert catalog.build(discover=False).entries == []


def test_include_unavailable_marks_no_auth():
    cat = catalog.build(discover=False, include_unavailable=True)
    assert cat.entries and {e.availability for e in cat.entries} == {"no_auth"}
    assert not any(e.routable for e in cat.entries)


def test_keyless_custom_only_for_local(monkeypatch):
    monkeypatch.setenv("CUSTOM_API_URL", "https://remote.example.com/v1")
    assert catalog.build(discover=False).entries == []
    monkeypatch.setenv("CUSTOM_API_URL", "http://localhost:11434/v1")
    assert {e.provider for e in catalog.build(discover=False).entries} == {"local"}


# --- discovery merge + cache -----------------------------------------------
def test_merge_static_and_discovered(monkeypatch):
    _groq(monkeypatch)
    cat = catalog.build(fetcher=Fetcher())
    e = _by_model(cat, "openai/gpt-oss-120b")
    assert e.source == "static+discovered" and e.routable
    w = _by_model(cat, "whisper-large-v3")
    assert w.source == "discovered" and w.availability == "discovered" and not w.routable
    assert w.chat is None  # never guessed from the name


def test_static_model_missing_from_live_listing_is_stale(monkeypatch):
    _groq(monkeypatch)
    cat = catalog.build(fetcher=Fetcher(ids=("openai/gpt-oss-120b",)))
    assert _by_model(cat, "openai/gpt-oss-20b").availability == "stale"
    assert _by_model(cat, "openai/gpt-oss-120b").availability == "available"


def test_ttl_cache_and_refresh(monkeypatch):
    _groq(monkeypatch)
    f = Fetcher()
    catalog.build(fetcher=f)
    catalog.build(fetcher=f)
    assert f.calls == 1  # second build served from cache
    catalog.build(fetcher=f, refresh=True)
    assert f.calls == 2
    monkeypatch.setenv("PAL_CATALOG_TTL_S", "0")
    catalog.build(fetcher=f)
    assert f.calls == 3  # expired


def test_offline_build_never_fetches_and_uses_cache(monkeypatch):
    _groq(monkeypatch)
    catalog.build(fetcher=Fetcher())
    boom = Fetcher(fail=True)
    cat = catalog.build(discover=False, fetcher=boom)
    assert boom.calls == 0
    assert _by_model(cat, "whisper-large-v3").source == "discovered"


def test_failure_degrades_to_static_and_is_negative_cached(monkeypatch):
    _groq(monkeypatch)
    f = Fetcher(fail=True)
    cat = catalog.build(fetcher=f)
    assert cat.discovery["groq"]["status"] == "failed"
    assert _by_model(cat, "openai/gpt-oss-120b").routable  # static still serves
    catalog.build(fetcher=f)
    assert f.calls == 1  # failure not retried inside the fail TTL


def test_failed_refresh_keeps_last_good_listing_on_disk(monkeypatch):
    _groq(monkeypatch)
    catalog.build(fetcher=Fetcher())
    catalog.build(fetcher=Fetcher(fail=True), refresh=True)
    data = json.loads(catalog.CACHE_PATH.read_text())
    assert data["services"]["groq"]["ok"] is False
    assert len(data["services"]["groq"]["models"]) == 3


def test_cache_holds_no_credentials(monkeypatch):
    _groq(monkeypatch)
    f = Fetcher()
    catalog.build(fetcher=f)
    assert "gsk_test_secret" not in catalog.CACHE_PATH.read_text()
    assert f.headers[0]["Authorization"] == "Bearer gsk_test_secret"  # sent, never stored


def test_openrouter_parser_reads_real_capabilities():
    raw = {
        "data": [
            {
                "id": "x/y",
                "context_length": 1000,
                "pricing": {"prompt": "0", "completion": "0"},
                "supported_parameters": ["tools", "structured_outputs"],
                "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
            }
        ]
    }
    m = catalog._parse_openrouter(raw)[0]
    assert (m["tools"], m["vision"], m["structured_output"], m["reasoning"]) == (True, True, True, False)
    assert catalog._tier_from_price(m["input_per_mtok"], m["output_per_mtok"]) == "free"


def test_gemini_parser_strips_prefix_and_flags_chat():
    m = catalog._parse_gemini(
        {"models": [{"name": "models/g-1", "inputTokenLimit": 5, "supportedGenerationMethods": ["embedContent"]}]}
    )[0]
    assert m["id"] == "g-1" and m["chat"] is False and m["context_limit"] == 5


# --- capability routing -----------------------------------------------------
def _e(model, *, provider="p", i=10, cost="low", ctx=100_000, tools=True, structured=True, avail="available", chat=True):
    return catalog.CatalogEntry(
        provider=provider,
        adapter="custom",
        model=model,
        display=model,
        chat=chat,
        tools=tools,
        structured_output=structured,
        context_limit=ctx,
        availability=avail,
        quality_profile={"intelligence": i},
        cost_profile={"tier": cost},
    )


def test_select_filters_on_capabilities_and_ignores_names():
    pool = [
        _e("gpt-structured", structured=True),
        _e("no-structured", structured=False),
        _e("unknown-structured", structured=None),
        _e("down", avail="stale"),
        _e("embed", chat=None),
    ]
    got = [e.model for e in catalog.select(catalog.Need(structured_output=True), pool)]
    assert got == ["gpt-structured"]  # None never satisfies; stale/non-chat excluded


def test_min_context_gate():
    pool = [_e("small", ctx=128_000), _e("big", ctx=1_000_000)]
    assert [e.model for e in catalog.select(catalog.Need(min_context=200_000), pool)] == ["big"]


def test_cheap_prefers_low_cost_then_prior_then_quality():
    pool = [_e("pricey", cost="high", i=19), _e("a", cost="low", i=8), _e("b", cost="low", i=12), _e("free", cost="free", i=5)]
    assert catalog.select(catalog.Need(tier="cheap"), pool, priors=("a",))[0].model == "a"  # free tier excluded by default
    assert catalog.select(catalog.Need(tier="cheap", allow_free_tier=True), pool)[0].model == "free"
    order = [e.model for e in catalog.select(catalog.Need(tier="cheap"), pool[:3], priors=("a",))]
    assert order == ["a", "b", "pricey"]  # prior breaks the cost tie; quality after


def test_smart_orders_by_prior_before_cost():
    pool = [_e("cheap-strong", i=15, cost="low"), _e("preferred", i=15, cost="mid")]
    assert catalog.select(catalog.Need(tier="smart"), pool, priors=("preferred",))[0].model == "preferred"


def test_free_tier_excluded_unless_bulk_category(monkeypatch):
    pool = [_e("freebie", cost="free", ctx=1_000_000), _e("paid", cost="mid", ctx=1_000_000)]
    assert [e.model for e in catalog.select(catalog.Need(), pool)] == ["paid"]
    assert catalog.category_need("security_permissive").allow_free_tier is False
    assert catalog.category_need("long_context_bulk").allow_free_tier is True


def test_smart_tier_has_quality_floor():
    pool = [_e("weak", i=8, cost="free"), _e("strong", i=15, cost="mid")]
    assert [e.model for e in catalog.select(catalog.Need(tier="smart"), pool)] == ["strong"]


def test_prior_never_admits_ineligible_model():
    pool = [_e("a", structured=False), _e("b", structured=True)]
    got = [e.model for e in catalog.select(catalog.Need(structured_output=True), pool, priors=("a",))]
    assert got == ["b"]


def test_order_for_category_uses_catalog_and_falls_back(monkeypatch):
    _groq(monkeypatch)
    catalog.build(fetcher=Fetcher())
    catalog.reset_memo()
    got = catalog.order_for_category("structured_extract", ["openai/gpt-oss-20b", "or-free"])
    assert got[0] == "openai/gpt-oss-20b" and "or-free" not in got
    # bulk needs 200k ctx; nothing on groq qualifies -> [] -> caller keeps legacy list
    assert catalog.order_for_category("long_context_bulk", ["x"]) == []
    monkeypatch.setenv("PAL_CATALOG_ROUTING", "0")
    assert catalog.order_for_category("structured_extract", ["x"]) == []


def test_pick_tier_respects_live_availability(monkeypatch):
    _groq(monkeypatch)
    monkeypatch.setattr(catalog, "routing_catalog", lambda *a, **k: catalog.build(discover=False))
    assert catalog.pick_tier("cheap", lambda n: n == "gpt-oss-20b") == "gpt-oss-20b"
    assert catalog.pick_tier("smart", lambda n: n == "gpt-oss-20b") is None  # 20b (11) < smart floor
    assert catalog.pick_tier("smart", lambda n: False) is None


# --- CLI --------------------------------------------------------------------
def test_cli_json_output(monkeypatch, capsys):
    _groq(monkeypatch)
    monkeypatch.setattr(catalog, "_http_json", Fetcher())
    assert cli.main(["models", "--json", "--refresh"]) == 0
    out = json.loads(capsys.readouterr().out)
    models = {m["model"] for m in out["models"]}
    assert "openai/gpt-oss-120b" in models and "whisper-large-v3" not in models  # uncurated hidden
    assert {"provider", "model", "display", "chat", "tools", "vision", "structured_output", "reasoning",
            "context_limit", "availability", "quality_profile", "cost_profile", "source"} <= set(out["models"][0])


def test_cli_all_shows_uncurated(monkeypatch, capsys):
    _groq(monkeypatch)
    monkeypatch.setattr(catalog, "_http_json", Fetcher())
    catalog_cli.main(["--json", "--all", "--refresh"])
    assert "whisper-large-v3" in capsys.readouterr().out


def test_cli_unknown_provider_exits_2(monkeypatch, capsys):
    _groq(monkeypatch)
    monkeypatch.setattr(catalog, "_http_json", Fetcher())
    assert catalog_cli.main(["--provider", "nope"]) == 2
    assert "groq" in capsys.readouterr().err


def test_cli_table_renders(monkeypatch, capsys):
    _groq(monkeypatch)
    monkeypatch.setattr(catalog, "_http_json", Fetcher())
    assert catalog_cli.main(["--provider", "groq"]) == 0
    out = capsys.readouterr().out
    assert "PROVIDER" in out and "discovery[groq]" in out
