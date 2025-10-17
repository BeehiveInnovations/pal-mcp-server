"""
Tests for Chat tool - validating SimpleTool architecture

This module contains unit tests to ensure that the Chat tool
(now using SimpleTool architecture) maintains proper functionality.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tools.chat import ChatRequest, ChatTool
from tools.shared.exceptions import ToolExecutionError


class TestChatTool:
    """Test suite for ChatSimple tool"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tool = ChatTool()

    def test_tool_metadata(self):
        """Test that tool metadata matches requirements"""
        assert self.tool.get_name() == "chat"
        assert "collaborative thinking" in self.tool.get_description()
        assert self.tool.get_system_prompt() is not None
        assert self.tool.get_default_temperature() > 0
        assert self.tool.get_model_category() is not None

    def test_schema_structure(self):
        """Test that schema has correct structure"""
        schema = self.tool.get_input_schema()

        # Basic schema structure
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        # Required fields
        assert "prompt" in schema["required"]
        assert "working_directory" in schema["required"]

        # Properties
        properties = schema["properties"]
        assert "prompt" in properties
        assert "files" in properties
        assert "images" in properties
        assert "working_directory" in properties

    def test_request_model_validation(self):
        """Test that the request model validates correctly"""
        # Test valid request
        request_data = {
            "prompt": "Test prompt",
            "files": ["test.txt"],
            "images": ["test.png"],
            "model": "anthropic/claude-opus-4.1",
            "temperature": 0.7,
            "working_directory": "/tmp",  # Dummy absolute path
        }

        request = ChatRequest(**request_data)
        assert request.prompt == "Test prompt"
        assert request.files == ["test.txt"]
        assert request.images == ["test.png"]
        assert request.model == "anthropic/claude-opus-4.1"
        assert request.temperature == 0.7
        assert request.working_directory == "/tmp"

    def test_required_fields(self):
        """Test that required fields are enforced"""
        # Missing prompt should raise validation error
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatRequest(model="anthropic/claude-opus-4.1", working_directory="/tmp")

    def test_model_availability(self):
        """Test that model availability works"""
        models = self.tool._get_available_models()
        assert len(models) > 0  # Should have some models
        assert isinstance(models, list)

    def test_model_field_schema(self):
        """Test that model field schema generation works correctly"""
        schema = self.tool.get_model_field_schema()

        assert schema["type"] == "string"
        assert "description" in schema

        # Description should route callers to listmodels, regardless of mode
        assert "listmodels" in schema["description"]
        if self.tool.is_effective_auto_mode():
            assert "auto mode" in schema["description"].lower()
        else:
            import config

            assert f"'{config.DEFAULT_MODEL}'" in schema["description"]

    @pytest.mark.asyncio
    async def test_prompt_preparation(self):
        """Test that prompt preparation works correctly"""
        request = ChatRequest(prompt="Test prompt", files=[], working_directory="/tmp")

        # Mock the system prompt and file handling
        with patch.object(self.tool, "get_system_prompt", return_value="System prompt"):
            with patch.object(self.tool, "handle_prompt_file_with_fallback", return_value="Test prompt"):
                with patch.object(self.tool, "_prepare_file_content_for_prompt", return_value=("", [])):
                    with patch.object(self.tool, "_validate_token_limit"):
                        with patch.object(self.tool, "get_websearch_instruction", return_value=""):
                            prompt = await self.tool.prepare_prompt(request)

                            assert "Test prompt" in prompt
                            assert prompt.startswith("=== USER REQUEST ===")
                            assert "System prompt" not in prompt

    def test_response_formatting(self):
        """Test that response formatting works correctly"""
        response = "Test response content"
        request = ChatRequest(prompt="Test", working_directory="/tmp")

        formatted = self.tool.format_response(response, request)

        assert "Test response content" in formatted
        assert "AGENT'S TURN:" in formatted
        assert "Evaluate this perspective" in formatted

    def test_format_response_multiple_generated_code_blocks(self, tmp_path):
        """All generated-code blocks should be combined and saved to zen_generated.code."""
        tool = ChatTool()
        tool._model_context = SimpleNamespace(capabilities=SimpleNamespace(allow_code_generation=True))

        response = (
            "Intro text\n"
            "<GENERATED-CODE>print('hello')</GENERATED-CODE>\n"
            "Other text\n"
            "<GENERATED-CODE>print('world')</GENERATED-CODE>"
        )

        request = ChatRequest(prompt="Test", working_directory=str(tmp_path))

        formatted = tool.format_response(response, request)

        saved_path = tmp_path / "zen_generated.code"
        saved_content = saved_path.read_text(encoding="utf-8")

        assert "print('hello')" in saved_content
        assert "print('world')" in saved_content
        assert saved_content.count("<GENERATED-CODE>") == 2
        assert str(saved_path) in formatted

    def test_tool_name(self):
        """Test tool name is correct"""
        assert self.tool.get_name() == "chat"

    def test_websearch_guidance(self):
        """Test web search guidance matches Chat tool style"""
        guidance = self.tool.get_websearch_guidance()
        chat_style_guidance = self.tool.get_chat_style_websearch_guidance()

        assert guidance == chat_style_guidance
        assert "Documentation for any technologies" in guidance
        assert "Current best practices" in guidance

    def test_convenience_methods(self):
        """Test SimpleTool convenience methods work correctly"""
        assert self.tool.supports_custom_request_model()

        # Test that the tool fields are defined correctly
        tool_fields = self.tool.get_tool_fields()
        assert "prompt" in tool_fields
        assert "files" in tool_fields
        assert "images" in tool_fields

        required_fields = self.tool.get_required_fields()
        assert "prompt" in required_fields
        assert "working_directory" in required_fields


