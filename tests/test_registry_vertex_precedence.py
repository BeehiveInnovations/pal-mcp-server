"""Tests for Vertex AI / Gemini API precedence logic in ModelProviderRegistry."""

from unittest.mock import MagicMock, patch

import pytest

from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType


class TestVertexPrecedence:
    """Test Vertex AI precedence logic in registry."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset registry before each test."""
        ModelProviderRegistry.reset_for_testing()

    def test_has_vertex_credentials_valid(self, monkeypatch):
        """Test _has_vertex_credentials with valid project ID."""
        monkeypatch.setenv("VERTEX_PROJECT_ID", "my-project-123")
        assert ModelProviderRegistry._has_vertex_credentials() is True

    def test_has_vertex_credentials_placeholder(self, monkeypatch):
        """Test _has_vertex_credentials rejects placeholder value."""
        monkeypatch.setenv("VERTEX_PROJECT_ID", "your_vertex_project_id_here")
        assert ModelProviderRegistry._has_vertex_credentials() is False

    def test_has_vertex_credentials_empty(self, monkeypatch):
        """Test _has_vertex_credentials with empty string."""
        monkeypatch.setenv("VERTEX_PROJECT_ID", "")
        assert ModelProviderRegistry._has_vertex_credentials() is False

    def test_has_vertex_credentials_whitespace(self, monkeypatch):
        """Test _has_vertex_credentials with whitespace-only value."""
        monkeypatch.setenv("VERTEX_PROJECT_ID", "   ")
        assert ModelProviderRegistry._has_vertex_credentials() is False

    def test_has_vertex_credentials_not_set(self, monkeypatch):
        """Test _has_vertex_credentials when not set."""
        monkeypatch.delenv("VERTEX_PROJECT_ID", raising=False)
        assert ModelProviderRegistry._has_vertex_credentials() is False

    def test_has_gemini_api_key_valid(self, monkeypatch):
        """Test _has_gemini_api_key with valid key."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        assert ModelProviderRegistry._has_gemini_api_key() is True

    def test_has_gemini_api_key_empty(self, monkeypatch):
        """Test _has_gemini_api_key with empty string."""
        monkeypatch.setenv("GEMINI_API_KEY", "")
        assert ModelProviderRegistry._has_gemini_api_key() is False

    def test_has_gemini_api_key_whitespace(self, monkeypatch):
        """Test _has_gemini_api_key with whitespace-only value."""
        monkeypatch.setenv("GEMINI_API_KEY", "   ")
        assert ModelProviderRegistry._has_gemini_api_key() is False

    def test_has_gemini_api_key_not_set(self, monkeypatch):
        """Test _has_gemini_api_key when not set."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert ModelProviderRegistry._has_gemini_api_key() is False

    @patch.object(ModelProviderRegistry, "get_provider")
    def test_configure_gemini_access_vertex_only(self, mock_get_provider, monkeypatch):
        """Test _configure_gemini_access when only Vertex credentials exist."""
        monkeypatch.setenv("VERTEX_PROJECT_ID", "test-project")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        # Mock provider
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        result = ModelProviderRegistry._configure_gemini_access()
        assert result == ProviderType.VERTEX_AI
        mock_get_provider.assert_called_once_with(ProviderType.VERTEX_AI)

    @patch.object(ModelProviderRegistry, "get_provider")
    def test_configure_gemini_access_api_only(self, mock_get_provider, monkeypatch):
        """Test _configure_gemini_access when only Gemini API key exists."""
        monkeypatch.delenv("VERTEX_PROJECT_ID", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        # Mock provider
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        result = ModelProviderRegistry._configure_gemini_access()
        assert result == ProviderType.GOOGLE
        mock_get_provider.assert_called_once_with(ProviderType.GOOGLE)

    @patch.object(ModelProviderRegistry, "get_provider")
    def test_configure_gemini_access_both_vertex_precedence(self, mock_get_provider, monkeypatch, caplog):
        """Test _configure_gemini_access when both credentials exist - Vertex takes precedence."""
        monkeypatch.setenv("VERTEX_PROJECT_ID", "test-project")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        # Mock provider
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        with caplog.at_level("INFO"):
            result = ModelProviderRegistry._configure_gemini_access()

        assert result == ProviderType.VERTEX_AI
        # Should log that Gemini API key is ignored
        assert "Gemini API key detected but ignored" in caplog.text
        mock_get_provider.assert_called_once_with(ProviderType.VERTEX_AI)

    def test_configure_gemini_access_neither(self, monkeypatch, caplog):
        """Test _configure_gemini_access when neither credential exists."""
        monkeypatch.delenv("VERTEX_PROJECT_ID", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with caplog.at_level("INFO"):
            result = ModelProviderRegistry._configure_gemini_access()

        assert result is None
        # Should log that no Gemini access is configured
        assert "No Gemini access configured" in caplog.text

    @patch.object(ModelProviderRegistry, "get_provider")
    def test_configure_gemini_access_vertex_provider_unavailable(self, mock_get_provider, monkeypatch):
        """Test _configure_gemini_access when Vertex credentials exist but provider unavailable."""
        monkeypatch.setenv("VERTEX_PROJECT_ID", "test-project")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        # Mock provider returns None (unavailable)
        mock_get_provider.return_value = None

        result = ModelProviderRegistry._configure_gemini_access()
        # Should fall through to return None
        assert result is None

    @patch.object(ModelProviderRegistry, "get_provider")
    def test_configure_gemini_access_both_but_vertex_unavailable_fallback_to_gemini(
        self, mock_get_provider, monkeypatch
    ):
        """Test fallback to Gemini API when Vertex credentials exist but provider unavailable."""
        monkeypatch.setenv("VERTEX_PROJECT_ID", "test-project")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        # Mock: Vertex provider unavailable, Gemini provider available
        def get_provider_side_effect(provider_type):
            if provider_type == ProviderType.VERTEX_AI:
                return None
            elif provider_type == ProviderType.GOOGLE:
                return MagicMock()
            return None

        mock_get_provider.side_effect = get_provider_side_effect

        result = ModelProviderRegistry._configure_gemini_access()
        assert result == ProviderType.GOOGLE
