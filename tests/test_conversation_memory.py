"""
Test suite for conversation memory system

Tests the Redis-based conversation persistence needed for AI-to-AI multi-turn
discussions in stateless MCP environments.
"""

import os
from unittest.mock import Mock, patch

import pytest

from server import get_follow_up_instructions
from utils.conversation_memory import (
    CONVERSATION_TIMEOUT_SECONDS,
    MAX_CONVERSATION_TURNS,
    ConversationTurn,
    ThreadContext,
    add_turn,
    build_conversation_history,
    create_thread,
    get_thread,
)


class TestConversationMemory:
    """Test the conversation memory system for stateless MCP requests"""

    @patch("utils.conversation_memory.get_storage")
    def test_create_thread(self, mock_storage):
        """Test creating a new thread"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        thread_id = create_thread("chat", {"prompt": "Hello", "files": ["/test.py"]})

        assert thread_id is not None
        assert len(thread_id) == 36  # UUID4 length

        # Verify Redis was called
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args
        assert call_args[0][0] == f"thread:{thread_id}"  # key
        assert call_args[0][1] == CONVERSATION_TIMEOUT_SECONDS  # TTL from configuration

    @patch("utils.conversation_memory.get_storage")
    def test_get_thread_valid(self, mock_storage):
        """Test retrieving an existing thread"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        test_uuid = "12345678-1234-1234-1234-123456789012"

        # Create valid ThreadContext and serialize it
        context_obj = ThreadContext(
            thread_id=test_uuid,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="chat",
            turns=[],
            initial_context={"prompt": "test"},
        )
        mock_client.get.return_value = context_obj.model_dump_json()

        context = get_thread(test_uuid)

        assert context is not None
        assert context.thread_id == test_uuid
        assert context.tool_name == "chat"
        mock_client.get.assert_called_once_with(f"thread:{test_uuid}")

    @patch("utils.conversation_memory.get_storage")
    def test_get_thread_invalid_uuid(self, mock_storage):
        """Test handling invalid UUID"""
        context = get_thread("invalid-uuid")
        assert context is None

    @patch("utils.conversation_memory.get_storage")
    def test_get_thread_not_found(self, mock_storage):
        """Test handling thread not found"""
        mock_client = Mock()
        mock_storage.return_value = mock_client
        mock_client.get.return_value = None

        context = get_thread("12345678-1234-1234-1234-123456789012")
        assert context is None

    @patch("utils.conversation_memory.get_storage")
    def test_add_turn_success(self, mock_storage):
        """Test adding a turn to existing thread"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        test_uuid = "12345678-1234-1234-1234-123456789012"

        # Create valid ThreadContext
        context_obj = ThreadContext(
            thread_id=test_uuid,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="chat",
            turns=[],
            initial_context={"prompt": "test"},
        )
        mock_client.get.return_value = context_obj.model_dump_json()

        success = add_turn(test_uuid, "user", "Hello there")

        assert success is True
        # Verify Redis get and setex were called
        mock_client.get.assert_called_once()
        mock_client.setex.assert_called_once()

    @patch("utils.conversation_memory.get_storage")
    def test_add_turn_max_limit(self, mock_storage):
        """Test turn limit enforcement"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        test_uuid = "12345678-1234-1234-1234-123456789012"

        # Create thread with MAX_CONVERSATION_TURNS turns (at limit)
        turns = [
            ConversationTurn(role="user", content=f"Turn {i}", timestamp="2023-01-01T00:00:00Z")
            for i in range(MAX_CONVERSATION_TURNS)
        ]
        context_obj = ThreadContext(
            thread_id=test_uuid,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="chat",
            turns=turns,
            initial_context={"prompt": "test"},
        )
        mock_client.get.return_value = context_obj.model_dump_json()

        success = add_turn(test_uuid, "user", "This should fail")

        assert success is False

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "OPENAI_API_KEY": ""}, clear=False)
    def test_build_conversation_history(self, project_path):
        """Test building conversation history format with files and speaker identification"""
        from providers.registry import ModelProviderRegistry

        ModelProviderRegistry.clear_cache()

        # Create real test files to test actual file embedding functionality
        main_file = project_path / "main.py"
        readme_file = project_path / "docs" / "readme.md"
        examples_dir = project_path / "examples"
        examples_file = examples_dir / "example.py"

        # Create directories and files
        readme_file.parent.mkdir(parents=True, exist_ok=True)
        examples_dir.mkdir(parents=True, exist_ok=True)

        main_file.write_text("def main():\n    print('Hello world')\n")
        readme_file.write_text("# Project Documentation\nThis is a test project.\n")
        examples_file.write_text("# Example code\nprint('Example')\n")

        test_uuid = "12345678-1234-1234-1234-123456789012"

        turns = [
            ConversationTurn(
                role="user",
                content="What is Python?",
                timestamp="2023-01-01T00:00:00Z",
                files=[str(main_file), str(readme_file)],
            ),
            ConversationTurn(
                role="assistant",
                content="Python is a programming language",
                timestamp="2023-01-01T00:01:00Z",
                files=[str(examples_dir)],  # Directory will be expanded to files
                tool_name="chat",
            ),
        ]

        context = ThreadContext(
            thread_id=test_uuid,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="chat",
            turns=turns,
            initial_context={},
        )

        history, tokens = build_conversation_history(context, model_context=None)

        # Test basic structure
        assert "CONVERSATION HISTORY" in history
        assert f"Thread: {test_uuid}" in history
        assert "Tool: chat" in history
        assert f"Turn 2/{MAX_CONVERSATION_TURNS}" in history

        # Test speaker identification
        assert "--- Turn 1 (Claude) ---" in history
        assert "--- Turn 2 (Gemini using chat) ---" in history

        # Test content
        assert "What is Python?" in history
        assert "Python is a programming language" in history

        # Test file tracking
        # Check that the new file embedding section is included
        assert "=== FILES REFERENCED IN THIS CONVERSATION ===" in history
        assert "The following files have been shared and analyzed during our conversation." in history

        # Check that file context from previous turns is included (now shows files used per turn)
        assert f"Files used in this turn: {main_file}, {readme_file}" in history
        assert f"Files used in this turn: {examples_dir}" in history

        # Verify actual file content is embedded
        assert "def main():" in history
        assert "Hello world" in history
        assert "Project Documentation" in history

    def test_build_conversation_history_empty(self):
        """Test building history with no turns"""
        test_uuid = "12345678-1234-1234-1234-123456789012"

        context = ThreadContext(
            thread_id=test_uuid,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:00:00Z",
            tool_name="chat",
            turns=[],
            initial_context={},
        )

        history, tokens = build_conversation_history(context, model_context=None)
        assert history == ""
        assert tokens == 0


