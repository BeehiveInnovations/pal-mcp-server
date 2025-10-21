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
        assert "working_directory_absolute_path" in schema["required"]

        # Properties
        properties = schema["properties"]
        assert "prompt" in properties
        assert "absolute_file_paths" in properties
        assert "images" in properties
        assert "working_directory_absolute_path" in properties

    def test_request_model_validation(self):
        """Test that the request model validates correctly"""
        # Test valid request
        request_data = {
            "prompt": "Test prompt",
            "absolute_file_paths": ["test.txt"],
            "images": ["test.png"],
            "model": "anthropic/claude-opus-4.1",
            "temperature": 0.7,
            "working_directory_absolute_path": "/tmp",  # Dummy absolute path
        }

        request = ChatRequest(**request_data)
        assert request.prompt == "Test prompt"
        assert request.absolute_file_paths == ["test.txt"]
        assert request.images == ["test.png"]
        assert request.model == "anthropic/claude-opus-4.1"
        assert request.temperature == 0.7
        assert request.working_directory_absolute_path == "/tmp"

    def test_required_fields(self):
        """Test that required fields are enforced"""
        # Missing prompt should raise validation error
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatRequest(model="anthropic/claude-opus-4.1", working_directory_absolute_path="/tmp")

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
        request = ChatRequest(
            prompt="Test prompt",
            absolute_file_paths=[],
            working_directory_absolute_path="/tmp",
        )

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
        request = ChatRequest(prompt="Test", working_directory_absolute_path="/tmp")

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

        request = ChatRequest(prompt="Test", working_directory_absolute_path=str(tmp_path))

        formatted = tool.format_response(response, request)

        saved_path = tmp_path / "zen_generated.code"
        saved_content = saved_path.read_text(encoding="utf-8")

        assert "print('world')" in saved_content
        assert "print('hello')" not in saved_content
        assert saved_content.count("<GENERATED-CODE>") == 1
        assert "<GENERATED-CODE>print('hello')" in formatted
        assert str(saved_path) in formatted

    def test_format_response_single_generated_code_block(self, tmp_path):
        """Single <GENERATED-CODE> block should be saved and removed from narrative."""
        tool = ChatTool()
        tool._model_context = SimpleNamespace(capabilities=SimpleNamespace(allow_code_generation=True))

        response = (
            "Intro text before code.\n"
            "<GENERATED-CODE>print('only-once')</GENERATED-CODE>\n"
            "Closing thoughts after code."
        )

        request = ChatRequest(prompt="Test", working_directory_absolute_path=str(tmp_path))

        formatted = tool.format_response(response, request)

        saved_path = tmp_path / "zen_generated.code"
        saved_content = saved_path.read_text(encoding="utf-8")

        assert "print('only-once')" in saved_content
        assert "<GENERATED-CODE>" in saved_content
        assert "print('only-once')" not in formatted
        assert "Closing thoughts after code." in formatted

    def test_format_response_ignores_unclosed_generated_code(self, tmp_path):
        """Unclosed generated-code tags should be ignored to avoid accidental clipping."""
        tool = ChatTool()
        tool._model_context = SimpleNamespace(capabilities=SimpleNamespace(allow_code_generation=True))

        response = "Intro text\n<GENERATED-CODE>print('oops')\nStill ongoing"

        request = ChatRequest(prompt="Test", working_directory_absolute_path=str(tmp_path))

        formatted = tool.format_response(response, request)

        saved_path = tmp_path / "zen_generated.code"
        assert not saved_path.exists()
        assert "print('oops')" in formatted

    def test_format_response_ignores_orphaned_closing_tag(self, tmp_path):
        """Stray closing tags should not trigger extraction."""
        tool = ChatTool()
        tool._model_context = SimpleNamespace(capabilities=SimpleNamespace(allow_code_generation=True))

        response = "Intro text\n</GENERATED-CODE> just text"

        request = ChatRequest(prompt="Test", working_directory_absolute_path=str(tmp_path))

        formatted = tool.format_response(response, request)

        saved_path = tmp_path / "zen_generated.code"
        assert not saved_path.exists()
        assert "</GENERATED-CODE> just text" in formatted

    def test_format_response_preserves_narrative_after_generated_code(self, tmp_path):
        """Narrative content after generated code must remain intact in the formatted output."""
        tool = ChatTool()
        tool._model_context = SimpleNamespace(capabilities=SimpleNamespace(allow_code_generation=True))

        response = (
            "Summary before code.\n"
            "<GENERATED-CODE>print('demo')</GENERATED-CODE>\n"
            "### Follow-up\n"
            "Further analysis and guidance after the generated snippet.\n"
        )

        request = ChatRequest(prompt="Test", working_directory_absolute_path=str(tmp_path))

        formatted = tool.format_response(response, request)

        assert "Summary before code." in formatted
        assert "### Follow-up" in formatted
        assert "Further analysis and guidance after the generated snippet." in formatted
        assert "print('demo')" not in formatted

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
        assert "absolute_file_paths" in tool_fields
        assert "images" in tool_fields

        required_fields = self.tool.get_required_fields()
        assert "prompt" in required_fields
        assert "working_directory_absolute_path" in required_fields


