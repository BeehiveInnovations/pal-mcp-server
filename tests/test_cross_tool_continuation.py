"""
Test suite for cross-tool continuation functionality

Tests that continuation IDs work properly across different tools,
allowing multi-turn conversations to span multiple tool types.
"""

import json
import os
from unittest.mock import Mock, patch

import pytest
from pydantic import Field

from tests.mock_helpers import create_mock_provider
from tools.base import BaseTool, ToolRequest
from utils.conversation_memory import ConversationTurn, ThreadContext


class AnalysisRequest(ToolRequest):
    """Test request for analysis tool"""

    code: str = Field(..., description="Code to analyze")


class ReviewRequest(ToolRequest):
    """Test request for review tool"""

    findings: str = Field(..., description="Analysis findings to review")
    files: list[str] = Field(default_factory=list, description="Optional files to review")


class MockAnalysisTool(BaseTool):
    """Mock analysis tool for cross-tool testing"""

    def get_name(self) -> str:
        return "test_analysis"

    def get_description(self) -> str:
        return "Test analysis tool"

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "continuation_id": {"type": "string", "required": False},
            },
        }

    def get_system_prompt(self) -> str:
        return "Analyze the provided code"

    def get_request_model(self):
        return AnalysisRequest

    async def prepare_prompt(self, request) -> str:
        return f"System: {self.get_system_prompt()}\nCode: {request.code}"


class MockReviewTool(BaseTool):
    """Mock review tool for cross-tool testing"""

    def get_name(self) -> str:
        return "test_review"

    def get_description(self) -> str:
        return "Test review tool"

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "findings": {"type": "string"},
                "continuation_id": {"type": "string", "required": False},
            },
        }

    def get_system_prompt(self) -> str:
        return "Review the analysis findings"

    def get_request_model(self):
        return ReviewRequest

    async def prepare_prompt(self, request) -> str:
        return f"System: {self.get_system_prompt()}\nFindings: {request.findings}"


class TestCrossToolContinuation:
    """Test cross-tool continuation functionality"""

    def setup_method(self):
        self.analysis_tool = MockAnalysisTool()
        self.review_tool = MockReviewTool()

    @patch("utils.conversation_memory.get_storage")
    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}, clear=False)
    async def test_continuation_id_works_across_different_tools(self, mock_storage):
        """Test that a continuation_id from one tool can be used with another tool"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Step 1: Analysis tool creates a conversation with continuation offer
        with patch.object(self.analysis_tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            # Simple content without JSON follow-up
            content = """Found potential security issues in authentication logic.

