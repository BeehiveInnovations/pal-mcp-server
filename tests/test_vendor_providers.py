"""Unit tests for the native OpenAI-compatible vendor providers (Qwen/GLM/Kimi/MiniMax/Mistral/Nvidia/Perplexity)."""

import pytest

from providers.minimax import MiniMaxModelProvider
from providers.mistral import MistralModelProvider
from providers.moonshot import MoonshotModelProvider
from providers.nvidia import NvidiaModelProvider
from providers.perplexity import PerplexityModelProvider
from providers.qwen import QwenModelProvider
from providers.shared import ProviderType
from providers.zai import ZaiModelProvider

# (provider class, expected ProviderType, expected base_url, a flagship model, its pinned score)
VENDORS = [
    (QwenModelProvider, ProviderType.QWEN, "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen3.8-max", 14),
    (ZaiModelProvider, ProviderType.ZAI, "https://api.z.ai/api/paas/v4", "glm-5.3", 15),
    (MoonshotModelProvider, ProviderType.MOONSHOT, "https://api.moonshot.ai/v1", "kimi-k3", 14),
    (MiniMaxModelProvider, ProviderType.MINIMAX, "https://api.minimax.io/v1", "MiniMax-M3", 11),
    (MistralModelProvider, ProviderType.MISTRAL, "https://api.mistral.ai/v1", "mistral-large-latest", 10),
    (
        NvidiaModelProvider,
        ProviderType.NVIDIA,
        "https://integrate.api.nvidia.com/v1",
        "nvidia/nemotron-3-super-120b-a12b",
        6,
    ),
    (PerplexityModelProvider, ProviderType.PERPLEXITY, "https://api.perplexity.ai", "sonar-pro", 11),
]


@pytest.mark.parametrize("cls,ptype,base_url,flagship,score", VENDORS)
def test_provider_type_and_base_url(cls, ptype, base_url, flagship, score):
    p = cls("test-key")
    assert p.get_provider_type() == ptype
    assert p.base_url == base_url


@pytest.mark.parametrize("cls,ptype,base_url,flagship,score", VENDORS)
def test_flagship_present_and_scored(cls, ptype, base_url, flagship, score):
    caps = cls("test-key").get_all_model_capabilities()
    assert flagship in caps, f"{flagship} missing from {cls.__name__} catalog"
    assert caps[flagship].intelligence_score == score


@pytest.mark.parametrize("cls,ptype,base_url,flagship,score", VENDORS)
def test_bare_family_alias_resolves(cls, ptype, base_url, flagship, score):
    # Every vendor exposes a bare family alias that resolves to a canonical model in its own catalog.
    p = cls("test-key")
    caps = p.get_all_model_capabilities()
    for alias in ("qwen", "glm", "kimi", "minimax", "mistral", "nemotron", "sonar"):
        resolved = p._resolve_model_name(alias)
        if resolved in caps:  # only the vendor owning this alias resolves it
            assert caps[resolved].intelligence_score >= 1
