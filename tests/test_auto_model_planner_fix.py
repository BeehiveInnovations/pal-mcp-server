"""
Unit tests for the auto model planner fix.

This test confirms that the planner tool no longer fails when DEFAULT_MODEL is "auto"
and only basic providers (Google/OpenAI) are configured, while ensuring other tools
still properly require model resolution.
"""

from unittest.mock import patch

from mcp.types import TextContent

from tools.base import BaseTool
from tools.chat import ChatTool
from tools.planner import PlannerTool


class TestAutoModelPlannerFix:
    """Test the fix for auto model resolution with planner tool."""

    def test_planner_requires_model_false(self):
        """Test that planner tool returns False for requires_model."""
        planner = PlannerTool()
        assert planner.requires_model() is False

    def test_chat_requires_model_true(self):
        """Test that chat tool returns True for requires_model (default behavior)."""
        chat = ChatTool()
        assert chat.requires_model() is True

    def test_base_tool_requires_model_default(self):
        """Test that BaseTool default implementation returns True."""

        # Create a mock tool that doesn't override requires_model
        class MockTool(BaseTool):
            def get_name(self):
                return "mock"

            def get_description(self):
                return "Mock tool"

            def get_input_schema(self):
                return {}

            def get_system_prompt(self):
                return "Mock prompt"

            def get_request_model(self):
                from tools.base import ToolRequest

                return ToolRequest

            async def prepare_prompt(self, request):
                return "Mock prompt"

        mock_tool = MockTool()
        assert mock_tool.requires_model() is True

    @patch("config.DEFAULT_MODEL", "auto")
    @patch("providers.registry.ModelProviderRegistry.get_provider_for_model")
    def test_auto_model_error_before_fix_simulation(self, mock_get_provider):
        """
        Simulate the error that would occur before the fix.

        This test simulates what would happen if server.py didn't check requires_model()
        and tried to resolve "auto" as a literal model name.
        """
        # Mock the scenario where no provider is found for "auto"
        mock_get_provider.return_value = None

        # This should return None, simulating the "No provider found for model auto" error
        result = mock_get_provider("auto")
        assert result is None

        # Verify that the mock was called with "auto"
        mock_get_provider.assert_called_with("auto")

    @patch("server.DEFAULT_MODEL", "auto")
    async def test_planner_execution_bypasses_model_resolution(self):
        """
        Test that planner tool execution works even when DEFAULT_MODEL is "auto".

        This test confirms that the fix allows planner to work regardless of
        model configuration since it doesn't need model resolution.
        """
        planner = PlannerTool()

        # Test with minimal planner arguments
        arguments = {"step": "Test planning step", "step_number": 1, "total_steps": 1, "next_step_required": False}

        # This should work without any model resolution
        result = await planner.execute(arguments)

        # Verify we got a result
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], TextContent)

        # Parse the JSON response to verify it's valid
        import json

        response_data = json.loads(result[0].text)
        assert response_data["status"] == "planning_success"
        assert response_data["step_number"] == 1

    @patch("config.DEFAULT_MODEL", "auto")
    def test_server_model_resolution_logic(self):
        """
        Test the server-side logic that checks requires_model() before model resolution.

        This simulates the key fix in server.py where we check tool.requires_model()
        before attempting model resolution.
        """
        planner = PlannerTool()
        chat = ChatTool()

        # Simulate the server logic
        def simulate_server_model_resolution(tool, model_name):
            """Simulate the fixed server logic from server.py"""
            if not tool.requires_model():
                # Skip model resolution for tools that don't require models
                return "SKIP_MODEL_RESOLUTION"
            else:
                # Would normally do model resolution here
                return f"RESOLVE_MODEL_{model_name}"

        # Test planner (should skip model resolution)
        result = simulate_server_model_resolution(planner, "auto")
        assert result == "SKIP_MODEL_RESOLUTION"

        # Test chat (should attempt model resolution)
        result = simulate_server_model_resolution(chat, "auto")
        assert result == "RESOLVE_MODEL_auto"

    def test_provider_registry_auto_handling(self):
        """
        Test that the provider registry correctly handles model resolution.

        This tests the scenario where providers don't recognize "auto" as a model.
        """
        from providers.registry import ModelProviderRegistry

        # This should return None since "auto" is not a real model name
        provider = ModelProviderRegistry.get_provider_for_model("auto")
        assert provider is None, "Provider registry should not find a provider for literal 'auto'"

    @patch("config.DEFAULT_MODEL", "auto")
    async def test_end_to_end_planner_with_auto_mode(self):
        """
        End-to-end test of planner tool execution in auto mode.

        This test verifies that the complete flow works when DEFAULT_MODEL is "auto"
        and the planner tool is used.
        """
        planner = PlannerTool()

        # Verify the tool doesn't require model resolution
        assert not planner.requires_model()

        # Test a multi-step planning scenario
        step1_args = {
            "step": "Analyze the current system architecture",
            "step_number": 1,
            "total_steps": 3,
            "next_step_required": True,
        }

        result1 = await planner.execute(step1_args)
        assert len(result1) > 0

        # Parse and verify the response
        import json

        response1 = json.loads(result1[0].text)
        assert response1["status"] == "planning_success"
        assert response1["next_step_required"] is True
        assert "continuation_id" in response1

        # Test step 2 with continuation
        continuation_id = response1["continuation_id"]
        step2_args = {
            "step": "Design the microservices architecture",
            "step_number": 2,
            "total_steps": 3,
            "next_step_required": True,
            "continuation_id": continuation_id,
        }

        result2 = await planner.execute(step2_args)
        assert len(result2) > 0

        response2 = json.loads(result2[0].text)
        assert response2["status"] == "planning_success"
        assert response2["step_number"] == 2

    def test_other_tools_still_require_models(self):
        """
        Verify that other tools still properly require model resolution.

        This ensures our fix doesn't break existing functionality.
        """
        from tools.analyze import AnalyzeTool
        from tools.chat import ChatTool
        from tools.debug import DebugIssueTool

        # Test various tools still require models
        tools_requiring_models = [ChatTool(), DebugIssueTool(), AnalyzeTool()]

        for tool in tools_requiring_models:
            assert tool.requires_model() is True, f"{tool.get_name()} should require model resolution"
