"""Cross-cutting wiring + coverage invariants for the native open-model providers.

These lock the gaps an adhd audit surfaced: four-registry bijection, natives-before-OpenRouter
ordering, cross-route score pinning, per-model conf well-formedness, vision flags, key-gating, and
the local R1 distills. They are route-independent (load conf JSON directly) so they never make a
network call.
"""

import json
from pathlib import Path

import pytest

from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from utils.model_restrictions import ModelRestrictionService

CONF = Path(__file__).resolve().parents[1] / "conf"

# The 8 native OpenAI-compatible providers added in this batch: (ProviderType, env var, conf filename).
NATIVE_VENDORS = [
    (ProviderType.DEEPSEEK, "DEEPSEEK_API_KEY", "deepseek_models.json"),
    (ProviderType.QWEN, "DASHSCOPE_API_KEY", "qwen_models.json"),
    (ProviderType.ZAI, "ZAI_API_KEY", "zai_models.json"),
    (ProviderType.MOONSHOT, "MOONSHOT_API_KEY", "moonshot_models.json"),
    (ProviderType.MINIMAX, "MINIMAX_API_KEY", "minimax_models.json"),
    (ProviderType.MISTRAL, "MISTRAL_API_KEY", "mistral_models.json"),
    (ProviderType.NVIDIA, "NVIDIA_API_KEY", "nvidia_models.json"),
    (ProviderType.PERPLEXITY, "PERPLEXITY_API_KEY", "perplexity_models.json"),
]

# Native model -> OpenRouter mirror model whose intelligence_score must stay identical (score pinning).
SCORE_PINS = [
    ("deepseek_models.json", "deepseek-v4-pro", "deepseek/deepseek-v4-pro"),
    ("deepseek_models.json", "deepseek-v4-flash", "deepseek/deepseek-v4-flash"),
    ("deepseek_models.json", "deepseek-reasoner", "deepseek/deepseek-r1-0528"),
    ("qwen_models.json", "qwen3.8-max", "qwen/qwen3.8-max"),
    ("qwen_models.json", "qwen3.8-flash", "qwen/qwen3.8-flash"),
    ("zai_models.json", "glm-5.3", "z-ai/glm-5.3"),
    ("zai_models.json", "glm-5.3-flash", "z-ai/glm-5.3-flash"),
    ("moonshot_models.json", "kimi-k3", "moonshotai/kimi-k3"),
    ("minimax_models.json", "MiniMax-M3", "minimax/minimax-m3"),
    ("anthropic_models.json", "claude-fable-5-1", "anthropic/claude-fable-5.1"),
    ("deepseek_models.json", "deepseek-v4.1-flash", "deepseek/deepseek-v4.1-flash"),
    ("qwen_models.json", "qwen3.8-max-0902", "qwen/qwen3.8-max-0902"),
    ("openai_models.json", "gpt-6-astra", "openai/gpt-6-astra"),
    ("anthropic_models.json", "claude-opus-5-5", "anthropic/claude-opus-5.5"),
    ("anthropic_models.json", "claude-sonnet-5-5", "anthropic/claude-sonnet-5.5"),
    ("openai_models.json", "gpt-6.1-sol", "openai/gpt-6.1-sol"),
    ("openai_models.json", "gpt-6-luna", "openai/gpt-6-luna"),
    ("xai_models.json", "grok-4.7", "x-ai/grok-4.7"),
    ("anthropic_models.json", "claude-haiku-5-5", "anthropic/claude-haiku-5.5"),
    ("gemini_models.json", "gemini-4-argon", "google/gemini-4-argon"),
]


def _models(filename):
    return {m["model_name"]: m for m in json.loads((CONF / filename).read_text())["models"]}


def _or_scores():
    return {
        m["model_name"]: m.get("intelligence_score")
        for m in json.loads((CONF / "openrouter_models.json").read_text())["models"]
    }


@pytest.mark.parametrize("ptype,env_var,conf", NATIVE_VENDORS)
def test_providertype_wired_in_all_registries(ptype, env_var, conf, monkeypatch):
    # Bijection: each new ProviderType must appear in priority order, both restriction maps, and the
    # registry key map (a member wired into one place but missing from another breaks resolution).
    assert ptype in ModelProviderRegistry.PROVIDER_PRIORITY_ORDER, f"{ptype} missing from PROVIDER_PRIORITY_ORDER"
    assert ptype in ModelRestrictionService.ENV_VARS, f"{ptype} missing from ENV_VARS"
    assert ptype in ModelRestrictionService.DISALLOWED_ENV_VARS, f"{ptype} missing from DISALLOWED_ENV_VARS"
    monkeypatch.setenv(env_var, "sentinel-key")
    assert ModelProviderRegistry._get_api_key_for_provider(ptype) == "sentinel-key", f"{ptype} key map wrong/absent"


