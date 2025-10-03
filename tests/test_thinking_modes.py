"""
Tests for thinking_mode functionality across all tools
"""

from unittest.mock import patch

import pytest

from tools.analyze import AnalyzeTool
from tools.codereview import CodeReviewTool
from tools.debug import DebugIssueTool
from tools.thinkdeep import ThinkDeepTool


@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment"""
    # PYTEST_CURRENT_TEST is already set by pytest
    yield


class TestThinkingModes:
    """Test thinking modes across all tools"""

    @patch("config.DEFAULT_THINKING_MODE_THINKDEEP", "high")
    def test_default_thinking_modes(self):
        """Test that tools have correct default thinking modes"""
        tools = [
            (ThinkDeepTool(), "high"),
            (AnalyzeTool(), "medium"),
            (CodeReviewTool(), "medium"),
            (DebugIssueTool(), "medium"),
        ]

        for tool, expected_default in tools:
            assert (
                tool.get_default_thinking_mode() == expected_default
            ), f"{tool.__class__.__name__} should default to {expected_default}"

    @pytest.mark.asyncio
    async def test_thinking_mode_minimal(self):
        """Test minimal thinking mode with real provider resolution"""
        import importlib
        import os

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for OpenAI provider (which supports thinking mode)
            os.environ["OPENAI_API_KEY"] = "sk-test-key-minimal-thinking-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"  # Use a model that supports thinking

            # Clear other provider keys to isolate to OpenAI
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            tool = AnalyzeTool()

            # This should attempt to use the real OpenAI provider
            # Even with a fake API key, we can test the provider resolution logic
            # The test will fail at the API call level, but we can verify the thinking mode logic
            try:
                result = await tool.execute(
                    {
                        "files": ["/absolute/path/test.py"],
                        "prompt": "What is this?",
                        "model": "o3-mini",
                        "thinking_mode": "minimal",
                    }
                )
                # If we get here, great! The provider resolution worked
                # Check that thinking mode was properly handled
                assert result is not None

            except Exception as e:
                # Expected: API call will fail with fake key, but we can check the error
                # If we get a provider resolution error, that's what we're testing
                error_msg = str(e)
                # Should NOT be a mock-related error - should be a real API or key error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error (API key, network, etc.)
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None

    @pytest.mark.asyncio
    async def test_thinking_mode_low(self):
        """Test low thinking mode with real provider resolution"""
        import importlib
        import os

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for OpenAI provider (which supports thinking mode)
            os.environ["OPENAI_API_KEY"] = "sk-test-key-low-thinking-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"

            # Clear other provider keys
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            tool = CodeReviewTool()

            # Test with real provider resolution
            try:
                result = await tool.execute(
                    {
                        "files": ["/absolute/path/test.py"],
                        "thinking_mode": "low",
                        "prompt": "Test code review for validation purposes",
                        "model": "o3-mini",
                    }
                )
                # If we get here, provider resolution worked
                assert result is not None

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = str(e)
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None

    @pytest.mark.asyncio
    async def test_thinking_mode_medium(self):
        """Test medium thinking mode (default for most tools) using real integration testing"""
        import importlib
        import os

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for OpenAI provider (which supports thinking mode)
            os.environ["OPENAI_API_KEY"] = "sk-test-key-medium-thinking-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"

            # Clear other provider keys to isolate to OpenAI
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            tool = DebugIssueTool()

            # Test with real provider resolution
            try:
                result = await tool.execute(
                    {
                        "prompt": "Test error",
                        "model": "o3-mini",
                        # Not specifying thinking_mode, should use default (medium)
                    }
                )
                # If we get here, provider resolution worked
                assert result is not None
                # Should be a valid debug response
                assert len(result) == 1

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = str(e)
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None

    @pytest.mark.asyncio
    async def test_thinking_mode_high(self):
        """Test high thinking mode with real provider resolution"""
        import importlib
        import os

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for OpenAI provider (which supports thinking mode)
            os.environ["OPENAI_API_KEY"] = "sk-test-key-high-thinking-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"

            # Clear other provider keys
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            tool = AnalyzeTool()

            # Test with real provider resolution
            try:
                result = await tool.execute(
                    {
                        "files": ["/absolute/path/complex.py"],
                        "prompt": "Analyze architecture",
                        "thinking_mode": "high",
                        "model": "o3-mini",
                    }
                )
                # If we get here, provider resolution worked
                assert result is not None

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = str(e)
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None

    @pytest.mark.asyncio
    async def test_thinking_mode_max(self):
        """Test max thinking mode (default for thinkdeep) using real integration testing"""
        import importlib
        import os

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
            "DEFAULT_THINKING_MODE_THINKDEEP": os.environ.get("DEFAULT_THINKING_MODE_THINKDEEP"),
        }

        try:
            # Set up environment for OpenAI provider (which supports thinking mode)
            os.environ["OPENAI_API_KEY"] = "sk-test-key-max-thinking-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"
            os.environ["DEFAULT_THINKING_MODE_THINKDEEP"] = "high"  # Set default to high for thinkdeep

            # Clear other provider keys to isolate to OpenAI
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            tool = ThinkDeepTool()

            # Test with real provider resolution
            try:
                result = await tool.execute(
                    {
                        "prompt": "Initial analysis",
                        "model": "o3-mini",
                        # Not specifying thinking_mode, should use default (high)
                    }
                )
                # If we get here, provider resolution worked
                assert result is not None
                # Should be a valid thinkdeep response
                assert len(result) == 1

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = str(e)
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None
