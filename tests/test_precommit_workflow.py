"""
Unit tests for the workflow-based PrecommitTool

Tests the core functionality of the precommit workflow tool including:
- Tool metadata and configuration
- Request model validation
- Workflow step handling
- Tool categorization
"""

import pytest

from tools.models import ToolModelCategory
from tools.precommit import PrecommitRequest, PrecommitTool


class TestPrecommitWorkflowTool:
    """Test suite for the workflow-based PrecommitTool"""

    def test_tool_metadata(self):
        """Test basic tool metadata"""
        tool = PrecommitTool()

        assert tool.get_name() == "precommit"
        assert "git changes" in tool.get_description()
        assert "systematic analysis" in tool.get_description()

    def test_tool_model_category(self):
        """Test that precommit tool uses extended reasoning category"""
        tool = PrecommitTool()
        assert tool.get_model_category() == ToolModelCategory.EXTENDED_REASONING

    def test_default_temperature(self):
        """Test analytical temperature setting"""
        tool = PrecommitTool()
        temp = tool.get_default_temperature()
        # Should be analytical temperature (0.2)
        assert temp == 0.2

    def test_request_model_basic_validation(self):
        """Test basic request model validation"""
        # Valid minimal workflow request
        request = PrecommitRequest(
            step="Initial validation step",
            step_number=1,
            total_steps=3,
            next_step_required=True,
            findings="Initial findings",
            path="/test/repo",  # Required for step 1
        )

        assert request.step == "Initial validation step"
        assert request.step_number == 1
        assert request.total_steps == 3
        assert request.next_step_required is True
        assert request.findings == "Initial findings"
        assert request.path == "/test/repo"

    def test_request_model_step_one_validation(self):
        """Test that step 1 requires path field"""
        # Step 1 without path should fail
        with pytest.raises(ValueError, match="Step 1 requires 'path' field"):
            PrecommitRequest(
                step="Initial validation step",
                step_number=1,
                total_steps=3,
                next_step_required=True,
                findings="Initial findings",
                # Missing path for step 1
            )

    def test_request_model_later_steps_no_path_required(self):
        """Test that later steps don't require path"""
        # Step 2+ without path should be fine
        request = PrecommitRequest(
            step="Continued validation",
            step_number=2,
            total_steps=3,
            next_step_required=True,
            findings="Detailed findings",
            # No path needed for step 2+
        )

        assert request.step_number == 2
        assert request.path is None

    def test_request_model_optional_fields(self):
        """Test optional workflow fields"""
        request = PrecommitRequest(
            step="Validation with optional fields",
            step_number=1,
            total_steps=2,
            next_step_required=False,
            findings="Comprehensive findings",
            path="/test/repo",
            precommit_type="external",
            files_checked=["/file1.py", "/file2.py"],
            relevant_files=["/file1.py"],
            relevant_context=["function_name", "class_name"],
            issues_found=[{"severity": "medium", "description": "Test issue"}],
            images=["/screenshot.png"],
        )

        assert request.precommit_type == "external"
        assert len(request.files_checked) == 2
        assert len(request.relevant_files) == 1
        assert len(request.relevant_context) == 2
        assert len(request.issues_found) == 1
        assert len(request.images) == 1

    def test_precommit_specific_fields(self):
        """Test precommit-specific configuration fields"""
        request = PrecommitRequest(
            step="Validation with git config",
            step_number=1,
            total_steps=1,
            next_step_required=False,
            findings="Complete validation",
            path="/repo",
            compare_to="main",
            include_staged=True,
            include_unstaged=False,
            focus_on="security issues",
            severity_filter="high",
        )

        assert request.compare_to == "main"
        assert request.include_staged is True
        assert request.include_unstaged is False
        assert request.focus_on == "security issues"
        assert request.severity_filter == "high"

    def test_precommit_type_validation(self):
        """Test precommit type validation"""
        valid_types = ["external", "internal"]

        for precommit_type in valid_types:
            request = PrecommitRequest(
                step="Test precommit type",
                step_number=1,
                total_steps=1,
                next_step_required=False,
                findings="Test findings",
                path="/repo",
                precommit_type=precommit_type,
            )
            assert request.precommit_type == precommit_type

        # Test default is external
        request = PrecommitRequest(
            step="Test default type",
            step_number=1,
            total_steps=1,
            next_step_required=False,
            findings="Test findings",
            path="/repo",
        )
        assert request.precommit_type == "external"

    def test_severity_filter_options(self):
        """Test severity filter validation"""
        valid_severities = ["critical", "high", "medium", "low", "all"]

        for severity in valid_severities:
            request = PrecommitRequest(
                step="Test severity filter",
                step_number=1,
                total_steps=1,
                next_step_required=False,
                findings="Test findings",
                path="/repo",
                severity_filter=severity,
            )
            assert request.severity_filter == severity

    def test_input_schema_generation(self):
        """Test that input schema is generated correctly"""
        tool = PrecommitTool()
        schema = tool.get_input_schema()

        # Check basic schema structure
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        # Check required fields are present
        required_fields = {"step", "step_number", "total_steps", "next_step_required", "findings"}
        assert all(field in schema["properties"] for field in required_fields)

        # Check model field is present and configured correctly
        assert "model" in schema["properties"]
        assert schema["properties"]["model"]["type"] == "string"

    def test_workflow_request_model_method(self):
        """Test get_workflow_request_model returns correct model"""
        tool = PrecommitTool()
        assert tool.get_workflow_request_model() == PrecommitRequest
        assert tool.get_request_model() == PrecommitRequest

    def test_system_prompt_integration(self):
        """Test system prompt integration"""
        tool = PrecommitTool()
        system_prompt = tool.get_system_prompt()

        # Should get the precommit prompt
        assert isinstance(system_prompt, str)
        assert len(system_prompt) > 0
