"""
Test that conversation history is correctly mapped to tool-specific fields
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from server import reconstruct_thread_context
from utils.conversation_memory import ConversationTurn, ThreadContext


@pytest.mark.asyncio
@pytest.mark.no_mock_provider
async def test_conversation_history_field_mapping():
    """Test that enhanced prompts are mapped to prompt field for all tools"""

    # Test data for different tools - all use 'prompt' now
    test_cases = [
        {
            "tool_name": "analyze",
            "original_value": "What does this code do?",
        },
        {
            "tool_name": "chat",
            "original_value": "Explain this concept",
        },
        {
            "tool_name": "debug",
            "original_value": "Getting undefined error",
        },
        {
            "tool_name": "codereview",
            "original_value": "Review this implementation",
        },
        {
            "tool_name": "thinkdeep",
            "original_value": "My analysis so far",
        },
    ]

    for test_case in test_cases:
        # Create real conversation context
        mock_context = ThreadContext(
            thread_id="test-thread-123",
            tool_name=test_case["tool_name"],
            created_at=datetime.now().isoformat(),
            last_updated_at=datetime.now().isoformat(),
            turns=[
                ConversationTurn(
                    role="user",
                    content="Previous user message",
                    timestamp=datetime.now().isoformat(),
                    files=["/test/file1.py"],
                ),
                ConversationTurn(
                    role="assistant",
                    content="Previous assistant response",
                    timestamp=datetime.now().isoformat(),
                ),
            ],
            initial_context={},
        )

        # Mock get_thread to return our test context
        with patch("utils.conversation_memory.get_thread", return_value=mock_context):
            with patch("utils.conversation_memory.add_turn", return_value=True):
                # Create arguments with continuation_id and use a test model
                arguments = {
                    "continuation_id": "test-thread-123",
                    "prompt": test_case["original_value"],
                    "files": ["/test/file2.py"],
                    "model": "flash",  # Use test model to avoid provider errors
                }

                # Call reconstruct_thread_context
                enhanced_args = await reconstruct_thread_context(arguments)

                # Verify the enhanced prompt is in the prompt field
                assert "prompt" in enhanced_args
                enhanced_value = enhanced_args["prompt"]

                # Should contain conversation history
                assert "=== CONVERSATION HISTORY" in enhanced_value  # Allow for both formats
                assert "Previous user message" in enhanced_value
                assert "Previous assistant response" in enhanced_value

                # Should contain the new user input
                assert "=== NEW USER INPUT ===" in enhanced_value
                assert test_case["original_value"] in enhanced_value

                # Should have token budget
                assert "_remaining_tokens" in enhanced_args
                assert enhanced_args["_remaining_tokens"] > 0


@pytest.mark.asyncio
@pytest.mark.no_mock_provider
async def test_unknown_tool_defaults_to_prompt():
    """Test that unknown tools default to using 'prompt' field"""

    mock_context = ThreadContext(
        thread_id="test-thread-456",
        tool_name="unknown_tool",
        created_at=datetime.now().isoformat(),
        last_updated_at=datetime.now().isoformat(),
        turns=[
            ConversationTurn(
                role="user",
                content="First message",
                timestamp=datetime.now().isoformat(),
            ),
            ConversationTurn(
                role="assistant",
                content="First response",
                timestamp=datetime.now().isoformat(),
            ),
        ],
        initial_context={},
    )

    with patch("utils.conversation_memory.get_thread", return_value=mock_context):
        with patch("utils.conversation_memory.add_turn", return_value=True):
            arguments = {
                "continuation_id": "test-thread-456",
                "prompt": "User input",
                "model": "flash",  # Use test model for real integration
            }

            enhanced_args = await reconstruct_thread_context(arguments)

            # Should default to 'prompt' field
            assert "prompt" in enhanced_args
            assert "=== CONVERSATION HISTORY" in enhanced_args["prompt"]  # Allow for both formats
            assert "First message" in enhanced_args["prompt"]
            assert "First response" in enhanced_args["prompt"]
            assert "User input" in enhanced_args["prompt"]


@pytest.mark.asyncio
async def test_tool_parameter_standardization():
    """Test that workflow tools use standardized investigation pattern"""
    from tools.analyze import AnalyzeWorkflowRequest
    from tools.codereview import CodeReviewRequest
    from tools.debug import DebugInvestigationRequest
    from tools.precommit import PrecommitRequest
    from tools.thinkdeep import ThinkDeepWorkflowRequest

    # Test analyze tool uses workflow pattern
    analyze = AnalyzeWorkflowRequest(
        step="What does this do?",
        step_number=1,
        total_steps=1,
        next_step_required=False,
        findings="Initial analysis",
        relevant_files=["/test.py"],
    )
    assert analyze.step == "What does this do?"

    # Debug tool now uses self-investigation pattern with different fields
    debug = DebugInvestigationRequest(
        step="Investigating error",
        step_number=1,
        total_steps=3,
        next_step_required=True,
        findings="Initial error analysis",
    )
    assert debug.step == "Investigating error"
    assert debug.findings == "Initial error analysis"

    # Test codereview tool uses workflow fields
    review = CodeReviewRequest(
        step="Initial code review investigation",
        step_number=1,
        total_steps=2,
        next_step_required=True,
        findings="Initial review findings",
        relevant_files=["/test.py"],
    )
    assert review.step == "Initial code review investigation"
    assert review.findings == "Initial review findings"

    # Test thinkdeep tool uses workflow pattern
    think = ThinkDeepWorkflowRequest(
        step="My analysis", step_number=1, total_steps=1, next_step_required=False, findings="Initial thinking analysis"
    )
    assert think.step == "My analysis"

    # Test precommit tool uses workflow fields
    precommit = PrecommitRequest(
        step="Validating changes for commit",
        step_number=1,
        total_steps=2,
        next_step_required=True,
        findings="Initial validation findings",
        path="/repo",  # path only needed for step 1
    )
    assert precommit.step == "Validating changes for commit"
    assert precommit.findings == "Initial validation findings"
