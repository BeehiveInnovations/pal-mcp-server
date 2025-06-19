"""
Comprehensive test demonstrating debug tool's self-investigation pattern
and continuation ID functionality working together end-to-end.
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


class TestDebugComprehensiveWorkflow:
    """Test the complete debug workflow from investigation to expert analysis to continuation."""

    @pytest.mark.asyncio
    async def test_full_debug_workflow_with_continuation(self):
        """Test complete debug workflow: investigation → expert analysis → continuation to another tool."""
        tool = DebugIssueTool()

        # Step 1: Initial investigation
        with patch("utils.conversation_memory.create_thread", return_value="debug-workflow-uuid"):
            with patch("utils.conversation_memory.add_turn") as mock_add_turn:
                result1 = await tool.execute(
                    {
                        "step": "Investigating memory leak in user session handler",
                        "step_number": 1,
                        "total_steps": 3,
                        "next_step_required": True,
                        "findings": "High memory usage detected in session handler",
                        "files_checked": ["/api/sessions.py"],
                        "images": ["/screenshots/memory_profile.png"],
                    }
                )

        # Verify step 1 response
        assert len(result1) == 1
        response1 = json.loads(result1[0].text)
        assert response1["status"] == "investigation_in_progress"
        assert response1["step_number"] == 1
        assert response1["continuation_id"] == "debug-workflow-uuid"

        # Verify conversation turn was added
        assert mock_add_turn.called
        call_args = mock_add_turn.call_args
        if call_args:
            # Check if args were passed positionally or as keywords
            args = call_args.args if hasattr(call_args, "args") else call_args[0]
            if args and len(args) >= 3:
                assert args[0] == "debug-workflow-uuid"
                assert args[1] == "assistant"
                assert json.loads(args[2])["status"] == "investigation_in_progress"

        # Step 2: Continue investigation with findings
        with patch("utils.conversation_memory.add_turn") as mock_add_turn:
            result2 = await tool.execute(
                {
                    "step": "Found circular references in session cache preventing garbage collection",
                    "step_number": 2,
                    "total_steps": 3,
                    "next_step_required": True,
                    "findings": "Session objects hold references to themselves through event handlers",
                    "files_checked": ["/api/sessions.py", "/api/cache.py"],
                    "relevant_files": ["/api/sessions.py"],
                    "relevant_methods": ["SessionHandler.__init__", "SessionHandler.add_event_listener"],
                    "hypothesis": "Circular references preventing garbage collection",
                    "confidence": "high",
                    "continuation_id": "debug-workflow-uuid",
                }
            )

        # Verify step 2 response
        response2 = json.loads(result2[0].text)
        assert response2["status"] == "investigation_in_progress"
        assert response2["step_number"] == 2
        assert response2["investigation_status"]["files_checked"] == 2
        assert response2["investigation_status"]["relevant_methods"] == 2
        assert response2["investigation_status"]["current_confidence"] == "high"

        # Step 3: Final investigation with expert analysis
        # Mock the expert analysis response
        mock_expert_response = {
            "status": "analysis_complete",
            "summary": "Memory leak caused by circular references in session event handlers",
            "hypotheses": [
                {
                    "name": "CIRCULAR_REFERENCE_LEAK",
                    "confidence": "High (95%)",
                    "evidence": ["Event handlers hold strong references", "No weak references used"],
                    "root_cause": "SessionHandler stores callbacks that reference the handler itself",
                    "potential_fixes": [
                        {
                            "description": "Use weakref for event handler callbacks",
                            "files_to_modify": ["/api/sessions.py"],
                            "complexity": "Low",
                        }
                    ],
                    "minimal_fix": "Replace self references in callbacks with weakref.ref(self)",
                }
            ],
            "investigation_summary": {
                "pattern": "Classic circular reference memory leak",
                "severity": "High - causes unbounded memory growth",
                "recommended_action": "Implement weakref solution immediately",
            },
        }

        with patch("utils.conversation_memory.add_turn") as mock_add_turn:
            with patch.object(tool, "_call_expert_analysis", return_value=mock_expert_response):
                result3 = await tool.execute(
                    {
                        "step": "Investigation complete - confirmed circular reference memory leak pattern",
                        "step_number": 3,
                        "total_steps": 3,
                        "next_step_required": False,  # Triggers expert analysis
                        "findings": "Circular references between SessionHandler and event callbacks prevent GC",
                        "files_checked": ["/api/sessions.py", "/api/cache.py"],
                        "relevant_files": ["/api/sessions.py"],
                        "relevant_methods": ["SessionHandler.__init__", "SessionHandler.add_event_listener"],
                        "hypothesis": "Circular references in event handler callbacks causing memory leak",
                        "confidence": "high",
                        "continuation_id": "debug-workflow-uuid",
                        "model": "flash",
                    }
                )

        # Verify final response with expert analysis
        response3 = json.loads(result3[0].text)
        assert response3["status"] == "calling_expert_analysis"
        assert response3["investigation_complete"] is True
        assert "expert_analysis" in response3

        expert = response3["expert_analysis"]
        assert expert["status"] == "analysis_complete"
        assert "CIRCULAR_REFERENCE_LEAK" in expert["hypotheses"][0]["name"]
        assert "weakref" in expert["hypotheses"][0]["minimal_fix"]

        # Verify complete investigation summary
        assert "complete_investigation" in response3
        complete = response3["complete_investigation"]
        assert complete["steps_taken"] == 3
        assert "/api/sessions.py" in complete["files_examined"]
        assert "SessionHandler.add_event_listener" in complete["relevant_methods"]

        # Step 4: Test continuation to another tool (e.g., analyze)
        # Create a mock thread context representing the debug conversation
        debug_context = ThreadContext(
            thread_id="debug-workflow-uuid",
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:10:00Z",
            tool_name="debug",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Step 1: Investigating memory leak",
                    timestamp="2025-01-01T00:01:00Z",
                    tool_name="debug",
                    files=["/api/sessions.py"],
                    images=["/screenshots/memory_profile.png"],
                ),
                ConversationTurn(
                    role="assistant",
                    content=json.dumps(response1),
                    timestamp="2025-01-01T00:02:00Z",
                    tool_name="debug",
                ),
                ConversationTurn(
                    role="user",
                    content="Step 2: Found circular references",
                    timestamp="2025-01-01T00:03:00Z",
                    tool_name="debug",
                ),
                ConversationTurn(
                    role="assistant",
                    content=json.dumps(response2),
                    timestamp="2025-01-01T00:04:00Z",
                    tool_name="debug",
                ),
                ConversationTurn(
                    role="user",
                    content="Step 3: Investigation complete",
                    timestamp="2025-01-01T00:05:00Z",
                    tool_name="debug",
                ),
                ConversationTurn(
                    role="assistant",
                    content=json.dumps(response3),
                    timestamp="2025-01-01T00:06:00Z",
                    tool_name="debug",
                ),
            ],
            initial_context={},
        )

        # Test that another tool can use the continuation
        with patch("utils.conversation_memory.get_thread", return_value=debug_context):
            # Mock file reading
            def mock_read_file(file_path):
                if file_path == "/api/sessions.py":
                    return "# SessionHandler with circular refs\nclass SessionHandler:\n    pass", 20
                elif file_path == "/screenshots/memory_profile.png":
                    # Images return empty string for content but 0 tokens
                    return "", 0
                elif file_path == "/api/cache.py":
                    return "# Cache module", 5
                return "", 0

            # Build conversation history for another tool
            from utils.model_context import ModelContext

            model_context = ModelContext("flash")
            history, tokens = build_conversation_history(debug_context, model_context, read_files_func=mock_read_file)

            # Verify history contains all debug information
            assert "=== CONVERSATION HISTORY (CONTINUATION) ===" in history
            assert "Thread: debug-workflow-uuid" in history
            assert "Tool: debug" in history

            # Check investigation progression
            assert "Step 1: Investigating memory leak" in history
            assert "Step 2: Found circular references" in history
            assert "Step 3: Investigation complete" in history

            # Check expert analysis is included
            assert "CIRCULAR_REFERENCE_LEAK" in history
            assert "weakref" in history
            assert "memory leak" in history

            # Check files are referenced in conversation history
            assert "/api/sessions.py" in history

            # File content would be in referenced files section if the files were readable
            # In our test they're not real files so they won't be embedded
            # But the expert analysis content should be there
            assert "Memory leak caused by circular references" in history

            # Verify file list includes all files from investigation
            file_list = get_conversation_file_list(debug_context)
            assert "/api/sessions.py" in file_list

    @pytest.mark.asyncio
    async def test_debug_investigation_state_machine(self):
        """Test the debug tool's investigation state machine behavior."""
        tool = DebugIssueTool()

        # Test state transitions
        states = []

        # Initial state
        with patch("utils.conversation_memory.create_thread", return_value="state-test-uuid"):
            with patch("utils.conversation_memory.add_turn"):
                result = await tool.execute(
                    {
                        "step": "Starting investigation",
                        "step_number": 1,
                        "total_steps": 2,
                        "next_step_required": True,
                        "findings": "Initial findings",
                    }
                )
                states.append(json.loads(result[0].text))

        # Verify initial state
        assert states[0]["status"] == "investigation_in_progress"
        assert states[0]["step_number"] == 1
        assert states[0]["next_step_required"] is True

        # Final state (triggers expert analysis)
        mock_expert_response = {"status": "analysis_complete", "summary": "Test complete"}

        with patch("utils.conversation_memory.add_turn"):
            with patch.object(tool, "_call_expert_analysis", return_value=mock_expert_response):
                result = await tool.execute(
                    {
                        "step": "Final findings",
                        "step_number": 2,
                        "total_steps": 2,
                        "next_step_required": False,
                        "findings": "Complete findings",
                        "continuation_id": "state-test-uuid",
                        "model": "flash",
                    }
                )
                states.append(json.loads(result[0].text))

        # Verify final state
        assert states[1]["status"] == "calling_expert_analysis"
        assert states[1]["investigation_complete"] is True
        assert "expert_analysis" in states[1]

    @pytest.mark.asyncio
    async def test_debug_backtracking_preserves_continuation(self):
        """Test that backtracking preserves continuation ID and investigation state."""
        tool = DebugIssueTool()

        # Start investigation
        with patch("utils.conversation_memory.create_thread", return_value="backtrack-test-uuid"):
            with patch("utils.conversation_memory.add_turn"):
                result1 = await tool.execute(
                    {
                        "step": "Initial hypothesis",
                        "step_number": 1,
                        "total_steps": 3,
                        "next_step_required": True,
                        "findings": "Initial findings",
                    }
                )

        response1 = json.loads(result1[0].text)
        continuation_id = response1["continuation_id"]

        # Step 2 - wrong direction
        with patch("utils.conversation_memory.add_turn"):
            await tool.execute(
                {
                    "step": "Wrong hypothesis",
                    "step_number": 2,
                    "total_steps": 3,
                    "next_step_required": True,
                    "findings": "Dead end",
                    "hypothesis": "Wrong initial hypothesis",
                    "confidence": "low",
                    "continuation_id": continuation_id,
                }
            )

        # Backtrack from step 2
        with patch("utils.conversation_memory.add_turn"):
            result3 = await tool.execute(
                {
                    "step": "Backtracking - new hypothesis",
                    "step_number": 3,
                    "total_steps": 4,  # Adjusted total
                    "next_step_required": True,
                    "findings": "New direction",
                    "hypothesis": "New hypothesis after backtracking",
                    "confidence": "medium",
                    "backtrack_from_step": 2,
                    "continuation_id": continuation_id,
                }
            )

        response3 = json.loads(result3[0].text)

        # Verify continuation preserved through backtracking
        assert response3["continuation_id"] == continuation_id
        assert response3["step_number"] == 3
        assert response3["total_steps"] == 4

        # Verify investigation status after backtracking
        # When we backtrack, investigation continues
        assert response3["investigation_status"]["files_checked"] == 0  # Reset after backtrack
        assert response3["investigation_status"]["current_confidence"] == "medium"

        # The key thing is the continuation ID is preserved
        # and we've adjusted our approach (total_steps increased)