class TestConversationFlow:
    """Test complete conversation flows simulating stateless MCP requests"""

    @patch("utils.conversation_memory.get_storage")
    def test_complete_conversation_cycle(self, mock_storage):
        """Test a complete 5-turn conversation until limit reached"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Simulate independent MCP request cycles

        # REQUEST 1: Initial request creates thread
        thread_id = create_thread("chat", {"prompt": "Analyze this code"})
        initial_context = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:00:00Z",
            tool_name="chat",
            turns=[],
            initial_context={"prompt": "Analyze this code"},
        )
        mock_client.get.return_value = initial_context.model_dump_json()

        # Add assistant response
        success = add_turn(
            thread_id,
            "assistant",
            "Code analysis complete",
        )
        assert success is True

        # REQUEST 2: User responds to follow-up (independent request cycle)
        # Simulate retrieving updated context from Redis
        context_after_1 = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="chat",
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="Code analysis complete",
                    timestamp="2023-01-01T00:00:30Z",
                )
            ],
            initial_context={"prompt": "Analyze this code"},
        )
        mock_client.get.return_value = context_after_1.model_dump_json()

        success = add_turn(thread_id, "user", "Yes, check error handling")
        assert success is True

        success = add_turn(thread_id, "assistant", "Error handling reviewed")
        assert success is True

        # REQUEST 3-5: Continue conversation (simulating independent cycles)
        # After turn 3
        context_after_3 = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:03:00Z",
            tool_name="chat",
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="Code analysis complete",
                    timestamp="2023-01-01T00:00:30Z",
                ),
                ConversationTurn(role="user", content="Yes, check error handling", timestamp="2023-01-01T00:01:30Z"),
                ConversationTurn(
                    role="assistant",
                    content="Error handling reviewed",
                    timestamp="2023-01-01T00:02:30Z",
                ),
            ],
            initial_context={"prompt": "Analyze this code"},
        )
        mock_client.get.return_value = context_after_3.model_dump_json()

        success = add_turn(thread_id, "user", "Yes, check tests")
        assert success is True

        success = add_turn(thread_id, "assistant", "Test coverage analyzed")
        assert success is True

        # REQUEST 6: Try to exceed MAX_CONVERSATION_TURNS limit - should fail
        turns_at_limit = [
            ConversationTurn(
                role="assistant" if i % 2 == 0 else "user", content=f"Turn {i + 1}", timestamp="2023-01-01T00:00:30Z"
            )
            for i in range(MAX_CONVERSATION_TURNS)
        ]

        context_at_limit = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:05:00Z",
            tool_name="chat",
            turns=turns_at_limit,
            initial_context={"prompt": "Analyze this code"},
        )
        mock_client.get.return_value = context_at_limit.model_dump_json()

        # This should fail - conversation has reached limit
        success = add_turn(thread_id, "user", "This should be rejected")
        assert success is False  # CONVERSATION STOPS HERE

    @patch("utils.conversation_memory.get_storage")
    def test_invalid_continuation_id_error(self, mock_storage):
        """Test that invalid continuation IDs raise proper error for restart"""
        from server import reconstruct_thread_context

        mock_client = Mock()
        mock_storage.return_value = mock_client
        mock_client.get.return_value = None  # Thread not found

        arguments = {"continuation_id": "invalid-uuid-12345", "prompt": "Continue conversation"}

        # Should raise ValueError asking to restart
        with pytest.raises(ValueError) as exc_info:
            import asyncio

            asyncio.run(reconstruct_thread_context(arguments))

        error_msg = str(exc_info.value)
        assert "Conversation thread 'invalid-uuid-12345' was not found or has expired" in error_msg
        assert (
            "Please restart the conversation by providing your full question/prompt without the continuation_id"
            in error_msg
        )

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "OPENAI_API_KEY": ""}, clear=False)
    def test_dynamic_max_turns_configuration(self):
        """Test that all functions respect MAX_CONVERSATION_TURNS configuration"""
        from providers.registry import ModelProviderRegistry

        ModelProviderRegistry.clear_cache()

        # This test ensures if we change MAX_CONVERSATION_TURNS, everything updates

        # Test with different max values by patching the constant
        test_values = [3, 7, 10]

        for test_max in test_values:
            # Create turns up to the test limit
            turns = [
                ConversationTurn(role="user", content=f"Turn {i}", timestamp="2023-01-01T00:00:00Z")
                for i in range(test_max)
            ]

            # Test history building respects the limit
            test_uuid = "12345678-1234-1234-1234-123456789012"
            context = ThreadContext(
                thread_id=test_uuid,
                created_at="2023-01-01T00:00:00Z",
                last_updated_at="2023-01-01T00:00:00Z",
                tool_name="chat",
                turns=turns,
                initial_context={},
            )

            history, tokens = build_conversation_history(context, model_context=None)
            expected_turn_text = f"Turn {test_max}/{MAX_CONVERSATION_TURNS}"
            assert expected_turn_text in history

    def test_follow_up_instructions_dynamic_behavior(self):
        """Test that follow-up instructions change correctly based on turn count and max setting"""
        # Test with default MAX_CONVERSATION_TURNS
        max_turns = MAX_CONVERSATION_TURNS

        # Test early conversation (should allow follow-ups)
        early_instructions = get_follow_up_instructions(0, max_turns)
        assert "CONVERSATION CONTINUATION" in early_instructions
        assert f"({max_turns - 1} exchanges remaining)" in early_instructions
        assert "Feel free to ask clarifying questions" in early_instructions

        # Test mid conversation
        mid_instructions = get_follow_up_instructions(2, max_turns)
        assert "CONVERSATION CONTINUATION" in mid_instructions
        assert f"({max_turns - 3} exchanges remaining)" in mid_instructions
        assert "Feel free to ask clarifying questions" in mid_instructions

        # Test approaching limit (should stop follow-ups)
        limit_instructions = get_follow_up_instructions(max_turns - 1, max_turns)
        assert "Do NOT include any follow-up questions" in limit_instructions
        assert "final exchange" in limit_instructions

        # Test at limit
        at_limit_instructions = get_follow_up_instructions(max_turns, max_turns)
        assert "Do NOT include any follow-up questions" in at_limit_instructions

        # Test with custom max_turns to ensure dynamic behavior
        custom_max = 3
        custom_early = get_follow_up_instructions(0, custom_max)
        assert f"({custom_max - 1} exchanges remaining)" in custom_early

        custom_limit = get_follow_up_instructions(custom_max - 1, custom_max)
        assert "Do NOT include any follow-up questions" in custom_limit

    def test_follow_up_instructions_defaults_to_config(self):
        """Test that follow-up instructions use MAX_CONVERSATION_TURNS when max_turns not provided"""
        instructions = get_follow_up_instructions(0)  # No max_turns parameter
        expected_remaining = MAX_CONVERSATION_TURNS - 1
        assert f"({expected_remaining} exchanges remaining)" in instructions

    @patch("utils.conversation_memory.get_storage")
    def test_complete_conversation_with_dynamic_turns(self, mock_storage):
        """Test complete conversation respecting MAX_CONVERSATION_TURNS dynamically"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        thread_id = create_thread("chat", {"prompt": "Start conversation"})

        # Simulate conversation up to MAX_CONVERSATION_TURNS - 1
        for turn_num in range(MAX_CONVERSATION_TURNS - 1):
            # Mock context with current turns
            turns = [
                ConversationTurn(
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"Turn {i + 1}",
                    timestamp="2023-01-01T00:00:00Z",
                )
                for i in range(turn_num)
            ]

            context = ThreadContext(
                thread_id=thread_id,
                created_at="2023-01-01T00:00:00Z",
                last_updated_at="2023-01-01T00:00:00Z",
                tool_name="chat",
                turns=turns,
                initial_context={"prompt": "Start conversation"},
            )
            mock_client.get.return_value = context.model_dump_json()

            # Should succeed
            success = add_turn(thread_id, "user", f"User turn {turn_num + 1}")
            assert success is True, f"Turn {turn_num + 1} should succeed"

        # Now we should be at the limit - create final context
        final_turns = [
            ConversationTurn(
                role="user" if i % 2 == 0 else "assistant", content=f"Turn {i + 1}", timestamp="2023-01-01T00:00:00Z"
            )
            for i in range(MAX_CONVERSATION_TURNS)
        ]

        final_context = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:00:00Z",
            tool_name="chat",
            turns=final_turns,
            initial_context={"prompt": "Start conversation"},
        )
        mock_client.get.return_value = final_context.model_dump_json()

        # This should fail - at the limit
        success = add_turn(thread_id, "user", "This should fail")
        assert success is False, f"Turn {MAX_CONVERSATION_TURNS + 1} should fail"

    @patch("utils.conversation_memory.get_storage")
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "OPENAI_API_KEY": ""}, clear=False)
    def test_conversation_with_files_and_context_preservation(self, mock_storage):
        """Test complete conversation flow with file tracking and context preservation"""
        from providers.registry import ModelProviderRegistry

        ModelProviderRegistry.clear_cache()

        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Start conversation with files
        thread_id = create_thread("analyze", {"prompt": "Analyze this codebase", "files": ["/project/src/"]})

        # Turn 1: Claude provides context with multiple files
        initial_context = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:00:00Z",
            tool_name="analyze",
            turns=[],
            initial_context={"prompt": "Analyze this codebase", "files": ["/project/src/"]},
        )
        mock_client.get.return_value = initial_context.model_dump_json()

        # Add Gemini's response
        success = add_turn(
            thread_id,
            "assistant",
            "I've analyzed your codebase structure.",
            files=["/project/src/main.py", "/project/src/utils.py"],
            tool_name="analyze",
        )
        assert success is True

        # Turn 2: Claude responds with different files
        context_turn_1 = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="analyze",
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="I've analyzed your codebase structure.",
                    timestamp="2023-01-01T00:00:30Z",
                    files=["/project/src/main.py", "/project/src/utils.py"],
                    tool_name="analyze",
                )
            ],
            initial_context={"prompt": "Analyze this codebase", "files": ["/project/src/"]},
        )
        mock_client.get.return_value = context_turn_1.model_dump_json()

        # User responds with test files
        success = add_turn(
            thread_id, "user", "Yes, check the test coverage", files=["/project/tests/", "/project/test_main.py"]
        )
        assert success is True

        # Turn 3: Gemini analyzes tests
        context_turn_2 = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:02:00Z",
            tool_name="analyze",
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="I've analyzed your codebase structure.",
                    timestamp="2023-01-01T00:00:30Z",
                    files=["/project/src/main.py", "/project/src/utils.py"],
                    tool_name="analyze",
                ),
                ConversationTurn(
                    role="user",
                    content="Yes, check the test coverage",
                    timestamp="2023-01-01T00:01:30Z",
                    files=["/project/tests/", "/project/test_main.py"],
                ),
            ],
            initial_context={"prompt": "Analyze this codebase", "files": ["/project/src/"]},
        )
        mock_client.get.return_value = context_turn_2.model_dump_json()

        success = add_turn(
            thread_id,
            "assistant",
            "Test coverage analysis complete. Coverage is 85%.",
            files=["/project/tests/test_utils.py", "/project/coverage.html"],
            tool_name="analyze",
        )
        assert success is True

        # Build conversation history and verify chronological file preservation
        final_context = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:03:00Z",
            tool_name="analyze",
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="I've analyzed your codebase structure.",
                    timestamp="2023-01-01T00:00:30Z",
                    files=["/project/src/main.py", "/project/src/utils.py"],
                    tool_name="analyze",
                ),
                ConversationTurn(
                    role="user",
                    content="Yes, check the test coverage",
                    timestamp="2023-01-01T00:01:30Z",
                    files=["/project/tests/", "/project/test_main.py"],
                ),
                ConversationTurn(
                    role="assistant",
                    content="Test coverage analysis complete. Coverage is 85%.",
                    timestamp="2023-01-01T00:02:30Z",
                    files=["/project/tests/test_utils.py", "/project/coverage.html"],
                    tool_name="analyze",
                ),
            ],
            initial_context={"prompt": "Analyze this codebase", "files": ["/project/src/"]},
        )

        history, tokens = build_conversation_history(final_context)

        # Verify chronological order and speaker identification
        assert "--- Turn 1 (Gemini using analyze) ---" in history
        assert "--- Turn 2 (Claude) ---" in history
        assert "--- Turn 3 (Gemini using analyze) ---" in history

        # Verify all files are preserved in chronological order
        turn_1_files = "Files used in this turn: /project/src/main.py, /project/src/utils.py"
        turn_2_files = "Files used in this turn: /project/tests/, /project/test_main.py"
        turn_3_files = "Files used in this turn: /project/tests/test_utils.py, /project/coverage.html"

        assert turn_1_files in history
        assert turn_2_files in history
        assert turn_3_files in history

        # Verify content
        assert "I've analyzed your codebase structure." in history
        assert "Yes, check the test coverage" in history
        assert "Test coverage analysis complete. Coverage is 85%." in history

        # Verify chronological ordering (turn 1 appears before turn 2, etc.)
        turn_1_pos = history.find("--- Turn 1 (Gemini using analyze) ---")
        turn_2_pos = history.find("--- Turn 2 (Claude) ---")
        turn_3_pos = history.find("--- Turn 3 (Gemini using analyze) ---")

        assert turn_1_pos < turn_2_pos < turn_3_pos

    @patch("utils.conversation_memory.get_storage")
    def test_stateless_request_isolation(self, mock_storage):
        """Test that each request cycle is independent but shares context via Redis"""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Simulate two different "processes" accessing same thread
        thread_id = "12345678-1234-1234-1234-123456789012"

        # Process 1: Creates thread
        initial_context = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:00:00Z",
            tool_name="thinkdeep",
            turns=[],
            initial_context={"prompt": "Think about architecture"},
        )
        mock_client.get.return_value = initial_context.model_dump_json()

        success = add_turn(thread_id, "assistant", "Architecture analysis")
        assert success is True

        # Process 2: Different "request cycle" accesses same thread
        context_from_redis = ThreadContext(
            thread_id=thread_id,
            created_at="2023-01-01T00:00:00Z",
            last_updated_at="2023-01-01T00:01:00Z",
            tool_name="thinkdeep",
            turns=[
                ConversationTurn(
                    role="assistant",
                    content="Architecture analysis",
                    timestamp="2023-01-01T00:00:30Z",
                )
            ],
            initial_context={"prompt": "Think about architecture"},
        )
        mock_client.get.return_value = context_from_redis.model_dump_json()

        # Verify context continuity across "processes"
        retrieved_context = get_thread(thread_id)
        assert retrieved_context is not None
        assert len(retrieved_context.turns) == 1

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "OPENAI_API_KEY": ""}, clear=False)
    def test_token_limit_optimization_in_conversation_history(self):
        """Test that build_conversation_history efficiently handles token limits"""
        import os
        import tempfile

        from providers.registry import ModelProviderRegistry

        ModelProviderRegistry.clear_cache()

        from utils.conversation_memory import build_conversation_history

        # Create test files with known content sizes
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create small and large test files
            small_file = os.path.join(temp_dir, "small.py")
            large_file = os.path.join(temp_dir, "large.py")

            small_content = "# Small file\nprint('hello')\n"
            large_content = "# Large file\n" + "x = 1\n" * 10000  # Very large file

            with open(small_file, "w") as f:
                f.write(small_content)
            with open(large_file, "w") as f:
                f.write(large_content)

            # Create context with files that would exceed token limit
            context = ThreadContext(
                thread_id="test-token-limit",
                created_at="2023-01-01T00:00:00Z",
                last_updated_at="2023-01-01T00:01:00Z",
                tool_name="analyze",
                turns=[
                    ConversationTurn(
                        role="user",
                        content="Analyze these files",
                        timestamp="2023-01-01T00:00:30Z",
                        files=[small_file, large_file],  # Large file should be truncated
                    )
                ],
                initial_context={"prompt": "Analyze code"},
            )

            # Build conversation history (should handle token limits gracefully)
            history, tokens = build_conversation_history(context, model_context=None)

            # Verify the history was built successfully
            assert "=== CONVERSATION HISTORY" in history
            assert "=== FILES REFERENCED IN THIS CONVERSATION ===" in history

            # The small file should be included, but large file might be truncated
            # At minimum, verify no crashes and history is generated
            assert len(history) > 0

            # If truncation occurred, there should be a note about it
            if "additional file(s) were truncated due to token limit" in history:
                assert small_file in history or large_file in history
            else:
                # Both files fit within limit
                assert small_file in history
                assert large_file in history


if __name__ == "__main__":
    pytest.main([__file__])
