"""Deferred LIVE provider-path smoke tests for the native open-model providers.

Each makes exactly one tiny real API call and is:
  * marked ``integration`` -> excluded from the default ``pytest -m "not integration"`` run, and
  * ``skipif`` its ``*_API_KEY`` is unset -> the ones we lack keys for are skipped, not absent.

So there is a real, collectable test for every native provider; it runs the moment a key exists
(``pytest -m integration``) and is otherwise an explicit, auditable skip. `test_native_provider_wiring`
holds a census test that fails if any native provider lacks an entry here.
"""

import os

import pytest

from providers.shared import ProviderType

# (ProviderType, env var, provider module, a cheap model/alias to ping)
LIVE_VENDORS = [
    (ProviderType.DEEPSEEK, "DEEPSEEK_API_KEY", "providers.deepseek", "deepseek-v4.1-flash"),
    (ProviderType.QWEN, "DASHSCOPE_API_KEY", "providers.qwen", "qwen-flash"),
    (ProviderType.ZAI, "ZAI_API_KEY", "providers.zai", "glm-5.3"),
    (ProviderType.MOONSHOT, "MOONSHOT_API_KEY", "providers.moonshot", "kimi-k3"),
    (ProviderType.MINIMAX, "MINIMAX_API_KEY", "providers.minimax", "MiniMax-M3"),
    (ProviderType.MISTRAL, "MISTRAL_API_KEY", "providers.mistral", "mistral-small-latest"),
    (ProviderType.NVIDIA, "NVIDIA_API_KEY", "providers.nvidia", "nemotron-nano"),
    (ProviderType.PERPLEXITY, "PERPLEXITY_API_KEY", "providers.perplexity", "sonar"),
]


def _provider_class(module_name):
    from importlib import import_module

    return next(v for k, v in vars(import_module(module_name)).items() if k.endswith("ModelProvider"))


@pytest.mark.integration
@pytest.mark.parametrize("ptype,env_var,module,model", LIVE_VENDORS)
def test_native_provider_live_smoke(ptype, env_var, module, model):
    key = os.environ.get(env_var)
    if not key:
        pytest.skip(f"{env_var} not set - deferred live test for {ptype.value}")
    provider = _provider_class(module)(key)
    resp = provider.generate_content(
        prompt="Reply with exactly one word: pong", model_name=model, temperature=0.0, max_output_tokens=64
    )
    assert resp is not None
    assert resp.provider == ptype
    assert resp.usage.get("total_tokens", 0) > 0  # a real round-trip happened


@pytest.mark.integration
# Cheap, current models from the newest catalog additions. Replace a model here when it is retired.
@pytest.mark.parametrize("model", ["deepseek-v4.1-flash", "mimo-v2.6-flash"])
def test_openrouter_new_models_live_smoke(model):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set - deferred OpenRouter live test")
    from providers.openrouter import OpenRouterProvider

    resp = OpenRouterProvider(key).generate_content(
        prompt="Reply with exactly one word: pong", model_name=model, temperature=0.0, max_output_tokens=64
    )
    assert resp is not None
    assert resp.usage.get("total_tokens", 0) > 0
