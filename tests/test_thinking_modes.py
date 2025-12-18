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
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
            "XAI_API_KEY": os.environ.get("XAI_API_KEY"),
            "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY"),
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
                        "absolute_file_paths": ["/absolute/path/test.py"],
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
                error_msg = getattr(e, "payload", str(e))
                # Should NOT be a mock-related error - should be a real API or key error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error (API key, network, etc.)
                import json

                try:
                    parsed = json.loads(error_msg)
                except Exception:
                    parsed = None

                if isinstance(parsed, dict) and parsed.get("status", "").endswith("_failed"):
                    assert "validation errors" in parsed.get("error", "")
                else:
                    assert any(
                        phrase in error_msg
                        for phrase in ["API", "key", "authentication", "provider", "network", "connection", "Model"]
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
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
            "XAI_API_KEY": os.environ.get("XAI_API_KEY"),
            "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY"),
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
                        "absolute_file_paths": ["/absolute/path/test.py"],
                        "thinking_mode": "low",
                        "prompt": "Test code review for validation purposes",
                        "model": "o3-mini",
                    }
                )
                # If we get here, provider resolution worked
                assert result is not None

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = getattr(e, "payload", str(e))
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                import json

                try:
                    parsed = json.loads(error_msg)
                except Exception:
                    parsed = None

                if isinstance(parsed, dict) and parsed.get("status", "").endswith("_failed"):
                    assert "validation errors" in parsed.get("error", "")
                else:
                    assert any(
                        phrase in error_msg
                        for phrase in ["API", "key", "authentication", "provider", "network", "connection", "Model"]
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
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
            "XAI_API_KEY": os.environ.get("XAI_API_KEY"),
            "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY"),
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
                error_msg = getattr(e, "payload", str(e))
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                import json

                try:
                    parsed = json.loads(error_msg)
                except Exception:
                    parsed = None

                if isinstance(parsed, dict) and parsed.get("status", "").endswith("_failed"):
                    assert "validation errors" in parsed.get("error", "")
                else:
                    assert any(
                        phrase in error_msg
                        for phrase in ["API", "key", "authentication", "provider", "network", "connection", "Model"]
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
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
            "XAI_API_KEY": os.environ.get("XAI_API_KEY"),
            "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY"),
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
                        "absolute_file_paths": ["/absolute/path/complex.py"],
                        "prompt": "Analyze architecture",
                        "thinking_mode": "high",
                        "model": "o3-mini",
                    }
                )
                # If we get here, provider resolution worked
                assert result is not None

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = getattr(e, "payload", str(e))
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                import json

                try:
                    parsed = json.loads(error_msg)
                except Exception:
                    parsed = None

                if isinstance(parsed, dict) and parsed.get("status", "").endswith("_failed"):
                    assert "validation errors" in parsed.get("error", "")
                else:
                    assert any(
                        phrase in error_msg
                        for phrase in ["API", "key", "authentication", "provider", "network", "connection", "Model"]
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
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
            "XAI_API_KEY": os.environ.get("XAI_API_KEY"),
            "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY"),
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
                error_msg = getattr(e, "payload", str(e))
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                import json

                try:
                    parsed = json.loads(error_msg)
                except Exception:
                    parsed = None

                if isinstance(parsed, dict) and parsed.get("status", "").endswith("_failed"):
                    assert "validation errors" in parsed.get("error", "")
                else:
                    assert any(
                        phrase in error_msg
                        for phrase in ["API", "key", "authentication", "provider", "network", "connection", "Model"]
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


class TestGeminiThinkingConfiguration:
    """Test Gemini-specific thinking configuration.

    Note: The current Google SDK (google-genai) only supports thinkingBudget (integer),
    NOT thinkingLevel (string). Both Gemini 2.x and 3.x models use thinkingBudget
    with the current SDK. The SDK may add thinkingLevel support in the future.
    """

    def test_gemini_3_uses_thinking_budget(self):
        """Verify Gemini 3 models use thinkingBudget parameter (integer) with current SDK"""
        from unittest.mock import MagicMock, patch

        from providers.gemini import GeminiModelProvider

        # Mock the client and response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.candidates = [MagicMock(finish_reason="STOP")]
        mock_response.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=20)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("google.genai.Client", return_value=mock_client):
            provider = GeminiModelProvider(api_key="test-key")

            # Call generate_content with Gemini 3 Flash model
            provider.generate_content(
                prompt="Test",
                model_name="gemini-3-flash-preview",
                thinking_mode="high",
            )

            # Verify the call was made
            mock_client.models.generate_content.assert_called_once()
            call_kwargs = mock_client.models.generate_content.call_args
            config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")

            # Verify thinking_config uses thinking_budget (integer)
            # Current SDK does NOT support thinking_level (string)
            assert config.thinking_config is not None
            assert hasattr(config.thinking_config, "thinking_budget")
            capability_map = provider.get_all_model_capabilities()
            max_thinking_tokens = capability_map["gemini-3-flash-preview"].max_thinking_tokens
            expected_budget = int(max_thinking_tokens * GeminiModelProvider.THINKING_BUDGETS["high"])
            assert config.thinking_config.thinking_budget == expected_budget

    def test_gemini_25_uses_thinking_budget(self):
        """Verify Gemini 2.5 models use thinkingBudget parameter (integer)"""
        from unittest.mock import MagicMock, patch

        from providers.gemini import GeminiModelProvider

        # Mock the client and response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.candidates = [MagicMock(finish_reason="STOP")]
        mock_response.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=20)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("google.genai.Client", return_value=mock_client):
            provider = GeminiModelProvider(api_key="test-key")

            # Call generate_content with Gemini 2.5 Flash model
            provider.generate_content(
                prompt="Test",
                model_name="gemini-2.5-flash",
                thinking_mode="high",
            )

            # Verify the call was made
            mock_client.models.generate_content.assert_called_once()
            call_kwargs = mock_client.models.generate_content.call_args
            config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")

            # Verify thinking_config uses thinking_budget (integer), not thinking_level
            assert config.thinking_config is not None
            assert hasattr(config.thinking_config, "thinking_budget")
            capability_map = provider.get_all_model_capabilities()
            max_thinking_tokens = capability_map["gemini-2.5-flash"].max_thinking_tokens
            expected_budget = int(max_thinking_tokens * GeminiModelProvider.THINKING_BUDGETS["high"])
            assert config.thinking_config.thinking_budget == expected_budget

    def test_gemini_3_flash_max_thinking_budget(self):
        """Verify Gemini 3 Flash 'max' thinking mode uses full thinking budget"""
        from unittest.mock import MagicMock, patch

        from providers.gemini import GeminiModelProvider

        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.candidates = [MagicMock(finish_reason="STOP")]
        mock_response.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=20)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("google.genai.Client", return_value=mock_client):
            provider = GeminiModelProvider(api_key="test-key")

            provider.generate_content(
                prompt="Test",
                model_name="gemini-3-flash-preview",
                thinking_mode="max",
            )

            call_kwargs = mock_client.models.generate_content.call_args
            config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")

            # 'max' = 100% of model max_thinking_tokens.
            assert config.thinking_config is not None
            assert hasattr(config.thinking_config, "thinking_budget")
            capability_map = provider.get_all_model_capabilities()
            max_thinking_tokens = capability_map["gemini-3-flash-preview"].max_thinking_tokens
            expected_budget = int(max_thinking_tokens * GeminiModelProvider.THINKING_BUDGETS["max"])
            assert config.thinking_config.thinking_budget == expected_budget