class TestChatRequestModel:
    """Test suite for ChatRequest model"""

    def test_field_descriptions(self):
        """Test that field descriptions are proper"""
        from tools.chat import CHAT_FIELD_DESCRIPTIONS

        # Field descriptions should exist and be descriptive
        assert len(CHAT_FIELD_DESCRIPTIONS["prompt"]) > 50
        assert "context" in CHAT_FIELD_DESCRIPTIONS["prompt"]
        files_desc = CHAT_FIELD_DESCRIPTIONS["files"].lower()
        assert "absolute" in files_desc
        assert "visual context" in CHAT_FIELD_DESCRIPTIONS["images"]
        assert "directory" in CHAT_FIELD_DESCRIPTIONS["working_directory"].lower()

    def test_working_directory_description_matches_behavior(self):
        """Working directory description should reflect automatic creation."""
        from tools.chat import CHAT_FIELD_DESCRIPTIONS

        description = CHAT_FIELD_DESCRIPTIONS["working_directory"].lower()
        assert "must already exist" in description

    @pytest.mark.asyncio
    async def test_working_directory_must_exist(self, tmp_path):
        """Chat tool should reject non-existent working directories."""
        tool = ChatTool()
        missing_dir = tmp_path / "nonexistent_subdir"

        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.execute(
                {
                    "prompt": "test",
                    "files": [],
                    "images": [],
                    "working_directory": str(missing_dir),
                }
            )

        payload = json.loads(exc_info.value.payload)
        assert payload["status"] == "error"
        assert "existing directory" in payload["content"].lower()

    def test_default_values(self):
        """Test that default values work correctly"""
        request = ChatRequest(prompt="Test", working_directory="/tmp")

        assert request.prompt == "Test"
        assert request.files == []  # Should default to empty list
        assert request.images == []  # Should default to empty list

    def test_inheritance(self):
        """Test that ChatRequest properly inherits from ToolRequest"""
        from tools.shared.base_models import ToolRequest

        request = ChatRequest(prompt="Test", working_directory="/tmp")
        assert isinstance(request, ToolRequest)

        # Should have inherited fields
        assert hasattr(request, "model")
        assert hasattr(request, "temperature")
        assert hasattr(request, "thinking_mode")
        assert hasattr(request, "continuation_id")
        assert hasattr(request, "images")  # From base model too


if __name__ == "__main__":
    pytest.main([__file__])