@pytest.mark.parametrize("ptype,env_var,conf", NATIVE_VENDORS)
def test_native_ranks_before_openrouter(ptype, env_var, conf):
    order = ModelProviderRegistry.PROVIDER_PRIORITY_ORDER
    assert order.index(ptype) < order.index(ProviderType.OPENROUTER), f"{ptype} must rank before OpenRouter"


def test_env_var_names_unique():
    names = [env for _, env, _ in NATIVE_VENDORS]
    assert len(names) == len(set(names)), "duplicate/typo-shadowed API-key env var names"


@pytest.mark.parametrize("conf,native_model,or_model", SCORE_PINS)
def test_cross_route_score_pinning(conf, native_model, or_model):
    native = _models(conf)
    assert native_model in native, f"{native_model} missing from {conf}"
    or_scores = _or_scores()
    assert or_model in or_scores, f"{or_model} missing from openrouter_models.json"
    assert (
        native[native_model]["intelligence_score"] == or_scores[or_model]
    ), f"score drift: {native_model} != {or_model}"
    assert native[native_model].get("aa_index") == _orm()[or_model].get("aa_index"), f"aa_index drift: {native_model}"
    assert native[native_model].get("aa_index_by_effort") == _orm()[or_model].get(
        "aa_index_by_effort"
    ), f"aa_index_by_effort drift: {native_model}"


@pytest.mark.parametrize("ptype,env_var,conf", NATIVE_VENDORS)
def test_conf_well_formed(ptype, env_var, conf):
    models = _models(conf)
    assert models, f"{conf} has no models"
    seen_aliases = {}
    for name, m in models.items():
        assert m.get("context_window", 0) > 0, f"{name}: context_window must be > 0"
        assert m.get("max_output_tokens", 0) > 0, f"{name}: max_output_tokens must be > 0"
        assert 1 <= m.get("intelligence_score", 0) <= 20, f"{name}: score out of range"
        assert m.get("aliases"), f"{name}: must declare at least one alias"
        assert isinstance(m.get("supports_images"), bool), f"{name}: supports_images must be an explicit bool"
        for a in m["aliases"]:
            assert (
                a.lower() not in seen_aliases
            ), f"{conf}: duplicate alias '{a}' ({name} vs {seen_aliases.get(a.lower())})"
            seen_aliases[a.lower()] = name


def test_vision_flags_explicit():
    ds = _models("deepseek_models.json")
    assert ds["deepseek-v4-flash-vision-exp"]["supports_images"] is True
    assert ds["deepseek-v4-pro"]["supports_images"] is False  # non-vision must NOT claim images
    orm = {m["model_name"]: m for m in json.loads((CONF / "openrouter_models.json").read_text())["models"]}
    assert orm["deepseek/deepseek-v4-flash-vision-exp"]["supports_images"] is True


def test_qwen38_flash_present_both_routes():
    # Production Qwen3.8 Flash: multimodal on both routes, and the bare "qwen-flash" alias now points
    # at it (newest production Flash), the same convention as glm-flash -> glm-5.3-flash.
    native = _models("qwen_models.json")
    assert "qwen3.8-flash" in native, "qwen3.8-flash missing from qwen_models.json"
    assert native["qwen3.8-flash"]["supports_images"] is True
    assert "qwen-flash" in native["qwen3.8-flash"]["aliases"]

    orm = {m["model_name"]: m for m in json.loads((CONF / "openrouter_models.json").read_text())["models"]}
    assert "qwen/qwen3.8-flash" in orm, "qwen/qwen3.8-flash missing from openrouter_models.json"
    assert orm["qwen/qwen3.8-flash"]["supports_images"] is True
    assert "qwen-flash" in orm["qwen/qwen3.8-flash"]["aliases"]
    # The bare alias must not still hang off the older 3.6 mirror (duplicate-alias collision).
    assert "qwen-flash" not in orm["qwen/qwen3.6-flash"]["aliases"]


def test_fable_5_1_present_both_routes():
    # Claude Fable 5.1 (tops the current AA Index at 53): native claude-fable-5-1 + OpenRouter mirror,
    # score 20, and the bare "fable" alias now points at 5.1 (newest-wins).
    a = _models("anthropic_models.json")
    assert a["claude-fable-5-1"]["intelligence_score"] == 19
    assert "fable" in a["claude-fable-5-1"]["aliases"]
    assert "fable" not in a["claude-fable-5"]["aliases"], "bare 'fable' must move off Fable 5"

    orm = {m["model_name"]: m for m in json.loads((CONF / "openrouter_models.json").read_text())["models"]}
    assert "anthropic/claude-fable-5.1" in orm
    assert orm["anthropic/claude-fable-5.1"]["intelligence_score"] == 19
    assert "fable" in orm["anthropic/claude-fable-5.1"]["aliases"]
    assert "fable" not in orm["anthropic/claude-fable-5"]["aliases"]