I'd be happy to review these security findings in detail if that would be helpful."""
            mock_provider.generate_content.return_value = Mock(
                content=content,
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute analysis tool
            arguments = {"code": "function authenticate(user) { return true; }"}
            response = await self.analysis_tool.execute(arguments)
            response_data = json.loads(response[0].text)

            assert response_data["status"] == "continuation_available"
            continuation_id = response_data["continuation_offer"]["continuation_id"]

        # Step 2: Mock the existing thread context for the review tool
        # The thread was created by analysis_tool but will be continued by review_tool
        existing_context = ThreadContext(
            thread_id=continuation_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="test_analysis",  # Original tool
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="Found potential security issues in authentication logic.\n\nI'd be happy to review these security findings in detail if that would be helpful.",
                    timestamp="2023-01-01T00:00:30Z",
                    tool_name="test_analysis",  # Original tool
                )
            ],
            initial_context={"code": "function authenticate(user) { return true; }"},
        )

        # Mock the get call to return existing context for add_turn to work
        def mock_get_side_effect(key):
            if key.startswith("thread:"):
                return existing_context.model_dump_json()
            return None

        mock_client.get.side_effect = mock_get_side_effect

        # Step 3: Review tool uses the same continuation_id
        with patch.object(self.review_tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = Mock(
                content="Critical security vulnerability confirmed. The authentication function always returns true, bypassing all security checks.",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute review tool with the continuation_id from analysis tool
            arguments = {
                "findings": "Authentication bypass vulnerability detected",
                "continuation_id": continuation_id,
            }
            response = await self.review_tool.execute(arguments)
            response_data = json.loads(response[0].text)

            # Should offer continuation since there are remaining turns available
            assert response_data["status"] == "continuation_available"
            assert "Critical security vulnerability confirmed" in response_data["content"]

        # Step 4: Verify the cross-tool continuation worked
        # Should have at least 2 setex calls: 1 from analysis tool follow-up, 1 from review tool add_turn
        setex_calls = mock_client.setex.call_args_list
        assert len(setex_calls) >= 2  # Analysis tool creates thread + review tool adds turn

        # Get the final thread state from the last setex call
        final_thread_data = setex_calls[-1][0][2]  # Last setex call's data
        final_context = json.loads(final_thread_data)

        assert final_context["thread_id"] == continuation_id
        assert final_context["tool_name"] == "test_analysis"  # Original tool name preserved
        assert len(final_context["turns"]) == 2  # Original + new turn

        # Verify the new turn has the review tool's name
        second_turn = final_context["turns"][1]
        assert second_turn["role"] == "assistant"
        assert second_turn["tool_name"] == "test_review"  # New tool name
        assert "Critical security vulnerability confirmed" in second_turn["content"]

    @patch("utils.conversation_memory.get_storage")
    def test_cross_tool_conversation_history_includes_tool_names(self, mock_storage):
        """Test that conversation history properly shows which tool was used for each turn"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Create a thread context with turns from different tools
        thread_context = ThreadContext(
            thread_id="12345678-1234-1234-1234-123456789012",
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:03:00Z",
            tool_name="test_analysis",  # Original tool
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="Analysis complete: Found 3 issues",
                    timestamp="2023-01-01T00:01:00Z",
                    tool_name="test_analysis",
                ),
                ConversationTurn(
                    role="assistant",
                    content="Review complete: 2 critical, 1 minor issue",
                    timestamp="2023-01-01T00:02:00Z",
                    tool_name="test_review",
                ),
                ConversationTurn(
                    role="assistant",
                    content="Deep analysis: Root cause identified",
                    timestamp="2023-01-01T00:03:00Z",
                    tool_name="test_thinkdeep",
                ),
            ],
            initial_context={"code": "test code"},
        )

        # Build conversation history
        from providers.registry import ModelProviderRegistry
        from utils.conversation_memory import build_conversation_history

        # Set up provider for this test
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "OPENAI_API_KEY": ""}, clear=False):
            ModelProviderRegistry.clear_cache()
            history, tokens = build_conversation_history(thread_context, model_context=None)

        # Verify tool names are included in the history
        assert "Turn 1 (Gemini using test_analysis)" in history
        assert "Turn 2 (Gemini using test_review)" in history
        assert "Turn 3 (Gemini using test_thinkdeep)" in history
        assert "Analysis complete: Found 3 issues" in history
        assert "Review complete: 2 critical, 1 minor issue" in history
        assert "Deep analysis: Root cause identified" in history

    @patch("utils.conversation_memory.get_storage")
    @patch("utils.conversation_memory.get_thread")
    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}, clear=False)
    async def test_cross_tool_conversation_with_files_context(self, mock_get_thread, mock_storage):
        """Test that file context is preserved across tool switches"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Create existing context with files from analysis tool
        existing_context = ThreadContext(
            thread_id="test-thread-id",
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="test_analysis",
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="Analysis of auth.py complete",
                    timestamp="2023-01-01T00:01:00Z",
                    tool_name="test_analysis",
                    files=["/src/auth.py", "/src/utils.py"],
                )
            ],
            initial_context={"code": "authentication code", "files": ["/src/auth.py"]},
        )

        # Mock get_thread to return the existing context
        mock_get_thread.return_value = existing_context

        # Mock review tool response
        with patch.object(self.review_tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = Mock(
                content="Security review of auth.py shows vulnerabilities",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute review tool with additional files
            arguments = {
                "findings": "Auth vulnerabilities found",
                "continuation_id": "test-thread-id",
                "files": ["/src/security.py"],  # Additional file for review
            }
            response = await self.review_tool.execute(arguments)
            response_data = json.loads(response[0].text)

            assert response_data["status"] == "continuation_available"

        # Verify files from both tools are tracked in Redis calls
        setex_calls = mock_client.setex.call_args_list
        assert len(setex_calls) >= 1  # At least the add_turn call from review tool

        # Get the final thread state
        final_thread_data = setex_calls[-1][0][2]
        final_context = json.loads(final_thread_data)

        # Check that the new turn includes the review tool's files
        review_turn = final_context["turns"][1]  # Second turn (review tool)
        assert review_turn["tool_name"] == "test_review"
        assert review_turn["files"] == ["/src/security.py"]

        # Original turn's files should still be there
        analysis_turn = final_context["turns"][0]  # First turn (analysis tool)
        assert analysis_turn["files"] == ["/src/auth.py", "/src/utils.py"]

    @patch("utils.conversation_memory.get_storage")
    @patch("utils.conversation_memory.get_thread")
    def test_thread_preserves_original_tool_name(self, mock_get_thread, mock_storage):
        """Test that the thread's original tool_name is preserved even when other tools contribute"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Create existing thread from analysis tool
        existing_context = ThreadContext(
            thread_id="test-thread-id",
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="test_analysis",  # Original tool
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="Initial analysis",
                    timestamp="2023-01-01T00:01:00Z",
                    tool_name="test_analysis",
                )
            ],
            initial_context={"code": "test"},
        )

        # Mock get_thread to return the existing context
        mock_get_thread.return_value = existing_context

        # Add turn from review tool
        from utils.conversation_memory import add_turn

        success = add_turn(
            "test-thread-id",
            "assistant",
            "Review completed",
            tool_name="test_review",  # Different tool
        )

        # Verify the add_turn succeeded (basic cross-tool functionality test)
        assert success

        # Verify thread's original tool_name is preserved
        setex_calls = mock_client.setex.call_args_list
        updated_thread_data = setex_calls[-1][0][2]
        updated_context = json.loads(updated_thread_data)

        assert updated_context["tool_name"] == "test_analysis"  # Original preserved
        assert len(updated_context["turns"]) == 2
        assert updated_context["turns"][0]["tool_name"] == "test_analysis"
        assert updated_context["turns"][1]["tool_name"] == "test_review"


if __name__ == "__main__":
    pytest.main([__file__])
