"""
Tests for the main server functionality
"""

import pytest

from server import handle_call_tool, handle_list_tools


class TestServerTools:
    """Test server tool handling"""

    @pytest.mark.asyncio
    async def test_handle_list_tools(self):
        """Test listing all available tools"""
        tools = await handle_list_tools()
        tool_names = [tool.name for tool in tools]

        # Check all core tools are present
        assert "thinkdeep" in tool_names
        assert "codereview" in tool_names
        assert "debug" in tool_names
        assert "analyze" in tool_names
        assert "chat" in tool_names
        assert "consensus" in tool_names
        assert "precommit" in tool_names
        assert "testgen" in tool_names
        assert "refactor" in tool_names
        assert "tracer" in tool_names
        assert "version" in tool_names

        # Should have exactly 12 tools (including consensus, refactor, tracer, and listmodels)
        assert len(tools) == 12

        # Check descriptions are verbose
        for tool in tools:
            assert len(tool.description) > 50  # All should have detailed descriptions

    @pytest.mark.asyncio
    async def test_handle_call_tool_unknown(self):
        """Test calling an unknown tool"""
        result = await handle_call_tool("unknown_tool", {})
        assert len(result) == 1
        assert "Unknown tool: unknown_tool" in result[0].text

    @pytest.mark.asyncio
    async def test_handle_chat(self):
        """Test chat functionality using real integration testing"""
        import importlib
        import os

        # Set test environment
        os.environ["PYTEST_CURRENT_TEST"] = "test"

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for real provider resolution
            os.environ["OPENAI_API_KEY"] = "sk-test-key-server-chat-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"

            # Clear other provider keys to isolate to OpenAI
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            # Test with real provider resolution
            try:
                result = await handle_call_tool("chat", {"prompt": "Hello Gemini", "model": "o3-mini"})

                # If we get here, check the response format
                assert len(result) == 1
                # Parse JSON response
                import json

                response_data = json.loads(result[0].text)
                assert "status" in response_data

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
    async def test_handle_version(self):
        """Test getting version info"""
        result = await handle_call_tool("version", {})
        assert len(result) == 1

        response = result[0].text
        assert "Zen MCP Server v" in response  # Version agnostic check
        assert "Available Tools:" in response
        assert "thinkdeep" in response
