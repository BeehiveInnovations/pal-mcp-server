"""Unit tests for CLIProvider."""

import pytest

from providers.cli_provider import CLI_MODEL_PREFIX, CLIProvider
from providers.shared import ProviderType


class TestCLIProviderModelNameParsing:
    """Tests for CLI model name parsing."""

    def test_parse_valid_model_name_default_role(self):
        """Test parsing cli:gemini -> (gemini, default)"""
        provider = CLIProvider.__new__(CLIProvider)
        provider._cli_names = ["gemini", "claude", "codex"]

        cli_name, role = provider._parse_model_name("cli:gemini")
        assert cli_name == "gemini"
        assert role == "default"

    def test_parse_valid_model_name_with_role(self):
        """Test parsing cli:gemini:planner -> (gemini, planner)"""
        provider = CLIProvider.__new__(CLIProvider)
        provider._cli_names = ["gemini", "claude", "codex"]

        cli_name, role = provider._parse_model_name("cli:gemini:planner")
        assert cli_name == "gemini"
        assert role == "planner"

    def test_parse_invalid_model_name_no_prefix(self):
        """Test that model names without cli: prefix raise ValueError"""
        provider = CLIProvider.__new__(CLIProvider)
        provider._cli_names = ["gemini"]

        with pytest.raises(ValueError, match="Invalid CLI model name"):
            provider._parse_model_name("gemini")

    def test_parse_invalid_model_name_wrong_prefix(self):
        """Test that model names with wrong prefix raise ValueError"""
        provider = CLIProvider.__new__(CLIProvider)
        provider._cli_names = ["gemini"]

        with pytest.raises(ValueError, match="Invalid CLI model name"):
            provider._parse_model_name("api:gemini")


class TestCLIProviderType:
    """Tests for CLI provider type."""

    def test_cli_provider_type_exists(self):
        """Test that CLI ProviderType exists."""
        assert hasattr(ProviderType, "CLI")
        assert ProviderType.CLI.value == "cli"

    def test_cli_model_prefix(self):
        """Test CLI model prefix constant."""
        assert CLI_MODEL_PREFIX == "cli:"


class TestCLIProviderValidation:
    """Tests for CLI provider model validation."""

    def test_validate_model_name_valid(self):
        """Test validation of valid CLI model names."""
        provider = CLIProvider.__new__(CLIProvider)
        provider._cli_names = ["gemini", "claude"]

        # Mock the registry
        class MockRegistry:
            def list_roles(self, cli_name):
                return ["default", "planner", "codereviewer"]

        provider._registry = MockRegistry()

        assert provider.validate_model_name("cli:gemini") is True
        assert provider.validate_model_name("cli:gemini:planner") is True
        assert provider.validate_model_name("cli:claude") is True

    def test_validate_model_name_invalid_cli(self):
        """Test validation rejects unknown CLI names."""
        provider = CLIProvider.__new__(CLIProvider)
        provider._cli_names = ["gemini"]

        class MockRegistry:
            def list_roles(self, cli_name):
                return ["default"]

        provider._registry = MockRegistry()

        assert provider.validate_model_name("cli:unknown") is False

    def test_validate_model_name_invalid_role(self):
        """Test validation rejects unknown roles."""
        provider = CLIProvider.__new__(CLIProvider)
        provider._cli_names = ["gemini"]

        class MockRegistry:
            def list_roles(self, cli_name):
                return ["default", "planner"]

        provider._registry = MockRegistry()

        assert provider.validate_model_name("cli:gemini:unknown_role") is False

    def test_validate_model_name_non_cli(self):
        """Test validation rejects non-CLI model names."""
        provider = CLIProvider.__new__(CLIProvider)
        provider._cli_names = ["gemini"]

        assert provider.validate_model_name("gpt-4o") is False
        assert provider.validate_model_name("gemini-2.5-flash") is False

    def test_validate_model_name_alias(self):
        """Test validation accepts alias format (cli-claude instead of cli:claude)."""
        provider = CLIProvider.__new__(CLIProvider)
        provider._cli_names = ["gemini", "claude"]

        class MockRegistry:
            def list_roles(self, cli_name):
                return ["default", "planner"]

        provider._registry = MockRegistry()

        # Build MODEL_CAPABILITIES with aliases
        from providers.shared import ModelCapabilities, ProviderType

        provider.MODEL_CAPABILITIES = {
            "cli:gemini": ModelCapabilities(
                provider=ProviderType.CLI,
                model_name="cli:gemini",
                friendly_name="CLI/gemini",
                aliases=["cli-gemini"],
            ),
            "cli:claude": ModelCapabilities(
                provider=ProviderType.CLI,
                model_name="cli:claude",
                friendly_name="CLI/claude",
                aliases=["cli-claude"],
            ),
        }

        # Test alias validation
        assert provider.validate_model_name("cli-gemini") is True
        assert provider.validate_model_name("cli-claude") is True
        assert provider.validate_model_name("cli:gemini") is True
        assert provider.validate_model_name("cli:claude") is True


class TestCLIProviderCapabilities:
    """Tests for CLI provider capabilities."""

    def test_get_provider_type(self):
        """Test get_provider_type returns CLI."""
        provider = CLIProvider.__new__(CLIProvider)
        assert provider.get_provider_type() == ProviderType.CLI


class TestCLIProviderIntegration:
    """Integration tests that require clink to be configured."""

    @pytest.fixture
    def mock_clink_registry(self, monkeypatch):
        """Mock clink registry for testing."""

        class MockClinkRegistry:
            def list_clients(self):
                return ["gemini", "claude"]

            def list_roles(self, cli_name):
                return ["default", "planner", "codereviewer"]

            def get_client(self, cli_name):
                raise KeyError(f"Mock: CLI {cli_name} not configured")

        def mock_get_registry():
            return MockClinkRegistry()

        # Mock at the clink module level
        monkeypatch.setattr("clink.get_registry", mock_get_registry)
        return mock_get_registry

    def test_cli_provider_initialization(self, mock_clink_registry):
        """Test CLIProvider initializes with mocked clink registry."""
        provider = CLIProvider()

        assert provider._cli_names == ["gemini", "claude"]
        assert "cli:gemini" in provider.MODEL_CAPABILITIES
        assert "cli:claude" in provider.MODEL_CAPABILITIES
        assert "cli:gemini:planner" in provider.MODEL_CAPABILITIES

    def test_cli_provider_list_models(self, mock_clink_registry):
        """Test CLIProvider list_models returns all CLI models."""
        provider = CLIProvider()

        models = provider.list_models()
        assert "cli:gemini" in models
        assert "cli:claude" in models

    def test_cli_provider_model_capabilities(self, mock_clink_registry):
        """Test CLIProvider model capabilities are correct."""
        provider = CLIProvider()

        caps = provider.get_capabilities("cli:gemini")
        assert caps.provider == ProviderType.CLI
        assert caps.supports_temperature is False  # CLI doesn't support temperature
        assert caps.supports_system_prompts is True
        assert caps.context_window == 200000

    def test_cli_provider_generate_content_fails_without_cli(self, mock_clink_registry):
        """Test generate_content raises error when CLI not configured."""
        provider = CLIProvider()

        with pytest.raises(ValueError, match="Invalid CLI configuration"):
            provider.generate_content(
                prompt="Test prompt",
                model_name="cli:gemini",
            )
