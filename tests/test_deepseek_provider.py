from unittest.mock import Mock

from providers.deepseek import DeepSeekModelProvider
from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType


class TestDeepSeekProvider:
    def test_provider_initialization(self):
        provider = DeepSeekModelProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.DEEPSEEK
        assert provider.base_url == "https://api.deepseek.com"

    def test_registry_uses_env_base_url(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://custom.local")
        ModelProviderRegistry.register_provider(ProviderType.DEEPSEEK, DeepSeekModelProvider)
        provider = ModelProviderRegistry.get_provider(ProviderType.DEEPSEEK, force_new=True)
        assert provider.base_url == "https://custom.local"
        ModelProviderRegistry.unregister_provider(ProviderType.DEEPSEEK)

    def test_get_capabilities(self):
        provider = DeepSeekModelProvider(api_key="test-key")
        caps = provider.get_capabilities("deepseek-chat")
        assert caps.provider == ProviderType.DEEPSEEK
        assert caps.model_name == "deepseek-chat"

    def test_model_shorthand_resolution(self):
        provider = DeepSeekModelProvider(api_key="test-key")
        assert provider.validate_model_name("chat")
        caps = provider.get_capabilities("chat")
        assert caps.model_name == "deepseek-chat"

    def test_generate_content(self):
        provider = DeepSeekModelProvider(api_key="test-key")
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="hello"), finish_reason="stop")],
            model="deepseek-chat",
            id="id",
            created=123,
            usage=Mock(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )
        provider._client = mock_client

        response = provider.generate_content(prompt="hi", model_name="chat", system_prompt="system")
        assert response.content == "hello"
        assert response.model_name == "deepseek-chat"
        assert response.provider == ProviderType.DEEPSEEK
