"""
Test that conversation history is correctly mapped to tool-specific fields
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from providers.base import ProviderType
from server import reconstruct_thread_context
from utils.conversation_memory import ConversationTurn, ThreadContext


@pytest.mark.asyncio
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
        # Create mock conversation context
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
                with patch("utils.conversation_memory.build_conversation_history") as mock_build:
                    # Mock provider registry to avoid model lookup errors
                    with patch("providers.registry.ModelProviderRegistry.get_provider_for_model") as mock_get_provider:
                        from providers.base import ModelCapabilities

                        mock_provider = MagicMock()
                        mock_provider.get_capabilities.return_value = ModelCapabilities(
                            provider=ProviderType.GOOGLE,
                            model_name="gemini-2.5-flash",
                            friendly_name="Gemini",
                            context_window=200000,
                            supports_extended_thinking=True,
                        )
                        mock_get_provider.return_value = mock_provider
                        # Mock conversation history building
                        mock_build.return_value = (
                            "=== CONVERSATION HISTORY ===\nPrevious conversation content\n=== END HISTORY ===",
                            1000,  # mock token count
                        )

                        # Create arguments with continuation_id
                        arguments = {
                            "continuation_id": "test-thread-123",
                            "prompt": test_case["original_value"],
                            "files": ["/test/file2.py"],
                        }

                        # Call reconstruct_thread_context
                        enhanced_args = await reconstruct_thread_context(arguments)

                        # Verify the enhanced prompt is in the prompt field
                        assert "prompt" in enhanced_args
                        enhanced_value = enhanced_args["prompt"]

                        # Should contain conversation history
                        assert "=== CONVERSATION HISTORY ===" in enhanced_value
                        assert "Previous conversation content" in enhanced_value

                        # Should contain the new user input
                        assert "=== NEW USER INPUT ===" in enhanced_value
                        assert test_case["original_value"] in enhanced_value

                        # Should have token budget
                        assert "_remaining_tokens" in enhanced_args
                        assert enhanced_args["_remaining_tokens"] > 0


@pytest.mark.asyncio
async def test_unknown_tool_defaults_to_prompt():
    """Test that unknown tools default to using 'prompt' field"""

    mock_context = ThreadContext(
        thread_id="test-thread-456",
        tool_name="unknown_tool",
        created_at=datetime.now().isoformat(),
        last_updated_at=datetime.now().isoformat(),
        turns=[],
        initial_context={},
    )

    with patch("utils.conversation_memory.get_thread", return_value=mock_context):
        with patch("utils.conversation_memory.add_turn", return_value=True):
            with patch("utils.conversation_memory.build_conversation_history", return_value=("History", 500)):
                # Mock ModelContext to avoid calculation errors
                with patch("utils.model_context.ModelContext") as mock_model_context_class:
                    mock_model_context = MagicMock()
                    mock_model_context.model_name = "gemini-2.5-flash"
                    mock_model_context.calculate_token_allocation.return_value = MagicMock(
                        total_tokens=200000,
                        content_tokens=120000,
                        response_tokens=80000,
                        file_tokens=48000,
                        history_tokens=48000,
                        available_for_prompt=24000,
                    )
                    mock_model_context_class.from_arguments.return_value = mock_model_context

                    arguments = {
                        "continuation_id": "test-thread-456",
                        "prompt": "User input",
                    }

                    enhanced_args = await reconstruct_thread_context(arguments)

                    # Should default to 'prompt' field
                    assert "prompt" in enhanced_args
                    assert "History" in enhanced_args["prompt"]


@pytest.mark.asyncio
async def test_tool_parameter_standardization():
    """Test that most tools use standardized 'prompt' parameter (debug uses investigation pattern)"""
    from tools.analyze import AnalyzeRequest
    from tools.codereview import CodeReviewRequest
    from tools.debug import DebugInvestigationRequest
    from tools.precommit import PrecommitRequest
    from tools.thinkdeep import ThinkDeepRequest

    # Test analyze tool uses prompt
    analyze = AnalyzeRequest(files=["/test.py"], prompt="What does this do?")
    assert analyze.prompt == "What does this do?"

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

    # Test codereview tool uses prompt
    review = CodeReviewRequest(files=["/test.py"], prompt="Review this")
    assert review.prompt == "Review this"

    # Test thinkdeep tool uses prompt
    think = ThinkDeepRequest(prompt="My analysis")
    assert think.prompt == "My analysis"

    # Test precommit tool uses prompt (optional)
    precommit = PrecommitRequest(path="/repo", prompt="Fix bug")
    assert precommit.prompt == "Fix bug"