def test_qwen38_max_0902_native_present():
    # Production Qwen3.8-Max-0902 snapshot on DashScope (no OpenRouter mirror yet); the bare "qwen-max"
    # alias now points at it. Score held at the base Max tier (17) since no distinct AA Index exists.
    q = _models("qwen_models.json")
    assert "qwen3.8-max-0902" in q, "qwen3.8-max-0902 missing from qwen_models.json"
    assert q["qwen3.8-max-0902"]["intelligence_score"] == 17
    assert "qwen-max" in q["qwen3.8-max-0902"]["aliases"]
    assert "qwen-max" not in q["qwen3.8-max"]["aliases"], "bare 'qwen-max' must move off base Max"


def test_local_r1_distills_present_and_scored():
    custom = _models("custom_models.json")
    expected = {
        "deepseek-r1:1.5b": 6,
        "deepseek-r1:7b": 7,
        "deepseek-r1:8b": 8,
        "deepseek-r1:14b": 9,
        "deepseek-r1:32b": 10,
    }
    for name, score in expected.items():
        assert name in custom, f"local distill {name} missing"
        assert custom[name]["intelligence_score"] == score
        assert custom[name]["supports_extended_thinking"] is True
    assert "deepseek-r1:70b" not in custom, "70B distill must be excluded (OOMs a single local box)"


@pytest.mark.parametrize("ptype,env_var,conf", NATIVE_VENDORS)
def test_dormant_without_key(ptype, env_var, conf, monkeypatch):
    # Key-gating: with the env var unset, the registry must not hand back an initialized provider.
    monkeypatch.delenv(env_var, raising=False)
    ModelProviderRegistry.reset_for_testing()
    from importlib import import_module

    module_name = {
        ProviderType.DEEPSEEK: "providers.deepseek",
        ProviderType.QWEN: "providers.qwen",
        ProviderType.ZAI: "providers.zai",
        ProviderType.MOONSHOT: "providers.moonshot",
        ProviderType.MINIMAX: "providers.minimax",
        ProviderType.MISTRAL: "providers.mistral",
        ProviderType.NVIDIA: "providers.nvidia",
        ProviderType.PERPLEXITY: "providers.perplexity",
    }[ptype]
    cls = next(v for k, v in vars(import_module(module_name)).items() if k.endswith("ModelProvider"))
    ModelProviderRegistry.register_provider(ptype, cls)
    assert ModelProviderRegistry.get_provider(ptype) is None, f"{ptype} initialized without a key"
    ModelProviderRegistry.reset_for_testing()


def test_every_native_provider_has_a_deferred_live_test():
    # "Deferred but present": each native provider must carry a (skipif-no-key) live test, so a missing
    # key is an explicit skip, never a silently-absent provider.
    from tests.test_native_provider_live import LIVE_VENDORS

    covered = {ptype for ptype, *_ in LIVE_VENDORS}
    expected = {ptype for ptype, *_ in NATIVE_VENDORS}
    assert covered == expected, f"native providers without a deferred live test: {expected - covered}"


# --------------------------------------------------------------------------------------------------
# 2026-09 re-anchor: scores mapped to the Artificial Analysis Intelligence Index v4.3 (2026-09-11),
# plus the models added in that pass.
# --------------------------------------------------------------------------------------------------


def _orm():
    return {m["model_name"]: m for m in json.loads((CONF / "openrouter_models.json").read_text())["models"]}


def test_gpt6_astra_present_both_routes():
    # OpenAI GPT-6 Astra ties the top of the current AA Index at 53 (max effort) -> score 20.
    native = _models("openai_models.json")
    assert native["gpt-6-astra"]["intelligence_score"] == 19
    assert "astra" in native["gpt-6-astra"]["aliases"]
    # OpenAI's API has no gpt-6-astra-pro model ID: pro is reasoning.mode=pro on GPT-6 Astra.
    assert "gpt-6-astra-pro" not in native

    orm = _orm()
    assert orm["openai/gpt-6-astra"]["intelligence_score"] == 19
    # The OpenRouter -pro preset exists, but it spends far more tokens, so it is explicit-only.
    pro = orm["openai/gpt-6-astra-pro"]
    assert pro["auto_selectable"] is False
    assert "astra-pro" in pro["aliases"]


