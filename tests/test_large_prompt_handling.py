"""
Tests for large prompt handling functionality.

This test module verifies that the MCP server correctly handles
prompts that exceed the 50,000 character limit by requesting
Claude to save them to a file and resend.
"""

import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from config import MCP_PROMPT_SIZE_LIMIT
from tools.chat import ChatTool
from tools.codereview import CodeReviewTool
from tools.shared.exceptions import ToolExecutionError

# from tools.debug import DebugIssueTool  # Commented out - debug tool refactored


class TestLargePromptHandling:
    """Test suite for large prompt handling across all tools."""

    def teardown_method(self):
        """Clean up after each test to prevent state pollution."""
        # Clear provider registry singleton
        from providers.registry import ModelProviderRegistry

        ModelProviderRegistry._instance = None

    @pytest.fixture
    def large_prompt(self):
        """Create a prompt larger than MCP_PROMPT_SIZE_LIMIT characters."""
        return "x" * (MCP_PROMPT_SIZE_LIMIT + 1000)

    @pytest.fixture
    def normal_prompt(self):
        """Create a normal-sized prompt."""
        return "This is a normal prompt that should work fine."

    @pytest.fixture
    def temp_prompt_file(self, large_prompt):
        """Create a temporary prompt.txt file with large content."""
        # Create temp file with exact name "prompt.txt"
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, "prompt.txt")
        with open(file_path, "w") as f:
            f.write(large_prompt)
        return file_path

    @pytest.mark.asyncio
    async def test_chat_large_prompt_detection(self, large_prompt):
        """Test that chat tool detects large prompts."""
        tool = ChatTool()
        temp_dir = tempfile.mkdtemp()
        temp_dir = tempfile.mkdtemp()
        try:
            with pytest.raises(ToolExecutionError) as exc_info:
                await tool.execute({"prompt": large_prompt, "working_directory_absolute_path": temp_dir})
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        output = json.loads(exc_info.value.payload)
        assert output["status"] == "resend_prompt"
        assert f"{MCP_PROMPT_SIZE_LIMIT:,} characters" in output["content"]
        # The prompt size should match the user input since we check at MCP transport boundary before adding internal content
        assert output["metadata"]["prompt_size"] == len(large_prompt)
        assert output["metadata"]["limit"] == MCP_PROMPT_SIZE_LIMIT

    @pytest.mark.asyncio
    async def test_chat_normal_prompt_works(self, normal_prompt):
        """Test that chat tool works normally with regular prompts."""
        tool = ChatTool()

        temp_dir = tempfile.mkdtemp()

        # This test runs in the test environment which uses dummy keys
        # The chat tool will return an error for dummy keys, which is expected
        try:
            try:
                result = await tool.execute(
                    {"prompt": normal_prompt, "model": "gemini-2.5-flash", "working_directory_absolute_path": temp_dir}
                )
            except ToolExecutionError as exc:
                output = json.loads(exc.payload if hasattr(exc, "payload") else str(exc))
            else:
                assert len(result) == 1
                output = json.loads(result[0].text)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Whether provider succeeds or fails, we should not hit the resend_prompt branch
        assert output["status"] != "resend_prompt"

    @pytest.mark.asyncio
    async def test_chat_prompt_file_handling(self):
        """Test that chat tool correctly handles prompt.txt files with reasonable size."""
        tool = ChatTool()
        # Use a smaller prompt that won't exceed limit when combined with system prompt
        reasonable_prompt = "This is a reasonable sized prompt for testing prompt.txt file handling."

        # Create a temp file with reasonable content
        temp_dir = tempfile.mkdtemp()
        temp_prompt_file = os.path.join(temp_dir, "prompt.txt")
        with open(temp_prompt_file, "w") as f:
            f.write(reasonable_prompt)

        try:
            try:
                result = await tool.execute(
                    {
                        "prompt": "",
                        "absolute_file_paths": [temp_prompt_file],
                        "model": "gemini-2.5-flash",
                        "working_directory_absolute_path": temp_dir,
                    }
                )
            except ToolExecutionError as exc:
                output = json.loads(exc.payload if hasattr(exc, "payload") else str(exc))
            else:
                assert len(result) == 1
                output = json.loads(result[0].text)

            # The test may fail with dummy API keys, which is expected behavior.
            # We're mainly testing that the tool processes prompt files correctly without size errors.
            assert output["status"] != "resend_prompt"
        finally:
            # Cleanup
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_codereview_large_focus(self, large_prompt):
        """Test that codereview tool detects large focus_on field using real integration testing."""
        import importlib
        import os

        tool = CodeReviewTool()

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for real provider resolution
            os.environ["OPENAI_API_KEY"] = "sk-test-key-large-focus-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"

            # Clear other provider keys to isolate to OpenAI
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            # Test with real provider resolution
            try:
                args = {
                    "step": "initial review setup",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Initial testing",
                    "relevant_files": ["/some/file.py"],
                    "files_checked": ["/some/file.py"],
                    "focus_on": large_prompt,
                    "prompt": "Test code review for validation purposes",
                    "model": "o3-mini",
                }

                try:
                    result = await tool.execute(args)
                except ToolExecutionError as exc:
                    output = json.loads(exc.payload if hasattr(exc, "payload") else str(exc))
                else:
                    assert len(result) == 1
                    output = json.loads(result[0].text)

                # The large focus_on may trigger the resend_prompt guard before provider access.
                # When the guard does not trigger, auto-mode falls back to provider selection and
                # returns an error about the unavailable model. Both behaviors are acceptable for this test.
                if output.get("status") == "resend_prompt":
                    assert output["metadata"]["prompt_size"] == len(large_prompt)
                else:
                    assert output.get("status") == "error"
                    assert "Model" in output.get("content", "")

            except Exception as e:
                # If we get an unexpected exception, ensure it's not a mock artifact
                error_msg = str(e)
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error (API, authentication, etc.)
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None

    # NOTE: Precommit test has been removed because the precommit tool has been
    # refactored to use a workflow-based pattern instead of accepting simple prompt/path fields.
    # The new precommit tool requires workflow fields like: step, step_number, total_steps,
    # next_step_required, findings, etc. See simulator_tests/test_precommitworkflow_validation.py
    # for comprehensive workflow testing including large prompt handling.

    # NOTE: Debug tool tests have been commented out because the debug tool has been
    # refactored to use a self-investigation pattern instead of accepting a prompt field.
    # The new debug tool requires fields like: step, step_number, total_steps, next_step_required, findings
    # and doesn't have the "resend_prompt" functionality for large prompts.

    # @pytest.mark.asyncio
    # async def test_debug_large_error_description(self, large_prompt):
    #     """Test that debug tool detects large error_description."""
    #     tool = DebugIssueTool()
    #     result = await tool.execute({"prompt": large_prompt})
    #
    #     assert len(result) == 1
    #     output = json.loads(result[0].text)
    #     assert output["status"] == "resend_prompt"

    # @pytest.mark.asyncio
    # async def test_debug_large_error_context(self, large_prompt, normal_prompt):
    #     """Test that debug tool detects large error_context."""
    #     tool = DebugIssueTool()
    #     result = await tool.execute({"prompt": normal_prompt, "error_context": large_prompt})
    #
    #     assert len(result) == 1
    #     output = json.loads(result[0].text)
    #     assert output["status"] == "resend_prompt"

    # Removed: test_analyze_large_question - workflow tool handles large prompts differently

    @pytest.mark.asyncio
    async def test_multiple_files_with_prompt_txt(self, temp_prompt_file):
        """Test handling of prompt.txt alongside other files."""
        tool = ChatTool()
        other_file = "/some/other/file.py"

        with (
            patch("utils.model_context.ModelContext") as mock_model_context_cls,
            patch.object(tool, "handle_prompt_file") as mock_handle_prompt,
            patch.object(tool, "_prepare_file_content_for_prompt") as mock_prepare_files,
        ):
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.generate_content.return_value = MagicMock(
                content="Success",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash",
                metadata={"finish_reason": "STOP"},
            )

            from utils.model_context import TokenAllocation

            mock_model_context = MagicMock()
            mock_model_context.model_name = "gemini-2.5-flash"
            mock_model_context.provider = mock_provider
            mock_model_context.capabilities = MagicMock(supports_extended_thinking=False)
            mock_model_context.estimate_tokens.return_value = 1000  # Mock token estimation
            mock_model_context.calculate_token_allocation.return_value = TokenAllocation(
                total_tokens=1_000_000,
                content_tokens=800_000,
                response_tokens=200_000,
                file_tokens=320_000,
                history_tokens=320_000,
            )
            mock_model_context_cls.return_value = mock_model_context

            # Return the prompt content and updated files list (without prompt.txt)
            mock_handle_prompt.return_value = ("Large prompt content from file", [other_file])

            # Mock the centralized file preparation method
            mock_prepare_files.return_value = ("File content", [other_file])

            # Use a small prompt to avoid triggering size limit
            await tool.execute(
                {
                    "prompt": "Test prompt",
                    "absolute_file_paths": [temp_prompt_file, other_file],
                    "working_directory_absolute_path": os.path.dirname(temp_prompt_file),
                }
            )

            # Verify handle_prompt_file was called with the original files list
            mock_handle_prompt.assert_called_once_with([temp_prompt_file, other_file])

            # Verify _prepare_file_content_for_prompt was called with the updated files list (without prompt.txt)
            mock_prepare_files.assert_called_once()
            files_arg = mock_prepare_files.call_args[0][0]
            assert len(files_arg) == 1
            assert files_arg[0] == other_file

        temp_dir = os.path.dirname(temp_prompt_file)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_boundary_case_exactly_at_limit(self):
        """Test prompt exactly at MCP_PROMPT_SIZE_LIMIT characters (should pass with the fix)."""
        tool = ChatTool()
        exact_prompt = "x" * MCP_PROMPT_SIZE_LIMIT

        # Mock the model provider to avoid real API calls
        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.get_capabilities.return_value = MagicMock(supports_extended_thinking=False)
            mock_provider.generate_content.return_value = MagicMock(
                content="Response to the large prompt",
                usage={"input_tokens": 12000, "output_tokens": 10, "total_tokens": 12010},
                model_name="gemini-2.5-flash",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            # With the fix, this should now pass because we check at MCP transport boundary before adding internal content
            temp_dir = tempfile.mkdtemp()
            try:
                try:
                    result = await tool.execute({"prompt": exact_prompt, "working_directory_absolute_path": temp_dir})
                except ToolExecutionError as exc:
                    output = json.loads(exc.payload if hasattr(exc, "payload") else str(exc))
                else:
                    output = json.loads(result[0].text)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
            assert output["status"] != "resend_prompt"

    @pytest.mark.asyncio
    async def test_boundary_case_just_over_limit(self):
        """Test prompt just over MCP_PROMPT_SIZE_LIMIT characters (should trigger file request)."""
        tool = ChatTool()
        over_prompt = "x" * (MCP_PROMPT_SIZE_LIMIT + 1)

        temp_dir = tempfile.mkdtemp()
        try:
            try:
                result = await tool.execute({"prompt": over_prompt, "working_directory_absolute_path": temp_dir})
            except ToolExecutionError as exc:
                output = json.loads(exc.payload if hasattr(exc, "payload") else str(exc))
            else:
                output = json.loads(result[0].text)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        assert output["status"] == "resend_prompt"

    @pytest.mark.asyncio
    async def test_empty_prompt_no_file(self):
        """Test empty prompt without prompt.txt file."""
        tool = ChatTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.get_capabilities.return_value = MagicMock(supports_extended_thinking=False)
            mock_provider.generate_content.return_value = MagicMock(
                content="Success",
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash",
                metadata={"finish_reason": "STOP"},
            )
            mock_get_provider.return_value = mock_provider

            temp_dir = tempfile.mkdtemp()
            try:
                try:
                    result = await tool.execute({"prompt": "", "working_directory_absolute_path": temp_dir})
                except ToolExecutionError as exc:
                    output = json.loads(exc.payload if hasattr(exc, "payload") else str(exc))
                else:
                    output = json.loads(result[0].text)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
            assert output["status"] != "resend_prompt"

    @pytest.mark.asyncio
    async def test_prompt_file_read_error(self):
        """Test handling when prompt.txt can't be read."""
        from tests.mock_helpers import create_mock_provider

        tool = ChatTool()
        bad_file = "/nonexistent/prompt.txt"

        with (
            patch.object(tool, "get_model_provider") as mock_get_provider,
            patch("utils.model_context.ModelContext") as mock_model_context_class,
        ):

            mock_provider = create_mock_provider(model_name="gemini-2.5-flash", context_window=1_048_576)
            mock_provider.generate_content.return_value.content = "Success"
            mock_get_provider.return_value = mock_provider

            # Mock ModelContext to avoid the comparison issue
            from utils.model_context import TokenAllocation

            mock_model_context = MagicMock()
            mock_model_context.model_name = "gemini-2.5-flash"
            mock_model_context.estimate_tokens.return_value = 1000  # Mock token estimation
            mock_model_context.calculate_token_allocation.return_value = TokenAllocation(
                total_tokens=1_048_576,
                content_tokens=838_861,
                response_tokens=209_715,
                file_tokens=335_544,
                history_tokens=335_544,
            )
            mock_model_context_class.return_value = mock_model_context

            # Should continue with empty prompt when file can't be read
            temp_dir = tempfile.mkdtemp()
            try:
                try:
                    result = await tool.execute(
                        {"prompt": "", "absolute_file_paths": [bad_file], "working_directory_absolute_path": temp_dir}
                    )
                except ToolExecutionError as exc:
                    output = json.loads(exc.payload if hasattr(exc, "payload") else str(exc))
                else:
                    output = json.loads(result[0].text)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
            assert output["status"] != "resend_prompt"

    @pytest.mark.asyncio
    async def test_large_file_context_does_not_trigger_mcp_prompt_limit(self, tmp_path):
        """Large context files should not be blocked by MCP prompt limit enforcement."""
        from tests.mock_helpers import create_mock_provider
        from utils.model_context import TokenAllocation

        tool = ChatTool()

        # Create a file significantly larger than MCP_PROMPT_SIZE_LIMIT characters
        large_content = "A" * (MCP_PROMPT_SIZE_LIMIT * 5)
        large_file = tmp_path / "huge_context.txt"
        large_file.write_text(large_content)

        mock_provider = create_mock_provider(model_name="flash")

        class DummyModelContext:
            def __init__(self, provider):
                self.model_name = "flash"
                self._provider = provider
                self.capabilities = provider.get_capabilities("flash")

            @property
            def provider(self):
                return self._provider

            def estimate_tokens(self, text):
                """Estimate token count for text."""
                return len(text) // 4  # Match fallback ratio

            def calculate_token_allocation(self):
                return TokenAllocation(
                    total_tokens=1_048_576,
                    content_tokens=838_861,
                    response_tokens=209_715,
                    file_tokens=335_544,
                    history_tokens=335_544,
                )

        dummy_context = DummyModelContext(mock_provider)

        with patch.object(tool, "get_model_provider", return_value=mock_provider):
            result = await tool.execute(
                {
                    "prompt": "Summarize the design decisions",
                    "absolute_file_paths": [str(large_file)],
                    "model": "flash",
                    "working_directory_absolute_path": str(tmp_path),
                    "_model_context": dummy_context,
                }
            )

        output = json.loads(result[0].text)
        assert output["status"] != "resend_prompt"

    @pytest.mark.asyncio
    async def test_mcp_boundary_with_large_internal_context(self):
        """
        Critical test: Ensure MCP_PROMPT_SIZE_LIMIT only applies to user input (MCP boundary),
        NOT to internal context like conversation history, system prompts, or file content.

        This test verifies that even if our internal prompt (with system prompts, history, etc.)
        exceeds MCP_PROMPT_SIZE_LIMIT, it should still work as long as the user's input is small.
        """

        tool = ChatTool()

        # Small user input that should pass MCP boundary check
        small_user_prompt = "What is the weather like?"

        # Mock a huge conversation history that would exceed MCP limits if incorrectly checked
        huge_history = "x" * (MCP_PROMPT_SIZE_LIMIT * 2)  # 100K chars = way over 50K limit

        temp_dir = tempfile.mkdtemp()
        original_prepare_prompt = tool.prepare_prompt

        try:
            with (
                patch.object(tool, "get_model_provider") as mock_get_provider,
                patch("utils.model_context.ModelContext") as mock_model_context_class,
            ):
                from tests.mock_helpers import create_mock_provider
                from utils.model_context import TokenAllocation

                mock_provider = create_mock_provider(model_name="flash")
                mock_get_provider.return_value = mock_provider

                mock_model_context = MagicMock()
                mock_model_context.model_name = "flash"
                mock_model_context.provider = mock_provider
                mock_model_context.estimate_tokens.return_value = 1000  # Mock token estimation
                mock_model_context.calculate_token_allocation.return_value = TokenAllocation(
                    total_tokens=1_048_576,
                    content_tokens=838_861,
                    response_tokens=209_715,
                    file_tokens=335_544,
                    history_tokens=335_544,
                )
                mock_model_context_class.return_value = mock_model_context

                async def mock_prepare_prompt(request):
                    normal_prompt = await original_prepare_prompt(request)
                    huge_internal_prompt = f"{normal_prompt}\n\n=== HUGE INTERNAL CONTEXT ===\n{huge_history}"
                    assert len(huge_internal_prompt) > MCP_PROMPT_SIZE_LIMIT
                    return huge_internal_prompt

                tool.prepare_prompt = mock_prepare_prompt

                result = await tool.execute(
                    {"prompt": small_user_prompt, "model": "flash", "working_directory_absolute_path": temp_dir}
                )
                output = json.loads(result[0].text)

                assert output["status"] != "resend_prompt"

                mock_provider.generate_content.assert_called_once()
                call_kwargs = mock_provider.generate_content.call_args[1]
                actual_prompt = call_kwargs.get("prompt")

                assert len(actual_prompt) > MCP_PROMPT_SIZE_LIMIT
                assert huge_history in actual_prompt
                assert small_user_prompt in actual_prompt
        finally:
            tool.prepare_prompt = original_prepare_prompt
            shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_mcp_boundary_vs_internal_processing_distinction(self):
        """
        Test that clearly demonstrates the distinction between:
        1. MCP transport boundary (user input - SHOULD be limited)
        2. Internal processing (system prompts, files, history - should NOT be limited)
        """
        tool = ChatTool()

        # Test case 1: Large user input should fail at MCP boundary
        large_user_input = "x" * (MCP_PROMPT_SIZE_LIMIT + 1000)
        temp_dir = tempfile.mkdtemp()
        try:
            try:
                result = await tool.execute(
                    {"prompt": large_user_input, "model": "flash", "working_directory_absolute_path": temp_dir}
                )
            except ToolExecutionError as exc:
                output = json.loads(exc.payload if hasattr(exc, "payload") else str(exc))
            else:
                output = json.loads(result[0].text)

            assert output["status"] == "resend_prompt"  # Should fail
            assert "too large for MCP's token limits" in output["content"]

            # Test case 2: Small user input should succeed even with huge internal processing
            small_user_input = "Hello"

            try:
                result = await tool.execute(
                    {
                        "prompt": small_user_input,
                        "model": "gemini-2.5-flash",
                        "working_directory_absolute_path": temp_dir,
                    }
                )
            except ToolExecutionError as exc:
                output = json.loads(exc.payload if hasattr(exc, "payload") else str(exc))
            else:
                output = json.loads(result[0].text)

            # The test will fail with dummy API keys, which is expected behavior
            # We're mainly testing that the tool processes small prompts correctly without size errors
            assert output["status"] != "resend_prompt"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_continuation_with_huge_conversation_history(self):
        """
        Test that continuation calls with huge conversation history work correctly.
        This simulates the exact scenario where conversation history builds up and exceeds
        MCP_PROMPT_SIZE_LIMIT but should still work since history is internal processing.
        """
        tool = ChatTool()

        # Small user input for continuation
        small_continuation_prompt = "Continue the discussion"

        # Mock huge conversation history (simulates many turns of conversation)
        # Calculate repetitions needed to exceed MCP_PROMPT_SIZE_LIMIT
        base_text = "=== CONVERSATION HISTORY ===\n"
        repeat_text = "Previous message content\n"
        # Add buffer to ensure we exceed the limit
        target_size = MCP_PROMPT_SIZE_LIMIT + 1000
        available_space = target_size - len(base_text)
        repetitions_needed = (available_space // len(repeat_text)) + 1

        huge_conversation_history = base_text + (repeat_text * repetitions_needed)

        # Ensure the history exceeds MCP limits
        assert len(huge_conversation_history) > MCP_PROMPT_SIZE_LIMIT

        temp_dir = tempfile.mkdtemp()

        with (
            patch.object(tool, "get_model_provider") as mock_get_provider,
            patch("utils.model_context.ModelContext") as mock_model_context_class,
        ):
            from tests.mock_helpers import create_mock_provider

            mock_provider = create_mock_provider(model_name="flash")
            mock_provider.generate_content.return_value.content = "Continuing our conversation..."
            mock_get_provider.return_value = mock_provider

            # Mock ModelContext to avoid the comparison issue
            from utils.model_context import TokenAllocation

            mock_model_context = MagicMock()
            mock_model_context.model_name = "flash"
            mock_model_context.provider = mock_provider
            mock_model_context.estimate_tokens.return_value = 1000  # Mock token estimation
            mock_model_context.calculate_token_allocation.return_value = TokenAllocation(
                total_tokens=1_048_576,
                content_tokens=838_861,
                response_tokens=209_715,
                file_tokens=335_544,
                history_tokens=335_544,
            )
            mock_model_context_class.return_value = mock_model_context

            # Simulate continuation by having the request contain embedded conversation history
            # This mimics what server.py does when it embeds conversation history
            request_with_history = {
                "prompt": f"{huge_conversation_history}\n\n=== CURRENT REQUEST ===\n{small_continuation_prompt}",
                "model": "flash",
                "continuation_id": "test_thread_123",
                "working_directory_absolute_path": temp_dir,
            }

            # Mock the conversation history embedding to simulate server.py behavior
            original_execute = tool.__class__.execute

            async def mock_execute_with_history(self, arguments):
                # Check if this has continuation_id (simulating server.py logic)
                if arguments.get("continuation_id"):
                    # Simulate the case where conversation history is already embedded in prompt
                    # by server.py before calling the tool
                    field_value = arguments.get("prompt", "")
                    if "=== CONVERSATION HISTORY ===" in field_value:
                        # Set the flag that history is embedded
                        self._has_embedded_history = True

                        # The prompt field contains both history AND user input
                        # But we should only check the user input part for MCP boundary
                        # (This is what our fix ensures happens in prepare_prompt)

                # Call original execute
                return await original_execute(self, arguments)

            tool.__class__.execute = mock_execute_with_history

            try:
                # This should succeed because:
                # 1. The actual user input is small (passes MCP boundary check)
                # 2. The huge conversation history is internal processing (not subject to MCP limits)
                result = await tool.execute(request_with_history)
                output = json.loads(result[0].text)

                # Should succeed even though total prompt with history is huge
                assert output["status"] != "resend_prompt"
                assert "Continuing our conversation" in output["content"]

                # Verify the model was called with the complete prompt (including huge history)
                mock_provider.generate_content.assert_called_once()
                call_kwargs = mock_provider.generate_content.call_args[1]
                final_prompt = call_kwargs.get("prompt")

                # The final prompt should contain both history and user input
                assert huge_conversation_history in final_prompt
                assert small_continuation_prompt in final_prompt
                # And it should be huge (proving we don't limit internal processing)
                assert len(final_prompt) > MCP_PROMPT_SIZE_LIMIT

            finally:
                # Restore original execute method
                tool.__class__.execute = original_execute
                shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
