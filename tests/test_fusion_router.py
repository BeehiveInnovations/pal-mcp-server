"""OpenRouter Fusion Router: a meta-router (panel -> analyst -> synthesis) exposed behind a single slug.

Two invariants matter here:
  * it is present and callable by its explicit name/alias, and
  * it is NEVER offered as an auto-mode candidate (``auto_selectable: false``), because it costs ~4-5x a
    single completion and should run only when the user asks for it by name.

The second invariant is enforced by a new ``ModelCapabilities.auto_selectable`` flag that the auto-mode
ranked-summary builder filters on.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from providers.openrouter import OpenRouterProvider
from providers.registries.openrouter import OpenRouterModelRegistry
from providers.shared import ProviderType
from providers.shared.model_capabilities import ModelCapabilities

CONF = Path(__file__).resolve().parents[1] / "conf"

FUSION_MODELS = ["openrouter/fusion"]

# Phase-1 preset SKUs: named Fusion panels selectable by name, sealed panel config in conf `_extras`.
PRESET_SKUS = ["openrouter/fusion-quality", "openrouter/fusion-fast"]


def _or_models():
    return {m["model_name"]: m for m in json.loads((CONF / "openrouter_models.json").read_text())["models"]}


def test_auto_selectable_defaults_true():
    # Every existing model stays auto-selectable; the flag only opts a model OUT.
    caps = ModelCapabilities(provider=ProviderType.OPENROUTER, model_name="x", friendly_name="x")
    assert caps.auto_selectable is True


def test_fusion_entries_present_and_tagged():
    models = _or_models()
    for name in FUSION_MODELS:
        assert name in models, f"{name} missing from openrouter_models.json"
        entry = models[name]
        assert entry["intelligence_score"] == 14, f"{name}: provisional meta-router score must be 14"
        assert entry.get("auto_selectable") is False, f"{name}: must be opted out of auto-selection"
        assert "meta-router" in entry.get("description", "").lower(), f"{name}: description must tag it a meta-router"


def test_fusion_resolvable_by_name_and_alias():
    # Callable by explicit slug and short alias, even though it is not auto-selectable.
    registry = OpenRouterModelRegistry()
    for name in FUSION_MODELS:
        assert registry.resolve(name) is not None, f"{name}: not resolvable by full slug"
    assert registry.resolve("fusion") is not None, "short alias 'fusion' must resolve"
    assert registry.resolve("fusion").auto_selectable is False


def test_ranked_summaries_exclude_non_auto_selectable(monkeypatch):
    # The auto-mode selection guidance (top-N ranked summaries) must skip auto_selectable=False models,
    # so the orchestrator never sees Fusion as a pick-from-here option.
    from tools.chat import ChatTool

    tool = ChatTool()

    keeper = ModelCapabilities(
        provider=ProviderType.OPENROUTER, model_name="keeper-model", friendly_name="Keeper", intelligence_score=12
    )
    fusion = ModelCapabilities(
        provider=ProviderType.OPENROUTER,
        model_name="openrouter/fusion",
        friendly_name="Fusion",
        intelligence_score=17,
        auto_selectable=False,
    )
    monkeypatch.setattr(
        tool,
        "_collect_ranked_capabilities",
        lambda: [(17, "openrouter/fusion", fusion), (12, "keeper-model", keeper)],
    )

    summaries, total, _ = tool._get_ranked_model_summaries()
    joined = " ".join(summaries)
    assert "fusion" not in joined.lower(), "Fusion must not appear in auto-mode ranked summaries"
    assert "keeper-model" in joined
    assert total == 1


# --------------------------------------------------------------------------------------------------
# Phase 1: named preset SKUs (fusion-quality / fusion-fast) + cost/injection seals
# --------------------------------------------------------------------------------------------------


def test_preset_skus_present_and_sealed():
    models = _or_models()
    for name in PRESET_SKUS:
        assert name in models, f"{name} missing from openrouter_models.json"
        entry = models[name]
        assert entry.get("auto_selectable") is False, f"{name}: preset SKU must be opted out of auto-selection"
        assert "meta-router" in entry.get("description", "").lower(), f"{name}: must be tagged a meta-router"
        assert isinstance(entry.get("fusion"), dict), f"{name}: must carry a sealed `fusion` panel block"

    # Quality pins an explicit panel; fast rides the vendor 'general-fast' preset.
    assert models["openrouter/fusion-quality"]["fusion"].get("analysis_models"), "quality SKU needs a pinned panel"
    assert models["openrouter/fusion-fast"]["fusion"].get("preset") == "general-fast"


def test_registry_exposes_fusion_extras():
    registry = OpenRouterModelRegistry()
    # `fusion` is a whitelisted non-capability key, so a conf entry carrying it loads without error...
    assert "fusion" in registry._extra_keys()
    # ...and the sealed block is retrievable per canonical model name.
    quality = registry.get_entry("openrouter/fusion-quality")
    assert quality and quality.get("fusion", {}).get("analysis_models")
    fast = registry.get_entry("openrouter/fusion-fast")
    assert fast and fast.get("fusion", {}).get("preset") == "general-fast"


def _provider():
    prov = OpenRouterProvider(api_key="test-key")
    return prov


def test_augment_injects_sealed_plugins():
    prov = _provider()

    quality = {"model": "openrouter/fusion-quality"}
    prov._augment_completion_params(quality, "openrouter/fusion-quality")
    plugins = quality.get("extra_body", {}).get("plugins")
    assert plugins and plugins[0]["id"] == "fusion"
    assert plugins[0]["analysis_models"], "quality panel must inject analysis_models"
    assert len(plugins[0]["analysis_models"]) <= 8, "hard fan-out ceiling (cost seal)"
    # Wire model must be the real Fusion slug, not our internal SKU alias.
    assert quality["model"] == "openrouter/fusion"

    fast = {"model": "openrouter/fusion-fast"}
    prov._augment_completion_params(fast, "openrouter/fusion-fast")
    assert fast["extra_body"]["plugins"][0]["preset"] == "general-fast"
    assert fast["model"] == "openrouter/fusion"

    # A model with no fusion block (bare fusion default, and any normal model) gets NO body injection.
    bare = {}
    prov._augment_completion_params(bare, "openrouter/fusion")
    assert "extra_body" not in bare
    normal = {}
    prov._augment_completion_params(normal, "deepseek/deepseek-v4-flash")
    assert "extra_body" not in normal


def test_injection_seal_ignores_caller_supplied_panel():
    # The panel MUST come only from trusted conf; a caller-supplied plugins/extra_body kwarg (as could be
    # smuggled via prompt-injected tool output) must never reach the request body.
    prov = _provider()

    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"), finish_reason="stop")],
            model="anthropic/claude-opus-5",
            id="x",
            created=0,
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = fake_create
    prov._client = mock_client  # bypass the lazy `client` property

    prov.generate_content(
        prompt="hi",
        model_name="openrouter/fusion-quality",
        temperature=0.3,
        plugins=[{"id": "fusion", "analysis_models": ["attacker/evil-model"]}],
        extra_body={"plugins": [{"id": "fusion", "analysis_models": ["attacker/evil-model"]}]},
    )

    assert "plugins" not in captured, "caller plugins kwarg must not be forwarded to the request"
    assert captured.get("model") == "openrouter/fusion", "SKU alias must resolve to the real wire slug"
    sealed = captured.get("extra_body", {}).get("plugins", [{}])[0].get("analysis_models", [])
    assert "attacker/evil-model" not in sealed, "injection seal breached: caller panel reached the body"
    assert sealed, "sealed conf panel should still be present"


def test_cost_receipt_captures_usage_cost():
    # Cost seal (receipt): OpenRouter reports a per-call dollar cost; it must surface in usage so spend is
    # auditable. Token-only responses (no cost field) stay unaffected.
    prov = _provider()

    with_cost = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.0039)
    usage = prov._extract_usage(SimpleNamespace(usage=with_cost))
    assert usage["cost"] == 0.0039
    assert usage["total_tokens"] == 15

    without_cost = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    usage2 = prov._extract_usage(SimpleNamespace(usage=without_cost))
    assert "cost" not in usage2