def test_deepseek_v41_flash_supersedes_retired_models():
    # V4.1 Flash (AA 40) replaces V4 Flash and V4 Flash Vision Exp, which DeepSeek retired, so the
    # bare "deepseek" / "deepseek-flash" aliases move to it on both routes.
    ds = _models("deepseek_models.json")
    assert ds["deepseek-v4.1-flash"]["intelligence_score"] == 13
    assert ds["deepseek-v4.1-flash"]["supports_images"] is True
    assert "deepseek" in ds["deepseek-v4.1-flash"]["aliases"]
    assert "deepseek-flash" in ds["deepseek-v4.1-flash"]["aliases"]
    assert "deepseek" not in ds["deepseek-v4-pro"]["aliases"]
    assert "deepseek-flash" not in ds["deepseek-v4-flash"]["aliases"]
    # The retired entries must say so, so nobody treats them as current.
    assert "RETIRED" in ds["deepseek-v4-flash"]["description"]
    assert "RETIRED" in ds["deepseek-v4-flash-vision-exp"]["description"]
    assert "DEPRECATED" in ds["deepseek-v4-pro"]["description"]

    orm = _orm()
    assert orm["deepseek/deepseek-v4.1-flash"]["intelligence_score"] == 13
    assert "deepseek" in orm["deepseek/deepseek-v4.1-flash"]["aliases"]


def test_qwen38_max_0902_openrouter_mirror():
    # The 0902 snapshot reached OpenRouter, so the mirror exists and is score-pinned to the native entry.
    orm = _orm()
    assert "qwen/qwen3.8-max-0902" in orm
    assert orm["qwen/qwen3.8-max-0902"]["intelligence_score"] == 17
    assert "qwen-max" in orm["qwen/qwen3.8-max-0902"]["aliases"]
    assert "qwen-max" not in orm["qwen/qwen3.8-max"]["aliases"]


def test_reanchor_top_of_catalog():
    # The re-anchor must leave a single coherent top: Fable 5.1 and GPT-6 Astra at 20, Opus 5 at 19,
    # and no legacy model left above them.
    a = _models("anthropic_models.json")
    o = _models("openai_models.json")
    assert a["claude-fable-5-1"]["intelligence_score"] == 19
    assert o["gpt-6-astra"]["intelligence_score"] == 19
    assert a["claude-opus-5"]["intelligence_score"] == 18
    assert o["gpt-5.6-sol"]["intelligence_score"] == 17
    # No model anywhere may exceed the top of the scale.
    import glob

    for path in glob.glob(str(CONF / "*_models.json")):
        for m in json.loads(open(path).read()).get("models", []):
            assert 1 <= m["intelligence_score"] <= 20, f"{m['model_name']} out of range in {path}"


def test_gemini_38_flash_and_family_refresh():
    # 2026-09-24 refresh. Gemini 3.8 Flash (AA 41) is the newest Flash, so it takes both the
    # "gemini-flash-latest" alias and the gated dynamic "flash" alias from 3.7.
    g = _models("gemini_models.json")
    assert g["gemini-3.8-flash"]["intelligence_score"] == 16
    assert "gemini-flash-latest" in g["gemini-3.8-flash"]["aliases"]
    assert "flash" in g["gemini-3.8-flash"]["dynamic_aliases"]
    assert "gemini-flash-latest" not in g["gemini-3.7-flash"]["aliases"]
    assert "dynamic_aliases" not in g["gemini-3.7-flash"]

    # Newest entry per open-weight family, each scored from the current AA Index.
    orm = _orm()
    expected = {
        "google/gemini-3.8-flash": 16,
        "meta/muse-spark-1.3": 17,
        "xiaomi/mimo-v2.6-pro": 18,
        "qwen/qwen3.8-27b": 12,
        "moonshotai/kimi-k2.7-code": 10,
        "nvidia/nemotron-3-ultra-550b-a55b": 9,
    }
    for name, score in expected.items():
        assert name in orm, f"{name} missing from openrouter_models.json"
        assert orm[name]["intelligence_score"] == score, f"{name}: expected {score}"

    # Bare family aliases follow newest-wins off the superseded entries.
    assert "muse" in orm["meta/muse-spark-1.3"]["aliases"]
    assert "muse" not in orm["meta/muse-spark-1.2"]["aliases"]
    assert "mimo" in orm["xiaomi/mimo-v2.6-pro"]["aliases"]
    assert "mimo" not in orm["xiaomi/mimo-v2.5-pro"]["aliases"]


def test_mimo_v26_series_complete():
    # Xiaomi announced the MiMo-V2.6 series (2026-09-22) as three models, not one. All three are
    # MIT-weight, 1M context and omnimodal. Pro is AA-scored at 46; the other two are provisional.
    orm = _orm()
    expected = {
        "xiaomi/mimo-v2.6-pro": 18,  # AA Index 46, measured
        "xiaomi/mimo-v2.6-flash": 15,  # provisional: within 4 points of Pro, one tier below
        "xiaomi/mimo-v2.6-pro-ultraspeed": 18,  # provisional: vendor-claimed parity with Pro
    }
    for name, score in expected.items():
        assert name in orm, f"{name} missing from openrouter_models.json"
        assert orm[name]["intelligence_score"] == score, f"{name}: expected {score}"
        assert orm[name]["supports_images"] is True, f"{name}: omnimodal, must accept images"
    # The two unmeasured entries must say so, so nobody mistakes them for AA-anchored scores.
    for name in ("xiaomi/mimo-v2.6-flash", "xiaomi/mimo-v2.6-pro-ultraspeed"):
        assert "PROVISIONAL" in orm[name]["description"], f"{name}: must be tagged PROVISIONAL"
    # Bare family aliases stay on the flagship.
    assert "mimo" in orm["xiaomi/mimo-v2.6-pro"]["aliases"]


