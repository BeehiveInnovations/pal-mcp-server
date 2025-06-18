"""
Tests for the planner tool.
"""

from unittest.mock import patch

import pytest

from tools.models import ToolModelCategory
from tools.planner import PlannerRequest, PlannerTool


class TestPlannerTool:
    """Test suite for PlannerTool."""

    def test_tool_metadata(self):
        """Test basic tool metadata and configuration."""
        tool = PlannerTool()

        assert tool.get_name() == "planner"
        assert "SEQUENTIAL PLANNER" in tool.get_description()
        assert tool.get_default_temperature() == 0.5  # TEMPERATURE_BALANCED
        assert tool.get_model_category() == ToolModelCategory.EXTENDED_REASONING
        assert tool.get_default_thinking_mode() == "high"

    def test_request_validation(self):
        """Test Pydantic request model validation."""
        # Valid interactive step request
        step_request = PlannerRequest(
            step="Create database migration scripts", step_number=3, total_steps=10, next_step_required=True
        )
        assert step_request.step == "Create database migration scripts"
        assert step_request.step_number == 3
        assert step_request.next_step_required is True
        assert step_request.is_step_revision is False  # default

        # Missing required fields should fail
        with pytest.raises(ValueError):
            PlannerRequest()  # Missing all required fields

        with pytest.raises(ValueError):
            PlannerRequest(step="test")  # Missing other required fields

    def test_input_schema_generation(self):
        """Test JSON schema generation for MCP client."""
        tool = PlannerTool()
        schema = tool.get_input_schema()

        assert schema["type"] == "object"
        # Interactive planning fields
        assert "step" in schema["properties"]
        assert "step_number" in schema["properties"]
        assert "total_steps" in schema["properties"]
        assert "next_step_required" in schema["properties"]
        assert "is_step_revision" in schema["properties"]
        assert "is_branch_point" in schema["properties"]
        assert "branch_id" in schema["properties"]
        assert "continuation_id" in schema["properties"]

        # Check excluded fields are NOT present
        assert "model" not in schema["properties"]
        assert "images" not in schema["properties"]
        assert "files" not in schema["properties"]
        assert "temperature" not in schema["properties"]
        assert "thinking_mode" not in schema["properties"]
        assert "use_websearch" not in schema["properties"]

        # Check required fields
        assert "step" in schema["required"]
        assert "step_number" in schema["required"]
        assert "total_steps" in schema["required"]
        assert "next_step_required" in schema["required"]

    def test_model_category_for_planning(self):
        """Test that planner uses extended reasoning category."""
        tool = PlannerTool()
        category = tool.get_model_category()

        # Planning needs deep thinking
        assert category == ToolModelCategory.EXTENDED_REASONING

    @pytest.mark.asyncio
    async def test_execute_first_step(self):
        """Test execute method for first planning step."""
        tool = PlannerTool()
        arguments = {
            "step": "Plan a microservices migration for our monolithic e-commerce platform",
            "step_number": 1,
            "total_steps": 10,
            "next_step_required": True,
        }

        # Mock conversation memory functions
        with patch("utils.conversation_memory.create_thread", return_value="test-uuid-123"):
            with patch("utils.conversation_memory.add_turn"):
                result = await tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        assert result[0].type == "text"

        # Parse the JSON response
        import json

        parsed_response = json.loads(result[0].text)

        assert parsed_response["step_number"] == 1
        assert parsed_response["total_steps"] == 10
        assert parsed_response["next_step_required"] is True
        assert parsed_response["continuation_id"] == "test-uuid-123"
        assert parsed_response["status"] == "planning_success"

    @pytest.mark.asyncio
    async def test_execute_subsequent_step(self):
        """Test execute method for subsequent planning step."""
        tool = PlannerTool()
        arguments = {
            "step": "Set up deployment configuration for each microservice",
            "step_number": 2,
            "total_steps": 8,
            "next_step_required": True,
            "continuation_id": "existing-uuid-456",
        }

        # Mock conversation memory functions
        with patch("utils.conversation_memory.add_turn"):
            result = await tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        assert result[0].type == "text"

        # Parse the JSON response
        import json

        parsed_response = json.loads(result[0].text)

        assert parsed_response["step_number"] == 2
        assert parsed_response["total_steps"] == 8
        assert parsed_response["next_step_required"] is True
        assert parsed_response["continuation_id"] == "existing-uuid-456"
        assert parsed_response["status"] == "planning_success"

    @pytest.mark.asyncio
    async def test_execute_with_continuation_context(self):
        """Test execute method with continuation that loads previous context."""
        tool = PlannerTool()
        arguments = {
            "step": "Continue planning the deployment phase",
            "step_number": 1,  # Step 1 with continuation_id loads context
            "total_steps": 8,
            "next_step_required": True,
            "continuation_id": "test-continuation-id",
        }

        # Mock thread with completed plan
        from utils.conversation_memory import ConversationTurn, ThreadContext

        mock_turn = ConversationTurn(
            role="assistant",
            content='{"status": "planning_success", "planning_complete": true, "plan_summary": "COMPLETE PLAN: Authentication system with 3 steps completed"}',
            tool_name="planner",
            model_name="claude-planner",
            timestamp="2024-01-01T00:00:00Z",
        )
        mock_thread = ThreadContext(
            thread_id="test-id",
            tool_name="planner",
            turns=[mock_turn],
            created_at="2024-01-01T00:00:00Z",
            last_updated_at="2024-01-01T00:00:00Z",
            initial_context={},
        )

        with patch("utils.conversation_memory.get_thread", return_value=mock_thread):
            with patch("utils.conversation_memory.add_turn"):
                result = await tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        response_text = result[0].text

        # Should include previous plan context in JSON
        import json

        parsed_response = json.loads(response_text)

        # Check for previous plan context in the structured response
        assert "previous_plan_context" in parsed_response
        assert "Authentication system" in parsed_response["previous_plan_context"]

    @pytest.mark.asyncio
    async def test_execute_final_step(self):
        """Test execute method for final planning step."""
        tool = PlannerTool()
        arguments = {
            "step": "Deploy and monitor the new system",
            "step_number": 10,
            "total_steps": 10,
            "next_step_required": False,  # Final step
            "continuation_id": "test-uuid-789",
        }

        # Mock conversation memory functions
        with patch("utils.conversation_memory.add_turn"):
            result = await tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        response_text = result[0].text

        # Parse the structured JSON response
        import json

        parsed_response = json.loads(response_text)

        # Check final step structure
        assert parsed_response["status"] == "planning_success"
        assert parsed_response["step_number"] == 10
        assert parsed_response["planning_complete"] is True
        assert "plan_summary" in parsed_response
        assert "COMPLETE PLAN:" in parsed_response["plan_summary"]

    @pytest.mark.asyncio
    async def test_execute_with_branching(self):
        """Test execute method with branching."""
        tool = PlannerTool()
        arguments = {
            "step": "Use Kubernetes for orchestration",
            "step_number": 4,
            "total_steps": 10,
            "next_step_required": True,
            "is_branch_point": True,
            "branch_from_step": 3,
            "branch_id": "cloud-native-path",
            "continuation_id": "test-uuid-branch",
        }

        # Mock conversation memory functions
        with patch("utils.conversation_memory.add_turn"):
            result = await tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        response_text = result[0].text

        # Parse the JSON response
        import json

        parsed_response = json.loads(response_text)

        assert parsed_response["metadata"]["branches"] == ["cloud-native-path"]
        assert "cloud-native-path" in str(tool.branches)

    @pytest.mark.asyncio
    async def test_execute_with_revision(self):
        """Test execute method with step revision."""
        tool = PlannerTool()
        arguments = {
            "step": "Revise API design to use GraphQL instead of REST",
            "step_number": 3,
            "total_steps": 8,
            "next_step_required": True,
            "is_step_revision": True,
            "revises_step_number": 2,
            "continuation_id": "test-uuid-revision",
        }

        # Mock conversation memory functions
        with patch("utils.conversation_memory.add_turn"):
            result = await tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        response_text = result[0].text

        # Parse the JSON response
        import json

        parsed_response = json.loads(response_text)

        assert parsed_response["step_number"] == 3
        assert parsed_response["next_step_required"] is True
        assert parsed_response["metadata"]["is_step_revision"] is True
        assert parsed_response["metadata"]["revises_step_number"] == 2

        # Check that step data was stored in history
        assert len(tool.step_history) > 0
        latest_step = tool.step_history[-1]
        assert latest_step["is_step_revision"] is True
        assert latest_step["revises_step_number"] == 2

    @pytest.mark.asyncio
    async def test_execute_adjusts_total_steps(self):
        """Test execute method adjusts total steps when current step exceeds estimate."""
        tool = PlannerTool()
        arguments = {
            "step": "Additional step discovered during planning",
            "step_number": 8,
            "total_steps": 5,  # Current step exceeds total
            "next_step_required": True,
            "continuation_id": "test-uuid-adjust",
        }

        # Mock conversation memory functions
        with patch("utils.conversation_memory.add_turn"):
            result = await tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        response_text = result[0].text

        # Parse the JSON response
        import json

        parsed_response = json.loads(response_text)

        # Total steps should be adjusted to match current step
        assert parsed_response["total_steps"] == 8
        assert parsed_response["step_number"] == 8
        assert parsed_response["status"] == "planning_success"

    @pytest.mark.asyncio
    async def test_execute_error_handling(self):
        """Test execute method error handling."""
        tool = PlannerTool()
        # Invalid arguments - missing required fields
        arguments = {
            "step": "Invalid request"
            # Missing required fields: step_number, total_steps, next_step_required
        }

        result = await tool.execute(arguments)

        # Should return error response
        assert len(result) == 1
        response_text = result[0].text

        # Parse the JSON response
        import json

        parsed_response = json.loads(response_text)

        assert parsed_response["status"] == "planning_failed"
        assert "error" in parsed_response

    @pytest.mark.asyncio
    async def test_execute_step_history_tracking(self):
        """Test that execute method properly tracks step history."""
        tool = PlannerTool()

        # Execute multiple steps
        step1_args = {"step": "First step", "step_number": 1, "total_steps": 3, "next_step_required": True}

        step2_args = {
            "step": "Second step",
            "step_number": 2,
            "total_steps": 3,
            "next_step_required": True,
            "continuation_id": "test-uuid-history",
        }

        # Mock conversation memory functions
        with patch("utils.conversation_memory.create_thread", return_value="test-uuid-history"):
            with patch("utils.conversation_memory.add_turn"):
                await tool.execute(step1_args)
                await tool.execute(step2_args)

        # Should have tracked both steps
        assert len(tool.step_history) == 2
        assert tool.step_history[0]["step"] == "First step"
        assert tool.step_history[1]["step"] == "Second step"


# Integration test
class TestPlannerToolIntegration:
    """Integration tests for planner tool."""

    def setup_method(self):
        """Set up model context for integration tests."""
        from utils.model_context import ModelContext

        self.tool = PlannerTool()
        self.tool._model_context = ModelContext("flash")  # Test model

    @pytest.mark.asyncio
    async def test_interactive_planning_flow(self):
        """Test complete interactive planning flow."""
        arguments = {
            "step": "Plan a complete system redesign",
            "step_number": 1,
            "total_steps": 5,
            "next_step_required": True,
        }

        # Mock conversation memory functions
        with patch("utils.conversation_memory.create_thread", return_value="test-flow-uuid"):
            with patch("utils.conversation_memory.add_turn"):
                result = await self.tool.execute(arguments)

        # Verify response structure
        assert len(result) == 1
        response_text = result[0].text

        # Parse the JSON response
        import json

        parsed_response = json.loads(response_text)

        assert parsed_response["step_number"] == 1
        assert parsed_response["total_steps"] == 5
        assert parsed_response["continuation_id"] == "test-flow-uuid"
        assert parsed_response["status"] == "planning_success"
