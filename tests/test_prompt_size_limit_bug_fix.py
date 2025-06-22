"""
Test for the prompt size limit bug fix.

This test verifies that SimpleTool correctly validates only the original user prompt
when conversation history is embedded, rather than validating the full enhanced prompt.
"""

from unittest.mock import MagicMock

from tools.chat import ChatTool


class TestPromptSizeLimitBugFix:
    """Test that the prompt size limit bug is fixed"""

    def test_prompt_size_validation_with_conversation_history(self):
        """Test that prompt size validation uses original prompt when conversation history is embedded"""

        # Create a ChatTool instance
        tool = ChatTool()

        # Simulate a short user prompt (should not trigger size limit)
        short_user_prompt = "Thanks for the help!"

        # Simulate conversation history (large content)
        conversation_history = "=== CONVERSATION HISTORY ===\n" + ("Previous conversation content. " * 5000)

        # Simulate enhanced prompt with conversation history (what server.py creates)
        enhanced_prompt = f"{conversation_history}\n\n=== NEW USER INPUT ===\n{short_user_prompt}"

        # Create request object simulation
        request = MagicMock()
        request.prompt = enhanced_prompt  # This is what get_request_prompt() would return

        # Simulate server.py behavior: store original prompt in _current_arguments
        tool._current_arguments = {
            "prompt": enhanced_prompt,  # Enhanced with history
            "_original_user_prompt": short_user_prompt,  # Original user input (our fix)
            "model": "local-llama",
        }

        # Test the hook method directly
        validation_content = tool.get_prompt_content_for_size_validation(enhanced_prompt)

        # Should return the original short prompt, not the enhanced prompt
        assert validation_content == short_user_prompt
        assert len(validation_content) == len(short_user_prompt)
        assert len(validation_content) < 1000  # Much smaller than enhanced prompt

        # Verify the enhanced prompt would have triggered the bug
        assert len(enhanced_prompt) > 50000  # This would trigger size limit

        # Test that size check passes with the original prompt
        size_check = tool.check_prompt_size(validation_content)
        assert size_check is None  # No size limit error

        # Test that size check would fail with enhanced prompt
        size_check_enhanced = tool.check_prompt_size(enhanced_prompt)
        assert size_check_enhanced is not None  # Would trigger size limit
        assert size_check_enhanced["status"] == "resend_prompt"

    def test_prompt_size_validation_without_original_prompt(self):
        """Test fallback behavior when no original prompt is stored (new conversations)"""

        tool = ChatTool()

        user_content = "Regular prompt without conversation history"

        # No _current_arguments (new conversation scenario)
        tool._current_arguments = None

        # Should fall back to validating the full user content
        validation_content = tool.get_prompt_content_for_size_validation(user_content)
        assert validation_content == user_content

    def test_prompt_size_validation_with_missing_original_prompt(self):
        """Test fallback when _current_arguments exists but no _original_user_prompt"""

        tool = ChatTool()

        user_content = "Regular prompt without conversation history"

        # _current_arguments exists but no _original_user_prompt field
        tool._current_arguments = {
            "prompt": user_content,
            "model": "local-llama",
            # No _original_user_prompt field
        }

        # Should fall back to validating the full user content
        validation_content = tool.get_prompt_content_for_size_validation(user_content)
        assert validation_content == user_content

    def test_base_tool_default_behavior(self):
        """Test that BaseTool's default implementation validates full content"""

        from tools.shared.base_tool import BaseTool

        # Create a minimal tool implementation for testing
        class TestTool(BaseTool):
            def get_name(self) -> str:
                return "test"

            def get_description(self) -> str:
                return "Test tool"

            def get_input_schema(self) -> dict:
                return {}

            def get_request_model(self, request) -> str:
                return "flash"

            def get_system_prompt(self) -> str:
                return "Test system prompt"

            async def prepare_prompt(self, request) -> str:
                return "Test prompt"

            async def execute(self, arguments: dict) -> list:
                return []

        tool = TestTool()
        user_content = "Test content"

        # Default implementation should return the same content
        validation_content = tool.get_prompt_content_for_size_validation(user_content)
        assert validation_content == user_content
