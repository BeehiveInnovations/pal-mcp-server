"""Unit tests for the native DeepSeek provider (OpenAI-compatible direct API)."""

from providers.deepseek import DeepSeekModelProvider
from providers.shared import ProviderType


def _provider():
    return DeepSeekModelProvider("test-key")


class TestDeepSeekCatalog:
    def test_provider_type_and_base_url(self):
        p = _provider()
        assert p.get_provider_type() == ProviderType.DEEPSEEK
        assert p.base_url == "https://api.deepseek.com"
        assert p.FRIENDLY_NAME == "DeepSeek"

    def test_models_and_scores(self):
        caps = _provider().get_all_model_capabilities()
        # Scores pinned to the OpenRouter mirrors, anchored to the current AA Index.
        assert caps["deepseek-v4.1-flash"].intelligence_score == 13
        assert caps["deepseek-v4-pro"].intelligence_score == 12
        assert caps["deepseek-v4-flash"].intelligence_score == 12
        assert caps["deepseek-reasoner"].intelligence_score == 11
        # Experimental vision model scored below stable flash, and multimodal-capable.
        assert caps["deepseek-v4-flash-vision-exp"].intelligence_score == 12
        assert caps["deepseek-v4-flash-vision-exp"].supports_images is True
        # The non-vision text models must NOT claim images.
        assert caps["deepseek-v4-pro"].context_window == 1048576

    def test_alias_resolution(self):
        p = _provider()
        assert p._resolve_model_name("deepseek") == "deepseek-v4.1-flash"
        assert p._resolve_model_name("reasoner") == "deepseek-reasoner"
        assert p._resolve_model_name("deepseek-r1") == "deepseek-reasoner"
        assert p._resolve_model_name("DEEPSEEK") == "deepseek-v4.1-flash"  # case-insensitive