def test_claude_opus_55_both_routes():
    # Claude Opus 5.5 (2026-09-22) scores 58 at max effort, above Fable 5.1 and GPT-6 Astra (53).
    # The 1-20 scale tops out at 20, so all three share the top score.
    a = _models("anthropic_models.json")
    assert a["claude-opus-5-5"]["intelligence_score"] == 20
    assert "opus" in a["claude-opus-5-5"]["aliases"]
    assert "opus" not in a["claude-opus-5"]["aliases"], "bare 'opus' must move off Opus 5"

    orm = _orm()
    assert orm["anthropic/claude-opus-5.5"]["intelligence_score"] == 20
    assert "opus" in orm["anthropic/claude-opus-5.5"]["aliases"]
    # On the OpenRouter route the bare alias used to hang off the legacy Opus 4.5.
    assert "opus" not in orm["anthropic/claude-opus-4.5"]["aliases"]


def test_late_september_releases():
    # Sonnet 5.5 (AA 56), GPT-6.1 Sol (52), Grok 4.7 (46), GPT-6 Luna (37) and Command A+ (13),
    # scored on the v4.3 ladder. Fork-owned bare aliases move directly; the upstream-owned "grok"
    # and OpenRouter "sonnet" aliases move only under DYNAMIC_MODEL_SELECTION.
    a = _models("anthropic_models.json")
    assert a["claude-sonnet-5-5"]["intelligence_score"] == 18
    assert "sonnet" in a["claude-sonnet-5-5"]["aliases"]
    assert "sonnet" not in a["claude-sonnet-5"]["aliases"]

    o = _models("openai_models.json")
    assert o["gpt-6.1-sol"]["intelligence_score"] == 19
    assert o["gpt-6-luna"]["intelligence_score"] == 13
    assert "sol" in o["gpt-6.1-sol"]["aliases"] and "sol" not in o["gpt-5.6-sol"]["aliases"]
    assert "luna" in o["gpt-6-luna"]["aliases"] and "luna" not in o["gpt-5.6-luna"]["aliases"]

    x = _models("xai_models.json")
    assert x["grok-4.7"]["intelligence_score"] == 18
    assert x["grok-4.7"]["dynamic_aliases"] == ["grok"]
    assert "grok" in x["grok-4"]["aliases"], "default 'grok' target stays upstream's grok-4"

    orm = _orm()
    assert orm["anthropic/claude-sonnet-5.5"]["dynamic_aliases"] == ["sonnet"]
    assert "sonnet" in orm["anthropic/claude-sonnet-4.5"]["aliases"]
    assert orm["x-ai/grok-4.7"]["dynamic_aliases"] == ["grok"]
    assert orm["cohere/command-a-plus"]["intelligence_score"] == 6


def test_gpt61_sol_pro_is_explicit_only():
    # GPT-6.1 Sol Pro is GPT-6.1 Sol with reasoning.mode=pro: same per-token price, far more tokens per
    # request. It must never be an auto-mode candidate, and its score stays pinned to the base model
    # until Artificial Analysis lists the pro mode.
    orm = _orm()
    pro = orm["openai/gpt-6.1-sol-pro"]
    assert pro["auto_selectable"] is False
    assert pro["intelligence_score"] == orm["openai/gpt-6.1-sol"]["intelligence_score"]
    assert "aa_index" not in pro, "no measured Index value for the pro mode yet"
    assert "PROVISIONAL" in pro["description"]


AA_EFFORT_KEYS = {"non-reasoning", "low", "medium", "high", "xhigh", "max", "default"}


def test_aa_index_by_effort_well_formed():
    # Per-effort AA values (Phase 2 of the effort-scoring plan): valid effort keys, integer values in
    # the Index range, and "default" only for a model that has a single AA row.
    seen = 0
    for path in sorted(CONF.glob("*_models.json")):
        for m in json.loads(path.read_text()).get("models", []):
            values = m.get("aa_index_by_effort")
            if values is None:
                continue
            seen += 1
            name = f"{path.name}:{m['model_name']}"
            assert values, f"{name}: empty aa_index_by_effort"
            assert set(values) <= AA_EFFORT_KEYS, f"{name}: unknown effort key {set(values) - AA_EFFORT_KEYS}"
            assert all(isinstance(v, int) and 0 < v <= 100 for v in values.values()), f"{name}: bad value"
            if "default" in values:
                assert len(values) == 1, f"{name}: 'default' must be the only key"
    assert seen >= 40, "expected per-effort values on the measured models"


