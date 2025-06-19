"""
Regression tests to ensure normal prompt handling still works after large prompt changes.

This test module verifies that all tools continue to work correctly with
normal-sized prompts after implementing the large prompt handling feature.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from tools.analyze import AnalyzeTool
from tools.chat import ChatTool
from tools.codereview import CodeReviewTool

# from tools.debug import DebugIssueTool  # Commented out - debug tool refactored
from tools.precommit import Precommit
from tools.thinkdeep import ThinkDeepTool


class TestPromptRegression:
    """Regression test suite for normal prompt handling."""

    @pytest.fixture
    def mock_model_response(self):
        """Create a mock model response."""
        from unittest.mock import Mock

        def _create_response(text="Test response"):
            # Return a Mock that acts like ModelResponse
            return Mock(
                content=text,
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                model_name="gemini-2.5-flash",
                metadata={"finish_reason": "STOP"},
            )

        return _create_response

    @pytest.mark.asyncio
    async def test_chat_normal_prompt(self, mock_model_response):
        """Test chat tool with normal prompt."""
        tool = ChatTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response(
                "This is a helpful response about Python."
            )
            mock_get_provider.return_value = mock_provider

            result = await tool.execute({"prompt": "Explain Python decorators"})

            assert len(result) == 1
            output = json.loads(result[0].text)
            assert output["status"] == "success"
            assert "helpful response about Python" in output["content"]

            # Verify provider was called
            mock_provider.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_with_files(self, mock_model_response):
        """Test chat tool with files parameter."""
        tool = ChatTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response()
            mock_get_provider.return_value = mock_provider

            # Mock file reading through the centralized method
            with patch.object(tool, "_prepare_file_content_for_prompt") as mock_prepare_files:
                mock_prepare_files.return_value = ("File content here", ["/path/to/file.py"])

                result = await tool.execute({"prompt": "Analyze this code", "files": ["/path/to/file.py"]})

                assert len(result) == 1
                output = json.loads(result[0].text)
                assert output["status"] == "success"
                mock_prepare_files.assert_called_once_with(["/path/to/file.py"], None, "Context files")

    @pytest.mark.asyncio
    async def test_thinkdeep_normal_analysis(self, mock_model_response):
        """Test thinkdeep tool with normal analysis."""
        tool = ThinkDeepTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response(
                "Here's a deeper analysis with edge cases..."
            )
            mock_get_provider.return_value = mock_provider

            result = await tool.execute(
                {
                    "prompt": "I think we should use a cache for performance",
                    "problem_context": "Building a high-traffic API",
                    "focus_areas": ["scalability", "reliability"],
                }
            )

            assert len(result) == 1
            output = json.loads(result[0].text)
            assert output["status"] == "success"
            assert "Critical Evaluation Required" in output["content"]
            assert "deeper analysis" in output["content"]

    @pytest.mark.asyncio
    async def test_codereview_normal_review(self, mock_model_response):
        """Test codereview tool with normal inputs."""
        tool = CodeReviewTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response(
                "Found 3 issues: 1) Missing error handling..."
            )
            mock_get_provider.return_value = mock_provider

            # Mock file reading
            with patch("tools.base.read_files") as mock_read_files:
                mock_read_files.return_value = "def main(): pass"

                result = await tool.execute(
                    {
                        "files": ["/path/to/code.py"],
                        "review_type": "security",
                        "focus_on": "Look for SQL injection vulnerabilities",
                        "prompt": "Test code review for validation purposes",
                    }
                )

                assert len(result) == 1
                output = json.loads(result[0].text)
                assert output["status"] == "success"
                assert "Found 3 issues" in output["content"]

    @pytest.mark.asyncio
    async def test_review_changes_normal_request(self, mock_model_response):
        """Test review_changes tool with normal original_request."""
        tool = Precommit()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response(
                "Changes look good, implementing feature as requested..."
            )
            mock_get_provider.return_value = mock_provider

            # Mock git operations
            with patch("tools.precommit.find_git_repositories") as mock_find_repos:
                with patch("tools.precommit.get_git_status") as mock_git_status:
                    mock_find_repos.return_value = ["/path/to/repo"]
                    mock_git_status.return_value = {
                        "branch": "main",
                        "ahead": 0,
                        "behind": 0,
                        "staged_files": ["file.py"],
                        "unstaged_files": [],
                        "untracked_files": [],
                    }

                    result = await tool.execute(
                        {
                            "path": "/path/to/repo",
                            "prompt": "Add user authentication feature with JWT tokens",
                        }
                    )

                    assert len(result) == 1
                    output = json.loads(result[0].text)
                    assert output["status"] == "success"

    # NOTE: Debug tool test has been commented out because the debug tool has been
    # refactored to use a self-investigation pattern instead of accepting prompt/error_context fields.
    # The new debug tool requires fields like: step, step_number, total_steps, next_step_required, findings

    # @pytest.mark.asyncio
    # async def test_debug_normal_error(self, mock_model_response):
    #     """Test debug tool with normal error description."""
    #     tool = DebugIssueTool()
    #
    #     with patch.object(tool, "get_model_provider") as mock_get_provider:
    #         mock_provider = MagicMock()
    #         mock_provider.get_provider_type.return_value = MagicMock(value="google")
    #         mock_provider.supports_thinking_mode.return_value = False
    #         mock_provider.generate_content.return_value = mock_model_response(
    #             "Root cause: The variable is undefined. Fix: Initialize it..."
    #         )
    #         mock_get_provider.return_value = mock_provider
    #
    #         result = await tool.execute(
    #             {
    #                 "prompt": "TypeError: Cannot read property 'name' of undefined",
    #                 "error_context": "at line 42 in user.js\n  console.log(user.name)",
    #                 "runtime_info": "Node.js v16.14.0",
    #             }
    #         )
    #
    #         assert len(result) == 1
    #         output = json.loads(result[0].text)
    #         assert output["status"] == "success"
    #         assert "Next Steps:" in output["content"]
    #         assert "Root cause" in output["content"]

    @pytest.mark.asyncio
    async def test_analyze_normal_question(self, mock_model_response):
        """Test analyze tool with normal question."""
        tool = AnalyzeTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response(
                "The code follows MVC pattern with clear separation..."
            )
            mock_get_provider.return_value = mock_provider

            # Mock file reading
            with patch("tools.base.read_files") as mock_read_files:
                mock_read_files.return_value = "class UserController: ..."

                result = await tool.execute(
                    {
                        "files": ["/path/to/project"],
                        "prompt": "What design patterns are used in this codebase?",
                        "analysis_type": "architecture",
                    }
                )

                assert len(result) == 1
                output = json.loads(result[0].text)
                assert output["status"] == "success"
                assert "MVC pattern" in output["content"]

    @pytest.mark.asyncio
    async def test_empty_optional_fields(self, mock_model_response):
        """Test tools work with empty optional fields."""
        tool = ChatTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response()
            mock_get_provider.return_value = mock_provider

            # Test with no files parameter
            result = await tool.execute({"prompt": "Hello"})

            assert len(result) == 1
            output = json.loads(result[0].text)
            assert output["status"] == "success"

    @pytest.mark.asyncio
    async def test_thinking_modes_work(self, mock_model_response):
        """Test that thinking modes are properly passed through."""
        tool = ChatTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response()
            mock_get_provider.return_value = mock_provider

            result = await tool.execute({"prompt": "Test", "thinking_mode": "high", "temperature": 0.8})

            assert len(result) == 1
            output = json.loads(result[0].text)
            assert output["status"] == "success"

            # Verify generate_content was called with correct parameters
            mock_provider.generate_content.assert_called_once()
            call_kwargs = mock_provider.generate_content.call_args[1]
            assert call_kwargs.get("temperature") == 0.8
            # thinking_mode would be passed if the provider supports it
            # In this test, we set supports_thinking_mode to False, so it won't be passed

    @pytest.mark.asyncio
    async def test_special_characters_in_prompts(self, mock_model_response):
        """Test prompts with special characters work correctly."""
        tool = ChatTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response()
            mock_get_provider.return_value = mock_provider

            special_prompt = 'Test with "quotes" and\nnewlines\tand tabs'
            result = await tool.execute({"prompt": special_prompt})

            assert len(result) == 1
            output = json.loads(result[0].text)
            assert output["status"] == "success"

    @pytest.mark.asyncio
    async def test_mixed_file_paths(self, mock_model_response):
        """Test handling of various file path formats."""
        tool = AnalyzeTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response()
            mock_get_provider.return_value = mock_provider

            with patch("tools.base.read_files") as mock_read_files:
                mock_read_files.return_value = "Content"

                result = await tool.execute(
                    {
                        "files": [
                            "/absolute/path/file.py",
                            "/Users/name/project/src/",
                            "/home/user/code.js",
                        ],
                        "prompt": "Analyze these files",
                    }
                )

                assert len(result) == 1
                output = json.loads(result[0].text)
                assert output["status"] == "success"
                mock_read_files.assert_called_once()

    @pytest.mark.asyncio
    async def test_unicode_content(self, mock_model_response):
        """Test handling of unicode content in prompts."""
        tool = ChatTool()

        with patch.object(tool, "get_model_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.get_provider_type.return_value = MagicMock(value="google")
            mock_provider.supports_thinking_mode.return_value = False
            mock_provider.generate_content.return_value = mock_model_response()
            mock_get_provider.return_value = mock_provider

            unicode_prompt = "Explain this: 你好世界 مرحبا بالعالم"
            result = await tool.execute({"prompt": unicode_prompt})

            assert len(result) == 1
            output = json.loads(result[0].text)
            assert output["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