class TestChatRequestModel:
    """Test suite for ChatRequest model"""

    def test_field_descriptions(self):
        """Test that field descriptions are proper"""
        from tools.chat import CHAT_FIELD_DESCRIPTIONS

        # Field descriptions should exist and be descriptive
        assert len(CHAT_FIELD_DESCRIPTIONS["prompt"]) > 50
        assert "context" in CHAT_FIELD_DESCRIPTIONS["prompt"]
        files_desc = CHAT_FIELD_DESCRIPTIONS["absolute_file_paths"].lower()
        assert "absolute" in files_desc
        assert "visual context" in CHAT_FIELD_DESCRIPTIONS["images"]
        assert "directory" in CHAT_FIELD_DESCRIPTIONS["working_directory_absolute_path"].lower()

    def test_working_directory_absolute_path_description_matches_behavior(self):
        """Absolute working directory description should reflect existing-directory requirement."""
        from tools.chat import CHAT_FIELD_DESCRIPTIONS

        description = CHAT_FIELD_DESCRIPTIONS["working_directory_absolute_path"].lower()
        assert "existing directory" in description

    @pytest.mark.asyncio
    async def test_working_directory_absolute_path_must_exist(self, tmp_path):
        """Chat tool should reject non-existent working directories."""
        tool = ChatTool()
        missing_dir = tmp_path / "nonexistent_subdir"

        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.execute(
                {
                    "prompt": "test",
                    "absolute_file_paths": [],
                    "images": [],
                    "working_directory_absolute_path": str(missing_dir),
                }
            )

        payload = json.loads(exc_info.value.payload)
        assert payload["status"] == "error"
        assert "existing directory" in payload["content"].lower()

    def test_default_values(self):
        """Test that default values work correctly"""
        request = ChatRequest(prompt="Test", working_directory_absolute_path="/tmp")

        assert request.prompt == "Test"
        assert request.absolute_file_paths == []  # Should default to empty list
        assert request.images == []  # Should default to empty list

    def test_inheritance(self):
        """Test that ChatRequest properly inherits from ToolRequest"""
        from tools.shared.base_models import ToolRequest

        request = ChatRequest(prompt="Test", working_directory_absolute_path="/tmp")
        assert isinstance(request, ToolRequest)

        # Should have inherited fields
        assert hasattr(request, "model")
        assert hasattr(request, "temperature")
        assert hasattr(request, "thinking_mode")
        assert hasattr(request, "continuation_id")
        assert hasattr(request, "images")  # From base model too


if __name__ == "__main__":
    pytest.main([__file__])