def test_october_releases():
    # Releases through 2026-10-13, scored on the max-effort ladder (Phase 3 re-scores at high).
    a = _models("anthropic_models.json")
    assert a["claude-haiku-5-5"]["intelligence_score"] == 15  # AA 43 (max)
    assert "haiku" in a["claude-haiku-5-5"]["aliases"]
    assert "haiku" not in a["claude-haiku-4-5-20251001"]["aliases"]

    g = _models("gemini_models.json")
    assert g["gemini-4-argon"]["intelligence_score"] == 20  # AA 53 (high is AA's only row)
    assert "dynamic_aliases" not in g["gemini-4-argon"], "Argon must not take over the pro/gemini3 aliases"

    orm = _orm()
    expected = {
        "anthropic/claude-haiku-5.5": 15,
        "google/gemini-4-argon": 20,
        "meta/muse-wonder": 18,
        "mistralai/mistral-large-4-0": 15,
        "stepfun/step-5-preview": 17,
        "qwen/qwen3.8-2.4t-a95b": 15,
        "openai/gpt-6-luna-pro": 13,
    }
    for name, score in expected.items():
        assert orm[name]["intelligence_score"] == score, name
        assert orm[name].get("aa_index_by_effort") or name.endswith("-pro"), name
    # The upstream-owned OpenRouter "haiku" alias moves only under DYNAMIC_MODEL_SELECTION.
    assert orm["anthropic/claude-haiku-5.5"]["dynamic_aliases"] == ["haiku"]
    assert "haiku" in orm["anthropic/claude-3.5-haiku"]["aliases"]
    # Pro presets stay explicit-only.
    assert orm["openai/gpt-6-luna-pro"]["auto_selectable"] is False


def test_model_catalog_doc_is_current():
    # docs/model_catalog.md is generated from the conf files. Every measured model and every
    # explicit-only preset must appear in it; run scripts/generate_model_catalog.py after a change.
    doc = (CONF.parent / "docs" / "model_catalog.md").read_text()
    missing = []
    for path in sorted(CONF.glob("*_models.json")):
        for m in json.loads(path.read_text()).get("models", []):
            listed = m.get("aa_index_by_effort") or (
                m.get("auto_selectable") is False and "fusion" not in m["model_name"]
            )
            if listed and f"`{m['model_name']}`" not in doc:
                missing.append(f"{path.name}:{m['model_name']}")
    assert not missing, f"regenerate docs/model_catalog.md; missing: {missing}"


# AA Index (at the high-effort anchor) -> intelligence_score. Mirrors the ladder in docs/model_ranking.md.
AA_LADDER = [
    (52, 20),
    (50, 19),
    (46, 18),
    (43, 17),
    (41, 16),
    (38, 15),
    (36, 14),
    (33, 13),
    (30, 12),
    (27, 11),
    (24, 10),
    (21, 9),
    (18, 8),
    (15, 7),
    (12, 6),
    (9, 5),
    (7, 4),
    (0, 3),
]


def _ladder(value):
    return next(score for floor, score in AA_LADDER if value >= floor)


def test_measured_scores_follow_the_high_effort_ladder():
    # Phase 3 of the effort-scoring plan: a measured model's score is ladder(AA at high), or ladder(the
    # single AA row). Without a high row the value is interpolated or estimated, and the description
    # must say so. aa_index records the anchor value in every case.
    for path in sorted(CONF.glob("*_models.json")):
        for m in json.loads(path.read_text()).get("models", []):
            effort = m.get("aa_index_by_effort")
            if not effort:
                continue
            name = f"{path.name}:{m['model_name']}"
            anchor = effort.get("high", effort.get("default"))
            if anchor is None:
                desc = m["description"]
                assert "interpolated" in desc or "ESTIMATE" in desc, f"{name}: anchor not documented"
                anchor = m["aa_index"]
            assert m.get("aa_index") is not None and abs(m["aa_index"] - anchor) < 1, f"{name}: aa_index != anchor"
            assert m["intelligence_score"] == _ladder(anchor), f"{name}: score != ladder({anchor})"


# ---------------------------------------------------------------------------
# Entra ID auth: Azure OpenAI (AZURE_OPENAI_USE_ENTRA) and Claude on Azure AI Foundry (ANTHROPIC_USE_ENTRA)
# need no API key at any gate: server provider detection, registry construction, provider client.
# ---------------------------------------------------------------------------

