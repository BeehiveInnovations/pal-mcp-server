"""
Tests for the debug tool using new WorkflowTool architecture.
"""

from tools.debug import DebugInvestigationRequest, DebugIssueTool
from tools.models import ToolModelCategory


class TestDebugTool:
    """Test suite for DebugIssueTool using new WorkflowTool architecture."""

    def test_tool_metadata(self):
        """Test basic tool metadata and configuration."""
        tool = DebugIssueTool()

        assert tool.get_name() == "debug"
        assert "debugging and root cause analysis" in tool.get_description()
        assert tool.get_default_temperature() == 0.2  # TEMPERATURE_ANALYTICAL
        assert tool.get_model_category() == ToolModelCategory.EXTENDED_REASONING
        assert tool.requires_model() is True

    def test_request_validation(self):
        """Test Pydantic request model validation."""
        # Valid investigation step request
        step_request = DebugInvestigationRequest(
            step="Investigating null pointer exception in UserService",
            step_number=1,
            total_steps=3,
            next_step_required=True,
            findings="Found potential null reference in user authentication flow",
            files_checked=["/src/UserService.java"],
            relevant_files=["/src/UserService.java"],
            relevant_context=["authenticate", "validateUser"],
            confidence="medium",
            hypothesis="Null pointer occurs when user object is not properly validated",
        )

        assert step_request.step_number == 1
        assert step_request.confidence == "medium"
        assert len(step_request.relevant_context) == 2

    def test_input_schema_generation(self):
        """Test that input schema is generated correctly."""
        tool = DebugIssueTool()
        schema = tool.get_input_schema()

        # Verify required investigation fields are present
        assert "step" in schema["properties"]
        assert "step_number" in schema["properties"]
        assert "total_steps" in schema["properties"]
        assert "next_step_required" in schema["properties"]
        assert "findings" in schema["properties"]
        assert "relevant_context" in schema["properties"]

        # Verify field types
        assert schema["properties"]["step"]["type"] == "string"
        assert schema["properties"]["step_number"]["type"] == "integer"
        assert schema["properties"]["next_step_required"]["type"] == "boolean"
        assert schema["properties"]["relevant_context"]["type"] == "array"

    def test_model_category_for_debugging(self):
        """Test that debug tool correctly identifies as extended reasoning category."""
        tool = DebugIssueTool()
        assert tool.get_model_category() == ToolModelCategory.EXTENDED_REASONING

    def test_relevant_context_handling(self):
        """Test that relevant_context is handled correctly."""
        request = DebugInvestigationRequest(
            step="Test investigation",
            step_number=1,
            total_steps=2,
            next_step_required=True,
            findings="Test findings",
            relevant_context=["method1", "method2"],
        )

        # Should have relevant_context directly
        assert request.relevant_context == ["method1", "method2"]

        # Test step data preparation
        tool = DebugIssueTool()
        step_data = tool.prepare_step_data(request)
        assert step_data["relevant_context"] == ["method1", "method2"]
