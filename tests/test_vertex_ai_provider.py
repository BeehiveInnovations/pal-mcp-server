"""Tests for Vertex AI provider implementation."""

from unittest.mock import MagicMock, patch

import pytest

from providers.shared import ProviderType
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
        """Test model name validation using canonical Gemini names."""
        provider = VertexAIProvider(project_id="test-project")

        # Test valid models (inherited from Gemini provider)
        assert provider.validate_model_name("gemini-2.5-pro") is True
        assert provider.validate_model_name("gemini-2.5-flash") is True
        assert provider.validate_model_name("gemini-2.0-flash-lite") is True
        assert provider.validate_model_name("gemini-2.0-flash") is True
        assert provider.validate_model_name("gemini-3-pro-preview") is True

        # Test Gemini aliases (inherited from parent)
        assert provider.validate_model_name("pro") is True  # alias for gemini-3-pro-preview
        assert provider.validate_model_name("flash") is True  # alias for gemini-2.5-flash

        # Test invalid model
        assert provider.validate_model_name("invalid-model") is False

    def test_resolve_model_name(self):
        """Test model name resolution for Gemini aliases."""
        provider = VertexAIProvider(project_id="test-project")

        # Test Gemini alias resolution (inherited from parent)
        assert provider._resolve_model_name("pro") == "gemini-3-pro-preview"
        assert provider._resolve_model_name("flash") == "gemini-2.5-flash"
        assert provider._resolve_model_name("flash2") == "gemini-2.0-flash"

        # Test canonical names pass through unchanged
        assert provider._resolve_model_name("gemini-2.5-pro") == "gemini-2.5-pro"
        assert provider._resolve_model_name("gemini-2.0-flash-lite") == "gemini-2.0-flash-lite"

    @patch("providers.vertex_ai.google.auth.default")
    def test_get_capabilities(self, mock_auth):
        """Test getting model capabilities using canonical names."""
        # Mock Google auth
        mock_credentials = MagicMock()
        mock_auth.return_value = (mock_credentials, "test-project")

        provider = VertexAIProvider(project_id="test-project")

        # Test with canonical Gemini model name
        capabilities = provider.get_capabilities("gemini-2.5-pro")
        assert capabilities.model_name == "gemini-2.5-pro"
        assert capabilities.friendly_name == "Vertex AI"  # Overridden for Vertex
        assert capabilities.context_window == 1_048_576
        assert capabilities.provider == ProviderType.VERTEX_AI  # Overridden for Vertex
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

        # Should include actual models inherited from Gemini provider
        assert "gemini-2.5-pro" in models
        assert "gemini-2.5-flash" in models
        assert "gemini-2.0-flash-lite" in models
        assert "gemini-2.0-flash" in models
        assert "gemini-3-pro-preview" in models

        # Should not include Vertex-specific aliases
        assert "vertex-pro" not in models
        assert "vertex-flash" not in models
        assert "vertex-lite" not in models

    def test_list_all_known_models(self):
        """Test listing all known models including aliases."""
        provider = VertexAIProvider(project_id="test-project")

        models = provider.list_all_known_models()

        # Should include actual models and their Gemini aliases (inherited from parent)
        assert "gemini-2.5-pro" in models
        assert "gemini-2.5-flash" in models
        assert "gemini-3-pro-preview" in models
        assert "pro" in models  # Gemini alias
        assert "flash" in models  # Gemini alias

    def test_supports_thinking_mode(self):
        """Test checking thinking mode support using canonical names."""
        provider = VertexAIProvider(project_id="test-project")

        # Models that support thinking (using canonical names)
        assert provider.supports_thinking_mode("gemini-2.5-pro") is True
        assert provider.supports_thinking_mode("gemini-3-pro-preview") is True
        assert provider.supports_thinking_mode("gemini-2.0-flash") is True

        # Test with Gemini aliases (inherited from parent)
        assert provider.supports_thinking_mode("pro") is True

    # Note: count_tokens() test removed - method inherited from base ModelProvider
    # Base class tests in test_base.py cover token counting behavior