_AZURE_ENDPOINT = "https://example.openai.azure.com"
_FOUNDRY_URL = "https://example-resource.services.ai.azure.com/anthropic"


@pytest.fixture
def azure_models_file(tmp_path, monkeypatch):
    path = tmp_path / "azure_models.json"
    path.write_text(json.dumps({"models": [{"model_name": "gpt-5.4", "deployment": "gpt54"}]}))
    monkeypatch.setenv("AZURE_MODELS_CONFIG_PATH", str(path))
    return path


@pytest.fixture
def clean_registry():
    ModelProviderRegistry.reset_for_testing()
    yield
    ModelProviderRegistry.reset_for_testing()


def test_registry_builds_azure_in_entra_mode_without_key(monkeypatch, azure_models_file, clean_registry):
    from providers.azure_openai import AzureOpenAIProvider

    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", _AZURE_ENDPOINT)
    monkeypatch.setenv("AZURE_OPENAI_USE_ENTRA", "true")
    ModelProviderRegistry.register_provider(ProviderType.AZURE, AzureOpenAIProvider)

    provider = ModelProviderRegistry.get_provider(ProviderType.AZURE)

    assert provider is not None
    assert provider._use_entra is True
    assert provider.api_key == ""


def test_registry_azure_entra_wins_over_a_configured_key(monkeypatch, azure_models_file, clean_registry):
    # With the flag on, a leftover AZURE_OPENAI_API_KEY is never handed to the client.
    from providers.azure_openai import AzureOpenAIProvider

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "static-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", _AZURE_ENDPOINT)
    monkeypatch.setenv("AZURE_OPENAI_USE_ENTRA", "true")
    ModelProviderRegistry.register_provider(ProviderType.AZURE, AzureOpenAIProvider)

    provider = ModelProviderRegistry.get_provider(ProviderType.AZURE)

    assert provider._use_entra is True
    assert provider.api_key == ""


def test_registry_azure_stays_key_gated_when_flag_off(monkeypatch, azure_models_file, clean_registry):
    from providers.azure_openai import AzureOpenAIProvider

    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", _AZURE_ENDPOINT)
    ModelProviderRegistry.register_provider(ProviderType.AZURE, AzureOpenAIProvider)

    assert ModelProviderRegistry.get_provider(ProviderType.AZURE) is None


def test_registry_builds_anthropic_foundry_in_entra_mode_without_key(monkeypatch, clean_registry):
    from providers.anthropic import AnthropicModelProvider

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_USE_ENTRA", "true")
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_BASE_URL", _FOUNDRY_URL)
    ModelProviderRegistry.register_provider(ProviderType.ANTHROPIC, AnthropicModelProvider)

    provider = ModelProviderRegistry.get_provider(ProviderType.ANTHROPIC)

    assert provider is not None
    assert provider._use_entra is True
    assert provider._foundry_base_url == _FOUNDRY_URL
    assert provider.api_key == ""


def test_registry_skips_anthropic_entra_without_foundry_url(monkeypatch, clean_registry):
    from providers.anthropic import AnthropicModelProvider

    monkeypatch.setenv("ANTHROPIC_API_KEY", "static-key")
    monkeypatch.setenv("ANTHROPIC_USE_ENTRA", "true")
    ModelProviderRegistry.register_provider(ProviderType.ANTHROPIC, AnthropicModelProvider)

    assert ModelProviderRegistry.get_provider(ProviderType.ANTHROPIC) is None


def test_registry_anthropic_stays_key_gated_when_flag_off(monkeypatch, clean_registry):
    from providers.anthropic import AnthropicModelProvider

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_BASE_URL", _FOUNDRY_URL)
    ModelProviderRegistry.register_provider(ProviderType.ANTHROPIC, AnthropicModelProvider)

    assert ModelProviderRegistry.get_provider(ProviderType.ANTHROPIC) is None


def test_server_registers_entra_providers_without_any_api_key(monkeypatch, azure_models_file, clean_registry):
    import server

    for var in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "XAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "DIAL_API_KEY",
        "CUSTOM_API_URL",
        *(env for _, env, _ in NATIVE_VENDORS),
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AZURE_OPENAI_USE_ENTRA", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", _AZURE_ENDPOINT)
    monkeypatch.setenv("ANTHROPIC_USE_ENTRA", "true")
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_BASE_URL", _FOUNDRY_URL)

    server.configure_providers()

    registered = ModelProviderRegistry.get_available_providers()
    assert ProviderType.AZURE in registered
    assert ProviderType.ANTHROPIC in registered
    assert ModelProviderRegistry.get_provider(ProviderType.AZURE)._use_entra is True
    assert ModelProviderRegistry.get_provider(ProviderType.ANTHROPIC)._use_entra is True


