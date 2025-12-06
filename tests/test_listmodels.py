"""Tests for the ListModels tool"""

import json
import os
from unittest.mock import patch

import pytest
from mcp.types import TextContent

from tools.listmodels import ListModelsTool


class TestListModelsTool:
    """Test the ListModels tool functionality"""

    @pytest.fixture
    def tool(self):
        """Create a ListModelsTool instance"""
        return ListModelsTool()

    def test_tool_metadata(self, tool):
        """Test tool has correct metadata"""
        assert tool.name == "listmodels"
        assert "model providers" in tool.description
        assert tool.get_request_model().__name__ == "ToolRequest"

    @pytest.mark.asyncio
    async def test_execute_with_no_providers(self, tool):
        """Test listing models with no providers configured"""
        with patch.dict(os.environ, {}, clear=True):
            # Set auto mode
            os.environ["DEFAULT_MODEL"] = "auto"

            result = await tool.execute({})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            # Parse JSON response
            response = json.loads(result[0].text)
            assert response["status"] == "success"

            content = response["content"]

            # Check that providers show as not configured
            assert "Google Gemini ❌" in content
            assert "OpenAI ❌" in content
            assert "X.AI (Grok) ❌" in content
            assert "OpenRouter ❌" in content
            assert "Custom/Local API ❌" in content

            # Check summary shows 0 configured
            assert "**Configured Providers**: 0" in content

    @pytest.mark.asyncio
    async def test_execute_with_gemini_configured(self, tool):
        """Test listing models with Gemini configured"""
        env_vars = {"GEMINI_API_KEY": "test-key", "DEFAULT_MODEL": "auto"}

        with patch.dict(os.environ, env_vars, clear=True):
            result = await tool.execute({})

            response = json.loads(result[0].text)
            content = response["content"]

            # Check Gemini shows as configured
            assert "Google Gemini ✅" in content
            assert "`flash` → `gemini-2.5-flash`" in content
            assert "`pro` → `gemini-3-pro-preview`" in content
            assert "1M context" in content
            assert "Supports structured code generation" in content

            # Check summary
            assert "**Configured Providers**: 1" in content

    @pytest.mark.asyncio
    async def test_execute_with_multiple_providers(self, tool):
        """Test listing models with multiple providers configured"""
        env_vars = {
            "GEMINI_API_KEY": "test-key",
            "OPENAI_API_KEY": "test-key",
            "XAI_API_KEY": "test-key",
            "DEFAULT_MODEL": "auto",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            result = await tool.execute({})

            response = json.loads(result[0].text)
            content = response["content"]

            # Check all show as configured
            assert "Google Gemini ✅" in content
            assert "OpenAI ✅" in content
            assert "X.AI (Grok) ✅" in content

            # Check models are listed
            assert "`o3`" in content
            assert "`grok`" in content

            # Check summary
            assert "**Configured Providers**: 3" in content

    @pytest.mark.asyncio
    async def test_execute_with_openrouter(self, tool):
        """Test listing models with OpenRouter configured"""
        env_vars = {"OPENROUTER_API_KEY": "test-key", "DEFAULT_MODEL": "auto"}

        with patch.dict(os.environ, env_vars, clear=True):
            result = await tool.execute({})

            response = json.loads(result[0].text)
            content = response["content"]

            # Check OpenRouter shows as configured
            assert "OpenRouter ✅" in content
            assert "Access to multiple cloud AI providers" in content

            # Should show some models (mocked registry will have some)
            assert "Available Models" in content

    @pytest.mark.asyncio
    async def test_execute_with_custom_api(self, tool):
        """Test listing models with custom API configured"""
        env_vars = {"CUSTOM_API_URL": "http://localhost:11434", "DEFAULT_MODEL": "auto"}

        with patch.dict(os.environ, env_vars, clear=True):
            result = await tool.execute({})

            response = json.loads(result[0].text)
            content = response["content"]

            # Check Custom API shows as configured
            assert "Custom/Local API ✅" in content
            assert "http://localhost:11434" in content
            assert "Local models via Ollama" in content

    @pytest.mark.asyncio
    async def test_output_includes_usage_tips(self, tool):
        """Test that output includes helpful usage tips"""
        result = await tool.execute({})

        response = json.loads(result[0].text)
        content = response["content"]

        # Check for usage tips
        assert "**Usage Tips**:" in content
        assert "Use model aliases" in content
        assert "auto mode" in content

    def test_model_category(self, tool):
        """Test that tool uses FAST_RESPONSE category"""
        from tools.models import ToolModelCategory

        assert tool.get_model_category() == ToolModelCategory.FAST_RESPONSE
