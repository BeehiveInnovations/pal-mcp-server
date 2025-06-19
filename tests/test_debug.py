"""
Tests for the debug tool.
"""

from unittest.mock import patch

import pytest

from tools.debug import DebugInvestigationRequest, DebugIssueTool
from tools.models import ToolModelCategory


class TestDebugTool:
    """Test suite for DebugIssueTool."""

    def test_tool_metadata(self):
        """Test basic tool metadata and configuration."""
        tool = DebugIssueTool()

        assert tool.get_name() == "debug"
        assert "DEBUG & ROOT CAUSE ANALYSIS" in tool.get_description()
        assert tool.get_default_temperature() == 0.2  # TEMPERATURE_ANALYTICAL
        assert tool.get_model_category() == ToolModelCategory.EXTENDED_REASONING
        assert tool.requires_model() is False  # Since it manages its own model calls

    def test_request_validation(self):
        """Test Pydantic request model validation."""
        # Valid investigation step request
        step_request = DebugInvestigationRequest(
            step="Investigating null pointer exception in UserService",
            step_number=1,
            total_steps=5,
            next_step_required=True,
            findings="Found that UserService.getUser() is called with null ID",
        )
        assert step_request.step == "Investigating null pointer exception in UserService"
        assert step_request.step_number == 1
        assert step_request.next_step_required is True
        assert step_request.confidence == "low"  # default

        # Request with optional fields
        detailed_request = DebugInvestigationRequest(
            step="Deep dive into getUser method implementation",
            step_number=2,
            total_steps=5,
            next_step_required=True,
            findings="Method doesn't validate input parameters",
            files_checked=["/src/UserService.java", "/src/UserController.java"],
            relevant_files=["/src/UserService.java"],
            relevant_methods=["UserService.getUser", "UserController.handleRequest"],
            hypothesis="Null ID passed from controller without validation",
            confidence="medium",
        )
        assert len(detailed_request.files_checked) == 2
        assert len(detailed_request.relevant_files) == 1
        assert detailed_request.confidence == "medium"

        # Missing required fields should fail
        with pytest.raises(ValueError):
            DebugInvestigationRequest()  # Missing all required fields

        with pytest.raises(ValueError):
            DebugInvestigationRequest(step="test")  # Missing other required fields

    def test_input_schema_generation(self):
        """Test JSON schema generation for MCP client."""
        tool = DebugIssueTool()
        schema = tool.get_input_schema()

        assert schema["type"] == "object"
        # Investigation fields
        assert "step" in schema["properties"]
        assert "step_number" in schema["properties"]
        assert "total_steps" in schema["properties"]
        assert "next_step_required" in schema["properties"]
        assert "findings" in schema["properties"]
        assert "files_checked" in schema["properties"]
        assert "relevant_files" in schema["properties"]
        assert "relevant_methods" in schema["properties"]
        assert "hypothesis" in schema["properties"]
        assert "confidence" in schema["properties"]
        assert "backtrack_from_step" in schema["properties"]
        assert "continuation_id" in schema["properties"]
        assert "images" in schema["properties"]  # Now supported for visual debugging

        # Check excluded fields are NOT present
        assert "model" not in schema["properties"]
        assert "temperature" not in schema["properties"]
        assert "thinking_mode" not in schema["properties"]
        assert "use_websearch" not in schema["properties"]

        # Check required fields
        assert "step" in schema["required"]
        assert "step_number" in schema["required"]
        assert "total_steps" in schema["required"]
        assert "next_step_required" in schema["required"]
        assert "findings" in schema["required"]

    def test_model_category_for_debugging(self):
        """Test that debug uses extended reasoning category."""
        tool = DebugIssueTool()
        category = tool.get_model_category()

        # Debugging needs deep thinking
        assert category == ToolModelCategory.EXTENDED_REASONING

    @pytest.mark.asyncio
    async def test_execute_first_investigation_step(self):
        """Test execute method for first investigation step."""
        tool = DebugIssueTool()
        arguments = {
            "step": "Investigating intermittent session validation failures in production",
            "step_number": 1,
            "total_steps": 5,
            "next_step_required": True,
            "findings": "Users report random session invalidation, occurs more during high traffic",
            "files_checked": ["/api/session_manager.py"],
            "relevant_files": ["/api/session_manager.py"],
        }

        # Mock conversation memory functions
        with patch("utils.conversation_memory.create_thread", return_value="debug-uuid-123"):
            with patch("utils.conversation_memory.add_turn"):
                result = await tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        assert result[0].type == "text"

        # Parse the JSON response
        import json

        parsed_response = json.loads(result[0].text)

        assert parsed_response["status"] == "investigation_in_progress"
        assert parsed_response["step_number"] == 1
        assert parsed_response["total_steps"] == 5
        assert parsed_response["next_step_required"] is True
        assert parsed_response["continuation_id"] == "debug-uuid-123"
        assert parsed_response["investigation_status"]["files_checked"] == 1
        assert parsed_response["investigation_status"]["relevant_files"] == 1

    @pytest.mark.asyncio
    async def test_execute_subsequent_investigation_step(self):
        """Test execute method for subsequent investigation step."""
        tool = DebugIssueTool()

        # Set up initial state
        tool.initial_issue = "Session validation failures"
        tool.consolidated_findings["files_checked"].add("/api/session_manager.py")

        arguments = {
            "step": "Examining session cleanup method for concurrent modification issues",
            "step_number": 2,
            "total_steps": 5,
            "next_step_required": True,
            "findings": "Found dictionary modification during iteration in cleanup_expired_sessions",
            "files_checked": ["/api/session_manager.py", "/api/utils.py"],
            "relevant_files": ["/api/session_manager.py"],
            "relevant_methods": ["SessionManager.cleanup_expired_sessions"],
            "hypothesis": "Dictionary modified during iteration causing RuntimeError",
            "confidence": "high",
            "continuation_id": "debug-uuid-123",
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
        assert parsed_response["next_step_required"] is True
        assert parsed_response["continuation_id"] == "debug-uuid-123"
        assert parsed_response["investigation_status"]["files_checked"] == 2  # Cumulative
        assert parsed_response["investigation_status"]["relevant_methods"] == 1
        assert parsed_response["investigation_status"]["current_confidence"] == "high"

    @pytest.mark.asyncio
    async def test_execute_final_investigation_step(self):
        """Test execute method for final investigation step with expert analysis."""
        tool = DebugIssueTool()

        # Set up investigation history
        tool.initial_issue = "Session validation failures"
        tool.investigation_history = [
            {
                "step_number": 1,
                "step": "Initial investigation of session validation failures",
                "findings": "Initial investigation",
                "files_checked": ["/api/utils.py"],
            },
            {
                "step_number": 2,
                "step": "Deeper analysis of session manager",
                "findings": "Found dictionary issue",
                "files_checked": ["/api/session_manager.py"],
            },
        ]
        tool.consolidated_findings = {
            "files_checked": {"/api/session_manager.py", "/api/utils.py"},
            "relevant_files": {"/api/session_manager.py"},
            "relevant_methods": {"SessionManager.cleanup_expired_sessions"},
            "findings": ["Step 1: Initial investigation", "Step 2: Found dictionary issue"],
            "hypotheses": [{"step": 2, "hypothesis": "Dictionary modified during iteration", "confidence": "high"}],
            "images": [],
        }

        arguments = {
            "step": "Confirmed the root cause and identified fix",
            "step_number": 3,
            "total_steps": 3,
            "next_step_required": False,  # Final step
            "findings": "Root cause confirmed: dictionary modification during iteration in cleanup method",
            "files_checked": ["/api/session_manager.py"],
            "relevant_files": ["/api/session_manager.py"],
            "relevant_methods": ["SessionManager.cleanup_expired_sessions"],
            "hypothesis": "Dictionary modification during iteration causes intermittent RuntimeError",
            "confidence": "high",
            "continuation_id": "debug-uuid-123",
        }

        # Mock the expert analysis call
        mock_expert_response = {
            "status": "analysis_complete",
            "summary": "Dictionary modification during iteration bug identified",
            "hypotheses": [
                {
                    "name": "CONCURRENT_MODIFICATION",
                    "confidence": "High",
                    "root_cause": "Modifying dictionary while iterating",
                    "minimal_fix": "Create list of keys to delete first",
                }
            ],
        }

        # Mock conversation memory and file reading
        with patch("utils.conversation_memory.add_turn"):
            with patch.object(tool, "_call_expert_analysis", return_value=mock_expert_response):
                with patch.object(tool, "_prepare_file_content_for_prompt", return_value=("file content", 100)):
                    result = await tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        response_text = result[0].text

        # Parse the JSON response
        import json

        parsed_response = json.loads(response_text)

        # Check final step structure
        assert parsed_response["status"] == "calling_expert_analysis"
        assert parsed_response["investigation_complete"] is True
        assert parsed_response["expert_analysis"]["status"] == "analysis_complete"
        assert "complete_investigation" in parsed_response
        assert parsed_response["complete_investigation"]["steps_taken"] == 3  # All steps including current

    @pytest.mark.asyncio
    async def test_execute_with_backtracking(self):
        """Test execute method with backtracking to revise findings."""
        tool = DebugIssueTool()

        # Set up some investigation history with all required fields
        tool.investigation_history = [
            {
                "step": "Initial investigation",
                "step_number": 1,
                "findings": "Initial findings",
                "files_checked": ["file1.py"],
                "relevant_files": [],
                "relevant_methods": [],
                "hypothesis": None,
                "confidence": "low",
            },
            {
                "step": "Wrong direction",
                "step_number": 2,
                "findings": "Wrong path",
                "files_checked": ["file2.py"],
                "relevant_files": [],
                "relevant_methods": [],
                "hypothesis": None,
                "confidence": "low",
            },
        ]
        tool.consolidated_findings = {
            "files_checked": {"file1.py", "file2.py"},
            "relevant_files": set(),
            "relevant_methods": set(),
            "findings": ["Step 1: Initial findings", "Step 2: Wrong path"],
            "hypotheses": [],
            "images": [],
        }

        arguments = {
            "step": "Backtracking to revise approach",
            "step_number": 3,
            "total_steps": 5,
            "next_step_required": True,
            "findings": "Taking a different investigation approach",
            "files_checked": ["file3.py"],
            "backtrack_from_step": 2,  # Backtrack from step 2
            "continuation_id": "debug-uuid-123",
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

        assert parsed_response["status"] == "investigation_in_progress"
        # After backtracking from step 2, history should have step 1 plus the new step
        assert len(tool.investigation_history) == 2  # Step 1 + new step 3
        assert tool.investigation_history[0]["step_number"] == 1
        assert tool.investigation_history[1]["step_number"] == 3  # The new step that triggered backtrack

    @pytest.mark.asyncio
    async def test_execute_adjusts_total_steps(self):
        """Test execute method adjusts total steps when current step exceeds estimate."""
        tool = DebugIssueTool()
        arguments = {
            "step": "Additional investigation needed",
            "step_number": 8,
            "total_steps": 5,  # Current step exceeds total
            "next_step_required": True,
            "findings": "More complexity discovered",
            "continuation_id": "debug-uuid-123",
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

    @pytest.mark.asyncio
    async def test_execute_error_handling(self):
        """Test execute method error handling."""
        tool = DebugIssueTool()
        # Invalid arguments - missing required fields
        arguments = {
            "step": "Invalid request"
            # Missing required fields
        }

        result = await tool.execute(arguments)

        # Should return error response
        assert len(result) == 1
        response_text = result[0].text

        # Parse the JSON response
        import json

        parsed_response = json.loads(response_text)

        assert parsed_response["status"] == "investigation_failed"
        assert "error" in parsed_response

    def test_prepare_investigation_summary(self):
        """Test investigation summary preparation."""
        tool = DebugIssueTool()
        tool.consolidated_findings = {
            "files_checked": {"file1.py", "file2.py", "file3.py"},
            "relevant_files": {"file1.py", "file2.py"},
            "relevant_methods": {"Class1.method1", "Class2.method2"},
            "findings": [
                "Step 1: Initial investigation findings",
                "Step 2: Discovered potential issue",
                "Step 3: Confirmed root cause",
            ],
            "hypotheses": [
                {"step": 1, "hypothesis": "Initial hypothesis", "confidence": "low"},
                {"step": 2, "hypothesis": "Refined hypothesis", "confidence": "medium"},
                {"step": 3, "hypothesis": "Final hypothesis", "confidence": "high"},
            ],
            "images": [],
        }

        summary = tool._prepare_investigation_summary()

        assert "SYSTEMATIC INVESTIGATION SUMMARY" in summary
        assert "Files examined: 3" in summary
        assert "Relevant files identified: 2" in summary
        assert "Methods/functions involved: 2" in summary
        assert "INVESTIGATION PROGRESSION" in summary
        assert "Step 1:" in summary
        assert "Step 2:" in summary
        assert "Step 3:" in summary
        assert "HYPOTHESIS EVOLUTION" in summary
        assert "low confidence" in summary
        assert "medium confidence" in summary
        assert "high confidence" in summary

    def test_extract_error_context(self):
        """Test error context extraction from findings."""
        tool = DebugIssueTool()
        tool.consolidated_findings = {
            "findings": [
                "Step 1: Found no issues initially",
                "Step 2: Discovered ERROR: Dictionary size changed during iteration",
                "Step 3: Stack trace shows RuntimeError in cleanup method",
                "Step 4: Exception occurs intermittently",
            ],
        }

        error_context = tool._extract_error_context()

        assert error_context is not None
        assert "ERROR: Dictionary size changed" in error_context
        assert "Stack trace shows RuntimeError" in error_context
        assert "Exception occurs intermittently" in error_context
        assert "Found no issues initially" not in error_context  # Should not include non-error findings

    def test_reprocess_consolidated_findings(self):
        """Test reprocessing of consolidated findings after backtracking."""
        tool = DebugIssueTool()
        tool.investigation_history = [
            {
                "step_number": 1,
                "findings": "Initial findings",
                "files_checked": ["file1.py"],
                "relevant_files": ["file1.py"],
                "relevant_methods": ["method1"],
                "hypothesis": "Initial hypothesis",
                "confidence": "low",
            },
            {
                "step_number": 2,
                "findings": "Second findings",
                "files_checked": ["file2.py"],
                "relevant_files": [],
                "relevant_methods": ["method2"],
            },
        ]

        tool._reprocess_consolidated_findings()

        assert tool.consolidated_findings["files_checked"] == {"file1.py", "file2.py"}
        assert tool.consolidated_findings["relevant_files"] == {"file1.py"}
        assert tool.consolidated_findings["relevant_methods"] == {"method1", "method2"}
        assert len(tool.consolidated_findings["findings"]) == 2
        assert len(tool.consolidated_findings["hypotheses"]) == 1
        assert tool.consolidated_findings["hypotheses"][0]["hypothesis"] == "Initial hypothesis"


# Integration test
class TestDebugToolIntegration:
    """Integration tests for debug tool."""

    def setup_method(self):
        """Set up model context for integration tests."""
        from utils.model_context import ModelContext

        self.tool = DebugIssueTool()
        self.tool._model_context = ModelContext("flash")  # Test model

    @pytest.mark.asyncio
    async def test_complete_investigation_flow(self):
        """Test complete investigation flow from start to expert analysis."""
        # Step 1: Initial investigation
        arguments = {
            "step": "Investigating memory leak in data processing pipeline",
            "step_number": 1,
            "total_steps": 3,
            "next_step_required": True,
            "findings": "High memory usage observed during batch processing",
            "files_checked": ["/processor/main.py"],
        }

        # Mock conversation memory and expert analysis
        with patch("utils.conversation_memory.create_thread", return_value="debug-flow-uuid"):
            with patch("utils.conversation_memory.add_turn"):
                result = await self.tool.execute(arguments)

        # Verify response structure
        assert len(result) == 1
        response_text = result[0].text

        # Parse the JSON response
        import json

        parsed_response = json.loads(response_text)

        assert parsed_response["status"] == "investigation_in_progress"
        assert parsed_response["step_number"] == 1
        assert parsed_response["continuation_id"] == "debug-flow-uuid"

    @pytest.mark.asyncio
    async def test_model_context_initialization_in_expert_analysis(self):
        """Real integration test that model context is properly initialized when expert analysis is called."""
        tool = DebugIssueTool()

        # Do NOT manually set up model context - let the method do it itself

        # Set up investigation state for final step
        tool.initial_issue = "Memory leak investigation"
        tool.investigation_history = [
            {
                "step_number": 1,
                "step": "Initial investigation",
                "findings": "Found memory issues",
                "files_checked": [],
            }
        ]
        tool.consolidated_findings = {
            "files_checked": set(),
            "relevant_files": set(),  # No files to avoid file I/O in this test
            "relevant_methods": {"process_data"},
            "findings": ["Step 1: Found memory issues"],
            "hypotheses": [],
            "images": [],
        }

        # Test the _call_expert_analysis method directly to verify ModelContext is properly handled
        # This is the real test - we're testing that the method can be called without the ModelContext error
        try:
            # Only mock the API call itself, not the model resolution infrastructure
            from unittest.mock import MagicMock

            mock_provider = MagicMock()
            mock_response = MagicMock()
            mock_response.content = '{"status": "analysis_complete", "summary": "Test completed"}'
            mock_provider.generate_content.return_value = mock_response

            # Use the real get_model_provider method but override its result to avoid API calls
            original_get_provider = tool.get_model_provider
            tool.get_model_provider = lambda model_name: mock_provider

            try:
                # Create mock arguments and request for model resolution
                from tools.debug import DebugInvestigationRequest
                mock_arguments = {"model": None}  # No model specified, should fall back to DEFAULT_MODEL
                mock_request = DebugInvestigationRequest(
                    step="Test step",
                    step_number=1,
                    total_steps=1,
                    next_step_required=False,
                    findings="Test findings"
                )

                # This should NOT raise a ModelContext error - the method should set up context itself
                result = await tool._call_expert_analysis(
                    initial_issue="Test issue",
                    investigation_summary="Test summary",
                    relevant_files=[],  # Empty to avoid file operations
                    relevant_methods=["test_method"],
                    final_hypothesis="Test hypothesis",
                    error_context=None,
                    images=[],
                    model_info=None,  # No pre-resolved model info
                    arguments=mock_arguments,  # Provide arguments for model resolution
                    request=mock_request,  # Provide request for model resolution
                )

                # Should complete without ModelContext error
                assert "error" not in result
                assert result["status"] == "analysis_complete"

                # Verify the model context was actually set up
                assert hasattr(tool, "_model_context")
                assert hasattr(tool, "_current_model_name")
                # Should use DEFAULT_MODEL when no model specified
                from config import DEFAULT_MODEL
                assert tool._current_model_name == DEFAULT_MODEL

            finally:
                # Restore original method
                tool.get_model_provider = original_get_provider

        except RuntimeError as e:
            if "ModelContext not initialized" in str(e):
                pytest.fail("ModelContext error still occurs - the fix is not working properly")
            else:
                raise  # Re-raise other RuntimeErrors
