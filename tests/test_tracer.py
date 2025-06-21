"""
Tests for the tracer tool functionality
"""

import pytest

from tools.models import ToolModelCategory
from tools.tracer import TracerRequest, TracerTool


class TestTracerTool:
    """Test suite for the Tracer tool"""

    @pytest.fixture
    def tracer_tool(self):
        """Create a tracer tool instance for testing"""
        return TracerTool()

    def test_get_name(self, tracer_tool):
        """Test that the tool returns the correct name"""
        assert tracer_tool.get_name() == "tracer"

    def test_get_description(self, tracer_tool):
        """Test that the tool returns a comprehensive description"""
        description = tracer_tool.get_description()
        assert "STEP-BY-STEP CODE TRACING WORKFLOW" in description
        assert "precision" in description
        assert "dependencies" in description
        assert "guided investigation" in description

    def test_get_input_schema(self, tracer_tool):
        """Test that the input schema includes required fields"""
        schema = tracer_tool.get_input_schema()

        assert schema["type"] == "object"
        assert "target_description" in schema["properties"]
        assert "trace_mode" in schema["properties"]
        assert "step" in schema["properties"]
        assert "step_number" in schema["properties"]

        # Check trace_mode enum values
        trace_enum = schema["properties"]["trace_mode"]["enum"]
        assert "precision" in trace_enum
        assert "dependencies" in trace_enum

        # Check required fields include workflow fields
        required_fields = set(schema["required"])
        assert "target_description" in required_fields
        assert "trace_mode" in required_fields

    def test_get_model_category(self, tracer_tool):
        """Test that the tracer tool uses EXTENDED_REASONING category"""
        category = tracer_tool.get_model_category()
        assert category == ToolModelCategory.EXTENDED_REASONING

    def test_request_model_validation(self, tracer_tool):
        """Test TracerRequest model validation"""
        # Valid request
        request = TracerRequest(
            step="Analyze BookingManager finalizeInvoice method execution flow",
            step_number=1,
            total_steps=3,
            next_step_required=True,
            findings="Initial investigation of booking finalization process",
            target_description="BookingManager finalizeInvoice method",
            trace_mode="precision",
        )
        assert request.target_description == "BookingManager finalizeInvoice method"
        assert request.trace_mode == "precision"
        assert request.step_number == 1

        # Test invalid trace_mode
        with pytest.raises(ValueError):
            TracerRequest(
                step="Test step",
                step_number=1,
                total_steps=1,
                next_step_required=False,
                findings="Test findings",
                trace_mode="invalid_mode",
            )

    def test_get_required_actions(self, tracer_tool):
        """Test that required actions are provided for each step"""
        # Step 1 - initial investigation
        actions = tracer_tool.get_required_actions(1, "exploring", "Initial findings", 3)
        assert len(actions) > 0
        assert any("search" in action.lower() for action in actions)
        assert any("locate" in action.lower() for action in actions)

        # Later steps with low confidence
        actions = tracer_tool.get_required_actions(2, "low", "Some findings", 3)
        assert len(actions) > 0
        assert any("trace" in action.lower() for action in actions)

        # High confidence steps
        actions = tracer_tool.get_required_actions(3, "high", "Strong findings", 3)
        assert len(actions) > 0
        assert any("verify" in action.lower() for action in actions)

    def test_workflow_tool_characteristics(self, tracer_tool):
        """Test that tracer has proper workflow tool characteristics"""
        # Should not require external expert analysis
        assert not tracer_tool.requires_expert_analysis()

        # Should return TracerRequest as the workflow model
        assert tracer_tool.get_workflow_request_model() == TracerRequest

        # Should not require AI model at MCP boundary
        assert not tracer_tool.requires_model()

    def test_get_rendering_instructions_precision(self, tracer_tool):
        """Test rendering instructions for precision mode"""
        instructions = tracer_tool._get_rendering_instructions("precision")

        assert "PRECISION TRACE" in instructions
        assert "CALL FLOW DIAGRAM" in instructions
        assert "ADDITIONAL ANALYSIS VIEWS" in instructions
        assert "ClassName::MethodName" in instructions
        assert "↓" in instructions

    def test_get_rendering_instructions_dependencies(self, tracer_tool):
        """Test rendering instructions for dependencies mode"""
        instructions = tracer_tool._get_rendering_instructions("dependencies")

        assert "DEPENDENCIES TRACE" in instructions
        assert "DEPENDENCY FLOW DIAGRAM" in instructions
        assert "DEPENDENCY TABLE" in instructions
        assert "INCOMING DEPENDENCIES" in instructions
        assert "OUTGOING DEPENDENCIES" in instructions
        assert "←" in instructions
        assert "→" in instructions

    def test_rendering_instructions_consistency(self, tracer_tool):
        """Test that rendering instructions are consistent between modes"""
        precision_instructions = tracer_tool._get_precision_rendering_instructions()
        dependencies_instructions = tracer_tool._get_dependencies_rendering_instructions()

        # Both should have mandatory instructions
        assert "MANDATORY RENDERING INSTRUCTIONS" in precision_instructions
        assert "MANDATORY RENDERING INSTRUCTIONS" in dependencies_instructions

        # Both should have specific styling requirements
        assert "ONLY" in precision_instructions
        assert "ONLY" in dependencies_instructions

        # Both should have absolute requirements
        assert "ABSOLUTE REQUIREMENTS" in precision_instructions
        assert "ABSOLUTE REQUIREMENTS" in dependencies_instructions

    def test_mode_selection_guidance(self, tracer_tool):
        """Test that the schema provides clear guidance on when to use each mode"""
        schema = tracer_tool.get_input_schema()
        trace_mode_desc = schema["properties"]["trace_mode"]["description"]

        # Should clearly indicate precision is for methods/functions
        assert "execution flow" in trace_mode_desc

        # Should clearly indicate dependencies is for structural relationships
        assert "structural relationships" in trace_mode_desc