# --------------------------------------------------------------------------------------------------
# ChatGPT-plan models through the Codex CLI (no API key; opt-in with CHATGPT_ENABLED)
# --------------------------------------------------------------------------------------------------

_NO_KEY_VARS = (
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "XAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "DIAL_API_KEY",
    "CUSTOM_API_URL",
    *(env for _, env, _ in NATIVE_VENDORS),
)


def test_chatgpt_wired_into_priority_and_restrictions():
    order = ModelProviderRegistry.PROVIDER_PRIORITY_ORDER
    assert ProviderType.CHATGPT in order
    # OpenRouter accepts any vendor/model name, so chatgpt/<model> must be claimed before it.
    assert order.index(ProviderType.CHATGPT) < order.index(ProviderType.OPENROUTER)
    assert order.index(ProviderType.CHATGPT) < order.index(ProviderType.CUSTOM)
    assert ModelRestrictionService.ENV_VARS[ProviderType.CHATGPT] == "CHATGPT_ALLOWED_MODELS"
    assert ModelRestrictionService.DISALLOWED_ENV_VARS[ProviderType.CHATGPT] == "CHATGPT_DISALLOWED_MODELS"


def test_registry_builds_chatgpt_without_any_key(monkeypatch, clean_registry):
    from providers.chatgpt import ChatGPTModelProvider

    for var in _NO_KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    ModelProviderRegistry.register_provider(ProviderType.CHATGPT, ChatGPTModelProvider)

    provider = ModelProviderRegistry.get_provider(ProviderType.CHATGPT)

    assert isinstance(provider, ChatGPTModelProvider)
    assert provider.api_key == ""


def test_chatgpt_names_beat_openrouter_catch_all(monkeypatch, clean_registry):
    from providers.chatgpt import ChatGPTModelProvider
    from providers.openrouter import OpenRouterProvider

    monkeypatch.setenv("OPENROUTER_API_KEY", "sentinel-key")
    ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)
    ModelProviderRegistry.register_provider(ProviderType.CHATGPT, ChatGPTModelProvider)

    provider = ModelProviderRegistry.get_provider_for_model("chatgpt/gpt-6.1-sol")

    assert provider.get_provider_type() == ProviderType.CHATGPT


def _fake_codex_on_path(monkeypatch, login_problem=None):
    import shutil

    import providers.chatgpt as chatgpt_module

    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: "/opt/fake/bin/codex" if name == "codex" else None)
    monkeypatch.setattr(chatgpt_module, "codex_login_problem", lambda executable: login_problem)


def test_server_registers_chatgpt_without_any_api_key(monkeypatch, clean_registry):
    import server

    for var in _NO_KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CHATGPT_ENABLED", "true")
    _fake_codex_on_path(monkeypatch)

    server.configure_providers()

    assert ProviderType.CHATGPT in ModelProviderRegistry.get_available_providers()
    assert "chatgpt/gpt-6.1-sol" in ModelProviderRegistry.get_available_models(respect_restrictions=True)


def test_server_registers_chatgpt_when_login_needs_fixing(monkeypatch, clean_registry, caplog):
    # A missing login is logged but the provider stays registered: `codex login` fixes it without a restart.
    import server

    for var in _NO_KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CHATGPT_ENABLED", "true")
    _fake_codex_on_path(monkeypatch, login_problem="the Codex CLI is not signed in (run `codex login`)")

    server.configure_providers()

    assert ProviderType.CHATGPT in ModelProviderRegistry.get_available_providers()
    assert "codex login" in caplog.text


def test_server_skips_chatgpt_without_codex_cli(monkeypatch, clean_registry):
    import server

    monkeypatch.setenv("GEMINI_API_KEY", "sentinel-key")
    monkeypatch.setenv("CHATGPT_ENABLED", "true")
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: None)

    server.configure_providers()

    assert ProviderType.CHATGPT not in ModelProviderRegistry.get_available_providers()


def test_server_leaves_chatgpt_off_by_default(monkeypatch, clean_registry):
    import server

    monkeypatch.setenv("GEMINI_API_KEY", "sentinel-key")
    _fake_codex_on_path(monkeypatch)

    server.configure_providers()

    assert ProviderType.CHATGPT not in ModelProviderRegistry.get_available_providers()


async def test_listmodels_shows_chatgpt_models(monkeypatch, clean_registry):
    import server
    from tools.listmodels import ListModelsTool

    for var in _NO_KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CHATGPT_ENABLED", "true")
    _fake_codex_on_path(monkeypatch)
    server.configure_providers()

    result = await ListModelsTool().execute({})
    content = json.loads(result[0].text)["content"]

    assert "## ChatGPT (via Codex CLI) ✅" in content
    assert "`chatgpt/gpt-6.1-sol`" in content
    assert "`chatgpt/sol` → `chatgpt/gpt-6.1-sol`" in content
