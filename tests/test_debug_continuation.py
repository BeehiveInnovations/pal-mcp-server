"""
Test debug tool continuation ID functionality and conversation history formatting.
"""

import json
from unittest.mock import patch

import pytest

from tools.debug import DebugIssueTool
from utils.conversation_memory import (
    ConversationTurn,
    ThreadContext,
    build_conversation_history,
    get_conversation_file_list,
)


class TestDebugContinuation:
    """Test debug tool continuation ID and conversation history integration."""

    @pytest.mark.asyncio
    async def test_debug_creates_continuation_id(self):
        """Test that debug tool creates continuation ID on first step."""
        tool = DebugIssueTool()

        with patch("utils.conversation_memory.create_thread", return_value="debug-test-uuid-123"):
            with patch("utils.conversation_memory.add_turn"):
                result = await tool.execute(
                    {
                        "step": "Investigating null pointer exception",
                        "step_number": 1,
                        "total_steps": 3,
                        "next_step_required": True,
                        "findings": "Initial investigation shows null reference in UserService",
                        "files_checked": ["/api/UserService.java"],
                    }
                )

        assert len(result) == 1
        response = json.loads(result[0].text)
        assert response["status"] == "investigation_in_progress"
        assert response["continuation_id"] == "debug-test-uuid-123"

    def test_debug_conversation_formatting(self):
        """Test that debug tool's structured output is properly formatted in conversation history."""
        # Create a mock conversation with debug tool output
        debug_output = {
            "status": "investigation_in_progress",
            "step_number": 2,
            "total_steps": 3,
            "next_step_required": True,
            "investigation_status": {
                "files_checked": 3,
                "relevant_files": 2,
                "relevant_methods": 1,
                "hypotheses_formed": 1,
                "images_collected": 0,
                "current_confidence": "medium",
            },
            "output": {"instructions": "Continue systematic investigation.", "format": "systematic_investigation"},
            "continuation_id": "debug-test-uuid-123",
            "next_steps": "Continue investigation with step 3.",
        }

        context = ThreadContext(
            thread_id="debug-test-uuid-123",
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:05:00Z",
            tool_name="debug",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Step 1: Investigating null pointer exception",
                    timestamp="2025-01-01T00:01:00Z",
                    tool_name="debug",
                    files=["/api/UserService.java"],
                ),
                ConversationTurn(
                    role="assistant",
                    content=json.dumps(debug_output, indent=2),
                    timestamp="2025-01-01T00:02:00Z",
                    tool_name="debug",
                    files=["/api/UserService.java", "/api/UserController.java"],
                ),
            ],
            initial_context={
                "step": "Investigating null pointer exception",
                "step_number": 1,
                "total_steps": 3,
                "next_step_required": True,
                "findings": "Initial investigation",
            },
        )

        # Mock file reading to avoid actual file I/O
        def mock_read_file(file_path):
            if file_path == "/api/UserService.java":
                return "// UserService.java\npublic class UserService {\n    // code...\n}", 10
            elif file_path == "/api/UserController.java":
                return "// UserController.java\npublic class UserController {\n    // code...\n}", 10
            return "", 0

        # Build conversation history
        from utils.model_context import ModelContext

        model_context = ModelContext("flash")
        history, tokens = build_conversation_history(context, model_context, read_files_func=mock_read_file)

        # Verify the history contains debug-specific content
        assert "=== CONVERSATION HISTORY (CONTINUATION) ===" in history
        assert "Thread: debug-test-uuid-123" in history
        assert "Tool: debug" in history

        # Check that files are included
        assert "UserService.java" in history
        assert "UserController.java" in history

        # Check that debug output is included
        assert "investigation_in_progress" in history
        assert '"step_number": 2' in history
        assert '"files_checked": 3' in history
        assert '"current_confidence": "medium"' in history

    def test_debug_continuation_preserves_investigation_state(self):
        """Test that continuation preserves investigation state across tools."""
        # Create a debug investigation context
        context = ThreadContext(
            thread_id="debug-test-uuid-123",
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:10:00Z",
            tool_name="debug",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Step 1: Initial investigation",
                    timestamp="2025-01-01T00:01:00Z",
                    tool_name="debug",
                    files=["/api/SessionManager.java"],
                ),
                ConversationTurn(
                    role="assistant",
                    content=json.dumps(
                        {
                            "status": "investigation_in_progress",
                            "step_number": 1,
                            "total_steps": 4,
                            "next_step_required": True,
                            "investigation_status": {"files_checked": 1, "relevant_files": 1},
                            "continuation_id": "debug-test-uuid-123",
                        }
                    ),
                    timestamp="2025-01-01T00:02:00Z",
                    tool_name="debug",
                ),
                ConversationTurn(
                    role="user",
                    content="Step 2: Found dictionary modification issue",
                    timestamp="2025-01-01T00:03:00Z",
                    tool_name="debug",
                    files=["/api/SessionManager.java", "/api/utils.py"],
                ),
                ConversationTurn(
                    role="assistant",
                    content=json.dumps(
                        {
                            "status": "investigation_in_progress",
                            "step_number": 2,
                            "total_steps": 4,
                            "next_step_required": True,
                            "investigation_status": {
                                "files_checked": 2,
                                "relevant_files": 1,
                                "relevant_methods": 1,
                                "hypotheses_formed": 1,
                                "current_confidence": "high",
                            },
                            "continuation_id": "debug-test-uuid-123",
                        }
                    ),
                    timestamp="2025-01-01T00:04:00Z",
                    tool_name="debug",
                ),
            ],
            initial_context={},
        )

        # Get file list to verify prioritization
        file_list = get_conversation_file_list(context)
        assert file_list == ["/api/SessionManager.java", "/api/utils.py"]

        # Mock file reading
        def mock_read_file(file_path):
            return f"// {file_path}\n// Mock content", 5

        # Build history
        from utils.model_context import ModelContext

        model_context = ModelContext("flash")
        history, tokens = build_conversation_history(context, model_context, read_files_func=mock_read_file)

        # Verify investigation progression is preserved
        assert "Step 1: Initial investigation" in history
        assert "Step 2: Found dictionary modification issue" in history
        assert '"step_number": 1' in history
        assert '"step_number": 2' in history
        assert '"current_confidence": "high"' in history

    @pytest.mark.asyncio
    async def test_debug_to_analyze_continuation(self):
        """Test continuation from debug tool to analyze tool."""
        # Simulate debug tool creating initial investigation
        debug_context = ThreadContext(
            thread_id="debug-analyze-uuid-123",
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:10:00Z",
            tool_name="debug",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Final investigation step",
                    timestamp="2025-01-01T00:01:00Z",
                    tool_name="debug",
                    files=["/api/SessionManager.java"],
                ),
                ConversationTurn(
                    role="assistant",
                    content=json.dumps(
                        {
                            "status": "calling_expert_analysis",
                            "investigation_complete": True,
                            "expert_analysis": {
                                "status": "analysis_complete",
                                "summary": "Dictionary modification during iteration bug",
                                "hypotheses": [
                                    {
                                        "name": "CONCURRENT_MODIFICATION",
                                        "confidence": "High",
                                        "root_cause": "Modifying dict while iterating",
                                        "minimal_fix": "Create list of keys first",
                                    }
                                ],
                            },
                            "complete_investigation": {
                                "initial_issue": "Session validation failures",
                                "steps_taken": 3,
                                "files_examined": ["/api/SessionManager.java"],
                                "relevant_methods": ["SessionManager.cleanup_expired_sessions"],
                            },
                        }
                    ),
                    timestamp="2025-01-01T00:02:00Z",
                    tool_name="debug",
                ),
            ],
            initial_context={},
        )

        # Mock getting the thread
        with patch("utils.conversation_memory.get_thread", return_value=debug_context):
            # Mock file reading
            def mock_read_file(file_path):
                return "// SessionManager.java\n// cleanup_expired_sessions method", 10

            # Build history for analyze tool
            from utils.model_context import ModelContext

            model_context = ModelContext("flash")
            history, tokens = build_conversation_history(debug_context, model_context, read_files_func=mock_read_file)

            # Verify analyze tool can see debug investigation
            assert "calling_expert_analysis" in history
            assert "CONCURRENT_MODIFICATION" in history
            assert "Dictionary modification during iteration bug" in history
            assert "SessionManager.cleanup_expired_sessions" in history

            # Verify the continuation context is clear
            assert "Thread: debug-analyze-uuid-123" in history
            assert "Tool: debug" in history  # Shows original tool

    def test_debug_planner_style_formatting(self):
        """Test that debug tool uses similar formatting to planner for structured responses."""
        # Create debug investigation with multiple steps
        context = ThreadContext(
            thread_id="debug-format-uuid-123",
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:15:00Z",
            tool_name="debug",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Step 1: Initial error analysis",
                    timestamp="2025-01-01T00:01:00Z",
                    tool_name="debug",
                ),
                ConversationTurn(
                    role="assistant",
                    content=json.dumps(
                        {
                            "status": "investigation_in_progress",
                            "step_number": 1,
                            "total_steps": 3,
                            "next_step_required": True,
                            "output": {
                                "instructions": "Continue systematic investigation.",
                                "format": "systematic_investigation",
                            },
                            "continuation_id": "debug-format-uuid-123",
                        },
                        indent=2,
                    ),
                    timestamp="2025-01-01T00:02:00Z",
                    tool_name="debug",
                ),
            ],
            initial_context={},
        )

        # Build history
        from utils.model_context import ModelContext

        model_context = ModelContext("flash")
        history, _ = build_conversation_history(context, model_context, read_files_func=lambda x: ("", 0))

        # Verify structured format is preserved
        assert '"status": "investigation_in_progress"' in history
        assert '"format": "systematic_investigation"' in history
        assert "--- Turn 1 (Claude using debug) ---" in history
        assert "--- Turn 2 (Gemini using debug" in history

        # The JSON structure should be preserved for tools to parse
        # This allows other tools to understand the investigation state
        turn_2_start = history.find("--- Turn 2 (Gemini using debug")
        turn_2_content = history[turn_2_start:]
        assert "{\n" in turn_2_content  # JSON formatting preserved
        assert '"continuation_id"' in turn_2_content
