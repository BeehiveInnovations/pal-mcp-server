from unittest.mock import Mock

from providers.base import ProviderType
from providers.deepseek import DeepSeekModelProvider
from providers.registry import ModelProviderRegistry


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

    def test_generate_content_with_reasoning(self):
        """Test DeepSeek reasoner model with reasoning_content extraction."""
        provider = DeepSeekModelProvider(api_key="test-key")
        mock_client = Mock()

        # Create a mock message with reasoning_content attribute
        mock_message = Mock(content="Final answer", reasoning_content="Thinking process...")
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=mock_message, finish_reason="stop")],
            model="deepseek-reasoner",
            id="id",
            created=123,
            usage=Mock(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )
        provider._client = mock_client

        response = provider.generate_content(prompt="test", model_name="deepseek-reasoner")

        # Should display reasoning + answer
        expected_content = "**Reasoning Process:**\n\nThinking process...\n\n**Final Answer:**\n\nFinal answer"
        assert response.content == expected_content
        assert response.model_name == "deepseek-reasoner"
        assert response.provider == ProviderType.DEEPSEEK

        # Check metadata
        assert response.metadata["has_reasoning"] is True
        assert response.metadata["reasoning_content"] == "Thinking process..."
        assert response.metadata["final_answer"] == "Final answer"

    def test_generate_content_without_reasoning(self):
        """Test DeepSeek reasoner model without reasoning_content."""
        provider = DeepSeekModelProvider(api_key="test-key")
        mock_client = Mock()

        # Create a mock message without reasoning_content (fallback case)
        mock_message = Mock(content="Direct answer")
        # Simulate missing reasoning_content attribute
        mock_message.reasoning_content = None
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=mock_message, finish_reason="stop")],
            model="deepseek-reasoner",
            id="id",
            created=123,
            usage=Mock(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )
        provider._client = mock_client

        response = provider.generate_content(prompt="test", model_name="deepseek-reasoner")

        # Should display only the answer (no reasoning)
        assert response.content == "Direct answer"
        assert response.model_name == "deepseek-reasoner"
        assert response.provider == ProviderType.DEEPSEEK

        # Check metadata
        assert response.metadata["has_reasoning"] is False
        assert response.metadata["reasoning_content"] == ""
        assert response.metadata["final_answer"] == "Direct answer"

    def test_supports_thinking_mode(self):
        """Test thinking mode support detection."""
        provider = DeepSeekModelProvider(api_key="test-key")

        # deepseek-reasoner should support thinking mode
        assert provider.supports_thinking_mode("deepseek-reasoner") is True
        assert provider.supports_thinking_mode("reasoner") is True

        # deepseek-chat should not support thinking mode
        assert provider.supports_thinking_mode("deepseek-chat") is False
        assert provider.supports_thinking_mode("chat") is False
