"""
Tests for utils/client_info.py

This module tests the client information utilities used for extracting
and formatting MCP client information.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from utils.client_info import (
    CLIENT_NAME_MAPPINGS,
    DEFAULT_FRIENDLY_NAME,
    format_client_info,
    get_cached_client_info,
    get_client_friendly_name,
    get_client_info_from_context,
    get_friendly_name,
    log_client_info,
)


class TestGetFriendlyName:
    """Tests for get_friendly_name function."""

    def test_empty_string_returns_default(self):
        """Empty string should return default friendly name."""
        assert get_friendly_name("") == DEFAULT_FRIENDLY_NAME

    def test_none_returns_default(self):
        """None should return default friendly name."""
        assert get_friendly_name(None) == DEFAULT_FRIENDLY_NAME

    def test_claude_variants(self):
        """Various Claude client names should return 'Claude'."""
        claude_names = [
            "claude-ai",
            "Claude-AI",
            "CLAUDE-AI",
            "claude",
            "Claude",
            "claude-desktop",
            "Claude-Desktop",
            "claude-code",
            "anthropic",
            "Anthropic-Client",
        ]
        for name in claude_names:
            assert get_friendly_name(name) == "Claude", f"Failed for: {name}"

    def test_gemini_variants(self):
        """Various Gemini client names should return 'Gemini'."""
        gemini_names = [
            "gemini-cli-mcp-client",
            "gemini-cli",
            "Gemini-CLI",
            "gemini",
            "google",
            "Google-AI",
        ]
        for name in gemini_names:
            assert get_friendly_name(name) == "Gemini", f"Failed for: {name}"

    def test_cursor_client(self):
        """Cursor client should return 'Cursor'."""
        assert get_friendly_name("cursor") == "Cursor"
        assert get_friendly_name("Cursor-IDE") == "Cursor"

    def test_vscode_client(self):
        """VS Code client should return 'VS Code'."""
        assert get_friendly_name("vscode") == "VS Code"
        assert get_friendly_name("VSCode-Extension") == "VS Code"

    def test_codeium_client(self):
        """Codeium client should return 'Codeium'."""
        assert get_friendly_name("codeium") == "Codeium"

    def test_copilot_client(self):
        """GitHub Copilot client should return 'GitHub Copilot'."""
        assert get_friendly_name("copilot") == "GitHub Copilot"
        assert get_friendly_name("github-copilot") == "GitHub Copilot"

    def test_mcp_client(self):
        """Generic MCP client should return 'MCP Client'."""
        assert get_friendly_name("mcp-client") == "MCP Client"

    def test_test_client(self):
        """Test client should return 'Test Client'."""
        assert get_friendly_name("test-client") == "Test Client"

    def test_unknown_client_returns_default(self):
        """Unknown client names should return default."""
        unknown_names = ["unknown-client", "random-app", "my-custom-tool"]
        for name in unknown_names:
            assert get_friendly_name(name) == DEFAULT_FRIENDLY_NAME, f"Failed for: {name}"

    def test_case_insensitive_matching(self):
        """Matching should be case-insensitive."""
        assert get_friendly_name("CLAUDE") == "Claude"
        assert get_friendly_name("GEMINI") == "Gemini"
        assert get_friendly_name("CuRsOr") == "Cursor"

    def test_partial_matching(self):
        """Partial matches should work (key contained in client name)."""
        assert get_friendly_name("my-claude-extension") == "Claude"
        assert get_friendly_name("gemini-custom-build") == "Gemini"


class TestFormatClientInfo:
    """Tests for format_client_info function."""

    def test_none_returns_default(self):
        """None client_info should return default friendly name."""
        assert format_client_info(None) == DEFAULT_FRIENDLY_NAME

    def test_empty_dict_returns_default(self):
        """Empty dict should return default friendly name."""
        assert format_client_info({}) == DEFAULT_FRIENDLY_NAME

    def test_with_friendly_name(self):
        """Should use friendly_name when use_friendly_name=True."""
        client_info = {
            "name": "claude-ai",
            "version": "1.0.0",
            "friendly_name": "Claude",
        }
        assert format_client_info(client_info, use_friendly_name=True) == "Claude"

    def test_without_friendly_name_flag(self):
        """Should use raw name with version when use_friendly_name=False."""
        client_info = {
            "name": "claude-ai",
            "version": "1.0.0",
            "friendly_name": "Claude",
        }
        assert format_client_info(client_info, use_friendly_name=False) == "claude-ai v1.0.0"

    def test_without_version(self):
        """Should handle missing version gracefully."""
        client_info = {
            "name": "claude-ai",
            "friendly_name": "Claude",
        }
        assert format_client_info(client_info, use_friendly_name=True) == "Claude"
        assert format_client_info(client_info, use_friendly_name=False) == "claude-ai"

    def test_fallback_to_name_when_no_friendly_name(self):
        """Should fallback to name if friendly_name is missing."""
        client_info = {"name": "custom-client"}
        result = format_client_info(client_info, use_friendly_name=True)
        assert result == "custom-client"


class TestGetClientInfoFromContext:
    """Tests for get_client_info_from_context function."""

    def setup_method(self):
        """Reset the cache before each test."""
        import utils.client_info as client_info_module

        client_info_module._client_info_cache = None

    def test_none_server_returns_none(self):
        """None server should return None."""
        assert get_client_info_from_context(None) is None

    def test_server_without_request_context(self):
        """Server without request_context should return None."""
        server = MagicMock(spec=[])  # No attributes
        assert get_client_info_from_context(server) is None

    def test_server_with_none_request_context(self):
        """Server with None request_context should return None."""
        server = MagicMock()
        server.request_context = None
        assert get_client_info_from_context(server) is None

    def test_request_context_without_session(self):
        """Request context without session should return None."""
        server = MagicMock()
        server.request_context = MagicMock(spec=[])  # No session attribute
        assert get_client_info_from_context(server) is None

    def test_session_without_client_params(self):
        """Session without _client_params should return None."""
        server = MagicMock()
        server.request_context.session = MagicMock(spec=[])  # No _client_params
        assert get_client_info_from_context(server) is None

    def test_successful_extraction(self):
        """Should successfully extract client info from valid server context."""
        # Build mock chain
        server = MagicMock()
        server.request_context.session._client_params.clientInfo.name = "claude-ai"
        server.request_context.session._client_params.clientInfo.version = "1.0.0"

        result = get_client_info_from_context(server)

        assert result is not None
        assert result["name"] == "claude-ai"
        assert result["version"] == "1.0.0"
        assert result["friendly_name"] == "Claude"

    def test_caching_behavior(self):
        """Should cache the result and return cached value on subsequent calls."""
        import utils.client_info as client_info_module

        # First call with valid server
        server = MagicMock()
        server.request_context.session._client_params.clientInfo.name = "gemini-cli"
        server.request_context.session._client_params.clientInfo.version = "2.0.0"

        result1 = get_client_info_from_context(server)
        assert result1["name"] == "gemini-cli"

        # Second call with different server should return cached result
        server2 = MagicMock()
        server2.request_context.session._client_params.clientInfo.name = "different-client"
        server2.request_context.session._client_params.clientInfo.version = "3.0.0"

        result2 = get_client_info_from_context(server2)
        assert result2["name"] == "gemini-cli"  # Still cached value

    def test_extraction_with_missing_version(self):
        """Should handle missing version attribute."""
        import utils.client_info as client_info_module

        client_info_module._client_info_cache = None

        server = MagicMock()
        client_info_mock = MagicMock(spec=["name"])  # Only name, no version
        client_info_mock.name = "test-client"
        server.request_context.session._client_params.clientInfo = client_info_mock

        result = get_client_info_from_context(server)

        assert result is not None
        assert result["name"] == "test-client"
        assert "version" not in result


class TestGetCachedClientInfo:
    """Tests for get_cached_client_info function."""

    def setup_method(self):
        """Reset the cache before each test."""
        import utils.client_info as client_info_module

        client_info_module._client_info_cache = None

    def test_returns_none_when_not_cached(self):
        """Should return None when no info is cached."""
        assert get_cached_client_info() is None

    def test_returns_cached_value(self):
        """Should return cached value when available."""
        import utils.client_info as client_info_module

        test_info = {"name": "test", "friendly_name": "Test"}
        client_info_module._client_info_cache = test_info

        assert get_cached_client_info() == test_info


class TestGetClientFriendlyName:
    """Tests for get_client_friendly_name function."""

    def setup_method(self):
        """Reset the cache before each test."""
        import utils.client_info as client_info_module

        client_info_module._client_info_cache = None

    def test_returns_default_when_not_cached(self):
        """Should return default when no info is cached."""
        assert get_client_friendly_name() == DEFAULT_FRIENDLY_NAME

    def test_returns_friendly_name_from_cache(self):
        """Should return friendly_name from cached info."""
        import utils.client_info as client_info_module

        client_info_module._client_info_cache = {
            "name": "gemini-cli",
            "friendly_name": "Gemini",
        }

        assert get_client_friendly_name() == "Gemini"

    def test_returns_default_when_friendly_name_missing(self):
        """Should return default when friendly_name is missing from cache."""
        import utils.client_info as client_info_module

        client_info_module._client_info_cache = {"name": "some-client"}

        assert get_client_friendly_name() == DEFAULT_FRIENDLY_NAME


class TestLogClientInfo:
    """Tests for log_client_info function."""

    def setup_method(self):
        """Reset the cache before each test."""
        import utils.client_info as client_info_module

        client_info_module._client_info_cache = None

    def test_logs_client_info_when_available(self):
        """Should log client info when extraction succeeds."""
        server = MagicMock()
        server.request_context.session._client_params.clientInfo.name = "claude-ai"
        server.request_context.session._client_params.clientInfo.version = "1.0.0"

        mock_logger = MagicMock()

        log_client_info(server, logger_instance=mock_logger)

        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args[0][0]
        assert "Claude" in call_args

    def test_logs_debug_when_not_available(self):
        """Should log debug message when extraction fails."""
        server = None
        mock_logger = MagicMock()

        log_client_info(server, logger_instance=mock_logger)

        mock_logger.debug.assert_called_with("Could not extract client info from MCP protocol")


class TestClientNameMappings:
    """Tests for CLIENT_NAME_MAPPINGS constant."""

    def test_mappings_not_empty(self):
        """CLIENT_NAME_MAPPINGS should not be empty."""
        assert len(CLIENT_NAME_MAPPINGS) > 0

    def test_all_mappings_have_string_values(self):
        """All mapping values should be strings."""
        for key, value in CLIENT_NAME_MAPPINGS.items():
            assert isinstance(key, str), f"Key {key} is not a string"
            assert isinstance(value, str), f"Value {value} for key {key} is not a string"

    def test_default_friendly_name_is_string(self):
        """DEFAULT_FRIENDLY_NAME should be a string."""
        assert isinstance(DEFAULT_FRIENDLY_NAME, str)
        assert len(DEFAULT_FRIENDLY_NAME) > 0

