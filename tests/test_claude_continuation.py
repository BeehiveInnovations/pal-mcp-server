"""
Test suite for Claude continuation opportunities

Tests the system that offers Claude the opportunity to continue conversations
when Gemini doesn't explicitly ask a follow-up question.
"""

import json
from unittest.mock import Mock, patch

import pytest
from pydantic import Field

from tests.mock_helpers import create_mock_provider
from tools.base import BaseTool, ToolRequest
from utils.conversation_memory import MAX_CONVERSATION_TURNS


class ContinuationRequest(ToolRequest):
    """Test request model with prompt field"""

    prompt: str = Field(..., description="The prompt to analyze")
    files: list[str] = Field(default_factory=list, description="Optional files to analyze")


class ClaudeContinuationTool(BaseTool):
    """Test tool for continuation functionality"""

    def get_name(self) -> str:
        return "test_continuation"

    def get_description(self) -> str:
        return "Test tool for Claude continuation"

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "continuation_id": {"type": "string", "required": False},
            },
        }

    def get_system_prompt(self) -> str:
        return "Test system prompt"

    def get_request_model(self):
        return ContinuationRequest

    async def prepare_prompt(self, request) -> str:
        return f"System: {self.get_system_prompt()}\nUser: {request.prompt}"


class TestClaudeContinuationOffers:
    """Test Claude continuation offer functionality"""

    def setup_method(self):
        # Note: Tool creation and schema generation happens here
        # If providers are not registered yet, tool might detect auto mode
        self.tool = ClaudeContinuationTool()
        # Set default model to avoid effective auto mode
        self.tool.default_model = "gemini-2.5-flash-preview-05-20"

    @patch("utils.conversation_memory.get_storage")
    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}, clear=False)
    async def test_new_conversation_offers_continuation(self, mock_storage):
        """Test that new conversations offer Claude continuation opportunity"""
        # Create tool AFTER providers are registered (in conftest.py fixture)
        tool = ClaudeContinuationTool()
        tool.default_model = "gemini-2.5-flash-preview-05-20"

        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Mock the model
        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = Mock(
                content="Analysis complete.",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute tool without continuation_id (new conversation)
            arguments = {"prompt": "Analyze this code"}
            response = await tool.execute(arguments)

            # Parse response
            response_data = json.loads(response[0].text)

            # Should offer continuation for new conversation
            assert response_data["status"] == "continuation_available"
            assert "continuation_offer" in response_data
            assert response_data["continuation_offer"]["remaining_turns"] == MAX_CONVERSATION_TURNS - 1

    @patch("utils.conversation_memory.get_storage")
    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}, clear=False)
    async def test_existing_conversation_still_offers_continuation(self, mock_storage):
        """Test that existing threaded conversations still offer continuation if turns remain"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Mock existing thread context with 2 turns
        from utils.conversation_memory import ConversationTurn, ThreadContext

        thread_context = ThreadContext(
            thread_id="12345678-1234-1234-1234-123456789012",
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="test_continuation",
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="Previous response",
                    timestamp="2023-01-01T00:00:30Z",
                    tool_name="test_continuation",
                ),
                ConversationTurn(
                    role="user",
                    content="Follow up question",
                    timestamp="2023-01-01T00:01:00Z",
                ),
            ],
            initial_context={"prompt": "Initial analysis"},
        )
        mock_client.get.return_value = thread_context.model_dump_json()

        # Mock the model
        with patch.object(self.tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = Mock(
                content="Continued analysis.",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute tool with continuation_id
            arguments = {"prompt": "Continue analysis", "continuation_id": "12345678-1234-1234-1234-123456789012"}
            response = await self.tool.execute(arguments)

            # Parse response
            response_data = json.loads(response[0].text)

            # Should still offer continuation since turns remain
            assert response_data["status"] == "continuation_available"
            assert "continuation_offer" in response_data
            # MAX_CONVERSATION_TURNS - 2 existing - 1 new = remaining
            assert response_data["continuation_offer"]["remaining_turns"] == MAX_CONVERSATION_TURNS - 3

    @patch("utils.conversation_memory.get_storage")
    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}, clear=False)
    async def test_full_response_flow_with_continuation_offer(self, mock_storage):
        """Test complete response flow that creates continuation offer"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Mock the model to return a response without follow-up question
        with patch.object(self.tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = Mock(
                content="Analysis complete. The code looks good.",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute tool with new conversation
            arguments = {"prompt": "Analyze this code", "model": "flash"}
            response = await self.tool.execute(arguments)

            # Parse response
            assert len(response) == 1
            response_data = json.loads(response[0].text)

            assert response_data["status"] == "continuation_available"
            assert response_data["content"] == "Analysis complete. The code looks good."
            assert "continuation_offer" in response_data

            offer = response_data["continuation_offer"]
            assert "continuation_id" in offer
            assert offer["remaining_turns"] == MAX_CONVERSATION_TURNS - 1
            assert "You have" in offer["note"]
            assert "more exchange(s) available" in offer["note"]

    @patch("utils.conversation_memory.get_storage")
    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}, clear=False)
    async def test_continuation_always_offered_with_natural_language(self, mock_storage):
        """Test that continuation is always offered with natural language prompts"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Mock the model to return a response with natural language follow-up
        with patch.object(self.tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            # Include natural language follow-up in the content
            content_with_followup = """Analysis complete. The code looks good.

