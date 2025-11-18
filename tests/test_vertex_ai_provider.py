"""Tests for Vertex AI provider implementation."""

from unittest.mock import MagicMock, patch

import pytest

from providers.base import ProviderType
from providers.vertex_ai import VertexAIProvider


class TestVertexAIProvider:
    """Test Vertex AI provider functionality."""

    def test_initialization(self):
        """Test provider initialization."""
        provider = VertexAIProvider(project_id="test-project", region="us-central1")
        assert provider.project_id == "test-project"
        assert provider.region == "us-central1"
        assert provider.get_provider_type() == ProviderType.VERTEX_AI

    def test_model_validation(self):
        """Test model name validation."""
        provider = VertexAIProvider(project_id="test-project")

        # Test valid models
        assert provider.validate_model_name("gemini-2.5-pro") is True
        assert provider.validate_model_name("gemini-2.5-flash") is True
        assert provider.validate_model_name("gemini-2.5-flash-lite") is True
        assert provider.validate_model_name("gemini-2.0-flash") is True
        assert provider.validate_model_name("vertex-pro") is True  # alias
        assert provider.validate_model_name("vertex-flash") is True  # alias
        assert provider.validate_model_name("vertex-lite") is True  # alias

        # Test invalid model
        assert provider.validate_model_name("invalid-model") is False

    def test_resolve_model_name(self):
        """Test model name resolution."""
        provider = VertexAIProvider(project_id="test-project")

        # Test shorthand resolution
        assert provider._resolve_model_name("vertex-pro") == "gemini-2.5-pro"
        assert provider._resolve_model_name("vertex-flash") == "gemini-2.5-flash"
        assert provider._resolve_model_name("vertex-lite") == "gemini-2.5-flash-lite-preview-06-17"
        assert provider._resolve_model_name("vertex-2.0-flash") == "gemini-2.0-flash"

        # Test that gemini-2.5-flash-lite also maps to the preview version
        assert provider._resolve_model_name("gemini-2.5-flash-lite") == "gemini-2.5-flash-lite-preview-06-17"

        # Test full name passthrough
        assert provider._resolve_model_name("gemini-2.5-pro") == "gemini-2.5-pro"

    @patch("providers.vertex_ai.google.auth.default")
    def test_get_capabilities(self, mock_auth):
        """Test getting model capabilities."""
        # Mock Google auth
        mock_credentials = MagicMock()
        mock_auth.return_value = (mock_credentials, "test-project")

        provider = VertexAIProvider(project_id="test-project")

        capabilities = provider.get_capabilities("vertex-pro")
        assert capabilities.model_name == "gemini-2.5-pro"
        assert capabilities.friendly_name == "Vertex AI"
        assert capabilities.context_window == 1_048_576
        assert capabilities.provider == ProviderType.VERTEX_AI
        assert capabilities.supports_extended_thinking is True
        assert capabilities.supports_images is True

        # Test temperature range (inherited from Gemini provider)
        assert capabilities.temperature_constraint.get_default() == 0.3
        assert capabilities.temperature_constraint.min_temp == 0.0
        assert capabilities.temperature_constraint.max_temp == 2.0

    @patch("providers.vertex_ai.google.auth.default")
    def test_credentials_error(self, mock_auth):
        """Test error when credentials cannot be initialized."""
        mock_auth.side_effect = Exception("Credentials error")

        provider = VertexAIProvider(project_id="test-project")

        with pytest.raises(
            ValueError, match="An unexpected error occurred while initializing Google Cloud credentials"
        ):
            _ = provider.credentials

    def test_list_models(self):
        """Test listing available models."""
        provider = VertexAIProvider(project_id="test-project")

        models = provider.list_models(respect_restrictions=False, include_aliases=False)

        # Should include actual models but not aliases
        assert "gemini-2.5-pro" in models
        assert "gemini-2.5-flash" in models
        assert "gemini-2.5-flash-lite-preview-06-17" in models
        assert "gemini-2.0-flash" in models

        # Should not include aliases
        assert "gemini-2.5-flash-lite" not in models

        # Should not include aliases
        assert "vertex-pro" not in models
        assert "vertex-flash" not in models

    def test_list_all_known_models(self):
        """Test listing all known models including aliases."""
        provider = VertexAIProvider(project_id="test-project")

        models = provider.list_all_known_models()

        # Should include both actual models and aliases
        assert "gemini-2.5-pro" in models
        assert "vertex-pro" in models
        assert "vertex-flash" in models

    def test_supports_thinking_mode(self):
        """Test checking thinking mode support."""
        provider = VertexAIProvider(project_id="test-project")

        # Models that support thinking
        assert provider.supports_thinking_mode("gemini-2.5-pro") is True
        assert provider.supports_thinking_mode("vertex-pro") is True

        # Models that support thinking (inherited from parent)
        assert provider.supports_thinking_mode("gemini-2.0-flash") is True

    def test_count_tokens(self):
        """Test token counting estimation (inherited from Gemini provider)."""
        provider = VertexAIProvider(project_id="test-project")

        # Test estimation (inherited from Gemini: chars // 4)
        assert provider.count_tokens("hello", "gemini-2.5-pro") == 1  # 5 chars // 4 = 1
        assert provider.count_tokens("hello world", "gemini-2.5-pro") == 2  # 11 chars // 4 = 2
        assert provider.count_tokens("a" * 100, "gemini-2.5-pro") == 25  # 100 chars // 4 = 25
        assert provider.count_tokens("a", "gemini-2.5-pro") == 0  # 1 char // 4 = 0
