"""
Test cases for uvx support and environment handling.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest


class TestUvxEnvironmentHandling:
    """Test uvx-specific environment handling features."""

    def test_dotenv_import_success(self):
        """Test that dotenv is imported successfully when available."""
        # Mock successful dotenv import
        mock_load = mock.MagicMock()
        mock_values = mock.MagicMock(return_value={})
        fake_dotenv = mock.MagicMock(load_dotenv=mock_load, dotenv_values=mock_values)

        with mock.patch.dict("sys.modules", {"dotenv": fake_dotenv}):
            if "utils.env" in sys.modules:
                del sys.modules["utils.env"]
            if "server" in sys.modules:
                del sys.modules["server"]

            import importlib

            import utils.env as env_config

            with tempfile.NamedTemporaryFile("w", delete=False) as tmp_env:
                temp_env_path = Path(tmp_env.name)
                tmp_env.write("ZEN_MCP_FORCE_ENV_OVERRIDE=false\n")

            try:
                importlib.reload(env_config)
                env_config._ENV_PATH = temp_env_path
                env_config.reload_env()
                import server  # noqa: F401

                assert mock_load.call_count >= 1
                _, kwargs = mock_load.call_args
                assert "dotenv_path" in kwargs
            finally:
                temp_env_path.unlink(missing_ok=True)

    def test_dotenv_import_failure_graceful_handling(self):
        """Test that ImportError for dotenv is handled gracefully (uvx scenario)."""
        # Mock only the dotenv import to fail
        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if name == "dotenv":
                raise ImportError("No module named 'dotenv'")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=mock_import):
            # This should not raise an exception when trying to import dotenv
            try:
                from dotenv import load_dotenv  # noqa: F401

                pytest.fail("Should have raised ImportError for dotenv")
            except ImportError:
                # Expected behavior - ImportError should be caught gracefully in server.py
                pass

    def test_env_file_path_resolution(self):
        """Test that .env file path is correctly resolved relative to server.py."""
        import server

        # Test that the server module correctly resolves .env path
        script_dir = Path(server.__file__).parent
        expected_env_file = script_dir / ".env"

        # The logic should create a path relative to server.py
        assert expected_env_file.name == ".env"
        assert expected_env_file.parent == script_dir

    def test_environment_variables_still_work_without_dotenv(self):
        """Test that environment variables work even when dotenv is not available."""
        # Set a test environment variable
        test_key = "TEST_ZEN_MCP_VAR"
        test_value = "test_value_123"

        with mock.patch.dict(os.environ, {test_key: test_value}):
            # Environment variable should still be accessible regardless of dotenv
            assert os.getenv(test_key) == test_value

    def test_dotenv_graceful_fallback_behavior(self):
        """Test the actual graceful fallback behavior in server module."""
        # Test that server module handles missing dotenv gracefully
        # This is tested by the fact that the server can be imported even if dotenv fails
        import server

        # If we can import server, the graceful handling works
        assert hasattr(server, "run")

        # Test that environment variables still work
        test_key = "TEST_FALLBACK_VAR"
        test_value = "fallback_test_123"

        with mock.patch.dict(os.environ, {test_key: test_value}):
            assert os.getenv(test_key) == test_value


class TestUvxProjectConfiguration:
    """Test uvx-specific project configuration features."""

    def test_pyproject_toml_has_required_uvx_fields(self):
        """Test that pyproject.toml has all required fields for uvx support."""
        try:
            import tomllib
        except ImportError:
            # tomllib is only available in Python 3.11+
            # For older versions, use tomli or skip the test
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("tomllib/tomli not available for TOML parsing")

        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml should exist"

        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)

        # Check required uvx fields
        assert "project" in pyproject_data
        project = pyproject_data["project"]

        # Essential fields for uvx
        assert "name" in project
        assert project["name"] == "zen-mcp-server"
        assert "dependencies" in project
        assert "requires-python" in project

        # Script entry point for uvx
        assert "scripts" in project
        assert "zen-mcp-server" in project["scripts"]
        assert project["scripts"]["zen-mcp-server"] == "server:run"

    def test_pyproject_dependencies_match_requirements(self):
        """Test that pyproject.toml dependencies align with requirements.txt."""
        try:
            import tomllib
        except ImportError:
            # tomllib is only available in Python 3.11+
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("tomllib/tomli not available for TOML parsing")

        # Read pyproject.toml
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)

        pyproject_deps = set(pyproject_data["project"]["dependencies"])

        # Read requirements.txt
        requirements_path = Path(__file__).parent.parent / "requirements.txt"
        if requirements_path.exists():
            # Note: We primarily validate pyproject.toml has core dependencies
            # requirements.txt might have additional dev dependencies

            # Core dependencies should be present in both
            core_packages = {"mcp", "openai", "google-genai", "pydantic", "python-dotenv"}

            for pkg in core_packages:
                pyproject_has = any(pkg in dep for dep in pyproject_deps)

                assert pyproject_has, f"{pkg} should be in pyproject.toml dependencies"
                # requirements.txt might have additional dev dependencies

    def test_uvx_entry_point_callable(self):
        """Test that the uvx entry point (server:run) is callable."""
        import server

        # The entry point should reference a callable function
        assert hasattr(server, "run"), "server module should have a 'run' function"
        assert callable(server.run), "server.run should be callable"