I'd be happy to examine the error handling patterns in more detail if that would be helpful."""
            mock_provider.generate_content.return_value = Mock(
                content=content_with_followup,
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute tool
            arguments = {"prompt": "Analyze this code"}
            response = await self.tool.execute(arguments)

            # Parse response
            response_data = json.loads(response[0].text)

            # Should always offer continuation
            assert response_data["status"] == "continuation_available"
            assert "continuation_offer" in response_data
            assert response_data["continuation_offer"]["remaining_turns"] == MAX_CONVERSATION_TURNS - 1

    @patch("utils.conversation_memory.get_storage")
    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}, clear=False)
    async def test_threaded_conversation_with_continuation_offer(self, mock_storage):
        """Test that threaded conversations still get continuation offers when turns remain"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Mock existing thread context
        from utils.conversation_memory import ThreadContext

        thread_context = ThreadContext(
            thread_id="12345678-1234-1234-1234-123456789012",
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="test_continuation",
            turns=[],
            initial_context={"prompt": "Previous analysis"},
        )
        mock_client.get.return_value = thread_context.model_dump_json()

        # Mock the model
        with patch.object(self.tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = Mock(
                content="Continued analysis complete.",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute tool with continuation_id
            arguments = {"prompt": "Continue the analysis", "continuation_id": "12345678-1234-1234-1234-123456789012"}
            response = await self.tool.execute(arguments)

            # Parse response
            response_data = json.loads(response[0].text)

            # Should offer continuation since there are remaining turns (MAX - 0 current - 1)
            assert response_data["status"] == "continuation_available"
            assert response_data.get("continuation_offer") is not None
            assert response_data["continuation_offer"]["remaining_turns"] == MAX_CONVERSATION_TURNS - 1

    @patch("utils.conversation_memory.get_storage")
    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}, clear=False)
    async def test_max_turns_reached_no_continuation_offer(self, mock_storage):
        """Test that no continuation is offered when max turns would be exceeded"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Mock existing thread context at max turns
        from utils.conversation_memory import ConversationTurn, ThreadContext

        # Create turns at the limit (MAX_CONVERSATION_TURNS - 1 since we're about to add one)
        turns = [
            ConversationTurn(
                role="assistant" if i % 2 else "user",
                content=f"Turn {i + 1}",
                timestamp="2023-01-01T00:00:00Z",
                tool_name="test_continuation",
            )
            for i in range(MAX_CONVERSATION_TURNS - 1)
        ]

        thread_context = ThreadContext(
            thread_id="12345678-1234-1234-1234-123456789012",
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="test_continuation",
            turns=turns,
            initial_context={"prompt": "Initial"},
        )
        mock_client.get.return_value = thread_context.model_dump_json()

        # Mock the model
        with patch.object(self.tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = Mock(
                content="Final response.",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute tool with continuation_id at max turns
            arguments = {"prompt": "Final question", "continuation_id": "12345678-1234-1234-1234-123456789012"}
            response = await self.tool.execute(arguments)

            # Parse response
            response_data = json.loads(response[0].text)

            # Should NOT offer continuation since we're at max turns
            assert response_data["status"] == "success"
            assert response_data.get("continuation_offer") is None


class TestContinuationIntegration:
    """Integration tests for continuation offers with conversation memory"""

    def setup_method(self):
        self.tool = ClaudeContinuationTool()
        # Set default model to avoid effective auto mode
        self.tool.default_model = "gemini-2.5-flash-preview-05-20"

    @patch("utils.conversation_memory.get_storage")
    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}, clear=False)
    async def test_continuation_offer_creates_proper_thread(self, mock_storage):
        """Test that continuation offers create properly formatted threads"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Mock the get call that add_turn makes to retrieve the existing thread
        # We'll set this up after the first setex call
        def side_effect_get(key):
            # Return the context from the first setex call
            if mock_client.setex.call_count > 0:
                first_call_data = mock_client.setex.call_args_list[0][0][2]
                return first_call_data
            return None

        mock_client.get.side_effect = side_effect_get

        # Mock the model
        with patch.object(self.tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = Mock(
                content="Analysis result",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute tool for initial analysis
            arguments = {"prompt": "Initial analysis", "files": ["/test/file.py"]}
            response = await self.tool.execute(arguments)

            # Parse response
            response_data = json.loads(response[0].text)

            # Should offer continuation
            assert response_data["status"] == "continuation_available"
            assert "continuation_offer" in response_data

            # Verify thread creation was called (should be called twice: create_thread + add_turn)
            assert mock_client.setex.call_count == 2

            # Check the first call (create_thread)
            first_call = mock_client.setex.call_args_list[0]
            thread_key = first_call[0][0]
            assert thread_key.startswith("thread:")
            assert len(thread_key.split(":")[-1]) == 36  # UUID length

            # Check the second call (add_turn) which should have the assistant response
            second_call = mock_client.setex.call_args_list[1]
            thread_data = second_call[0][2]
            thread_context = json.loads(thread_data)

            assert thread_context["tool_name"] == "test_continuation"
            assert len(thread_context["turns"]) == 1  # Assistant's response added
            assert thread_context["turns"][0]["role"] == "assistant"
            assert thread_context["turns"][0]["content"] == "Analysis result"
            assert thread_context["turns"][0]["files"] == ["/test/file.py"]  # Files from request
            assert thread_context["initial_context"]["prompt"] == "Initial analysis"
            assert thread_context["initial_context"]["files"] == ["/test/file.py"]

    @patch("utils.conversation_memory.get_storage")
    @patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}, clear=False)
    async def test_claude_can_use_continuation_id(self, mock_storage):
        """Test that Claude can use the provided continuation_id in subsequent calls"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Step 1: Initial request creates continuation offer
        with patch.object(self.tool, "get_model_provider") as mock_get_provider:
            mock_provider = create_mock_provider()
            mock_provider.get_provider_type.return_value = Mock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = Mock(
                content="Structure analysis done.",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # Execute initial request
            arguments = {"prompt": "Analyze code structure"}
            response = await self.tool.execute(arguments)

            # Parse response
            response_data = json.loads(response[0].text)
            thread_id = response_data["continuation_offer"]["continuation_id"]

            # Step 2: Mock the thread context for Claude's follow-up
            from utils.conversation_memory import ConversationTurn, ThreadContext

            existing_context = ThreadContext(
                thread_id=thread_id,
                created_at="2023-01-01T00:00:00Z",
                last_updated_at="2023-01-01T00:01:00Z",
                tool_name="test_continuation",
                turns=[
                    ConversationTurn(
                        role="assistant",
                        content="Structure analysis done.",
                        timestamp="2023-01-01T00:00:30Z",
                        tool_name="test_continuation",
                    )
                ],
                initial_context={"prompt": "Analyze code structure"},
            )
            mock_client.get.return_value = existing_context.model_dump_json()

            # Step 3: Claude uses continuation_id
            mock_provider.generate_content.return_value = Mock(
                content="Performance analysis done.",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash-preview-05-20",
                metadata={"finish_reason": "STOP"},
            )

            arguments2 = {"prompt": "Now analyze the performance aspects", "continuation_id": thread_id}
            response2 = await self.tool.execute(arguments2)

            # Parse response
            response_data2 = json.loads(response2[0].text)

            # Should still offer continuation if there are remaining turns
            assert response_data2["status"] == "continuation_available"
            assert "continuation_offer" in response_data2
            # MAX_CONVERSATION_TURNS - 1 existing - 1 new = remaining
            assert response_data2["continuation_offer"]["remaining_turns"] == MAX_CONVERSATION_TURNS - 2


if __name__ == "__main__":
    pytest.main([__file__])
