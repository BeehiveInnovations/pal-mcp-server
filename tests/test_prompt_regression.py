"""
Integration tests to ensure normal prompt handling works with real API calls.

This test module verifies that all tools continue to work correctly with
normal-sized prompts using real integration testing instead of mocks.

INTEGRATION TESTS:
These tests are marked with @pytest.mark.integration and make real API calls.
They use the local-llama model which is FREE and runs locally via Ollama.

Prerequisites:
- Ollama installed and running locally
- CUSTOM_API_URL environment variable set to your Ollama endpoint (e.g., http://localhost:11434)
- local-llama model available through custom provider configuration
- No API keys required - completely FREE to run unlimited times!

Running Tests:
- All tests (including integration): pytest tests/test_prompt_regression.py
- Unit tests only: pytest tests/test_prompt_regression.py -m "not integration"
- Integration tests only: pytest tests/test_prompt_regression.py -m "integration"

Note: Integration tests skip gracefully if CUSTOM_API_URL is not set.
They are excluded from CI/CD but run by default locally when Ollama is configured.
"""

import json
import os
import tempfile

import pytest

# Load environment variables from .env file
from dotenv import load_dotenv

from tools.analyze import AnalyzeTool
from tools.chat import ChatTool
from tools.codereview import CodeReviewTool
from tools.thinkdeep import ThinkDeepTool

load_dotenv()

# Check if CUSTOM_API_URL is available for local-llama
CUSTOM_API_AVAILABLE = os.getenv("CUSTOM_API_URL") is not None


def skip_if_no_custom_api():
    """Helper to skip integration tests if CUSTOM_API_URL is not available."""
    if not CUSTOM_API_AVAILABLE:
        pytest.skip(
            "CUSTOM_API_URL not set. To run integration tests with local-llama, ensure CUSTOM_API_URL is set in .env file (e.g., http://localhost:11434/v1)"
        )


class TestPromptIntegration:
    """Integration test suite for normal prompt handling with real API calls."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_chat_normal_prompt(self):
        """Test chat tool with normal prompt using real API."""
        skip_if_no_custom_api()

        tool = ChatTool()

        result = await tool.execute(
            {
                "prompt": "Explain Python decorators in one sentence",
                "model": "local-llama",  # Use available model for integration tests
            }
        )

        assert len(result) == 1
        output = json.loads(result[0].text)
        assert output["status"] in ["success", "continuation_available"]
        assert "content" in output
        assert len(output["content"]) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_chat_with_files(self):
        """Test chat tool with files parameter using real API."""
        skip_if_no_custom_api()

        tool = ChatTool()

        # Create a temporary Python file for testing
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
def hello_world():
    \"\"\"A simple hello world function.\"\"\"
    return "Hello, World!"

if __name__ == "__main__":
    print(hello_world())
"""
            )
            temp_file = f.name

        try:
            result = await tool.execute(
                {"prompt": "What does this Python code do?", "files": [temp_file], "model": "local-llama"}
            )

            assert len(result) == 1
            output = json.loads(result[0].text)
            assert output["status"] in ["success", "continuation_available"]
            assert "content" in output
            # Should mention the hello world function
            assert "hello" in output["content"].lower() or "function" in output["content"].lower()
        finally:
            # Clean up temp file
            os.unlink(temp_file)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_thinkdeep_normal_analysis(self):
        """Test thinkdeep tool with normal analysis using real API."""
        skip_if_no_custom_api()

        tool = ThinkDeepTool()

        result = await tool.execute(
            {
                "step": "I think we should use a cache for performance",
                "step_number": 1,
                "total_steps": 1,
                "next_step_required": False,
                "findings": "Building a high-traffic API - considering scalability and reliability",
                "problem_context": "Building a high-traffic API",
                "focus_areas": ["scalability", "reliability"],
                "model": "local-llama",
            }
        )

        assert len(result) == 1
        output = json.loads(result[0].text)
        # ThinkDeep workflow tool should process the analysis
        assert "status" in output
        assert output["status"] in ["calling_expert_analysis", "analysis_complete", "pause_for_investigation"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_codereview_normal_review(self):
        """Test codereview tool with workflow inputs using real API."""
        skip_if_no_custom_api()

        tool = CodeReviewTool()

        # Create a temporary Python file for testing
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
def process_user_input(user_input):
    # Potentially unsafe code for demonstration
    query = f"SELECT * FROM users WHERE name = '{user_input}'"
    return query

def main():
    user_name = input("Enter name: ")
    result = process_user_input(user_name)
    print(result)
"""
            )
            temp_file = f.name

        try:
            result = await tool.execute(
                {
                    "step": "Initial code review investigation - examining security vulnerabilities",
                    "step_number": 1,
                    "total_steps": 2,
                    "next_step_required": True,
                    "findings": "Found security issues in code",
                    "relevant_files": [temp_file],
                    "review_type": "security",
                    "focus_on": "Look for SQL injection vulnerabilities",
                    "model": "local-llama",
                }
            )

            assert len(result) == 1
            output = json.loads(result[0].text)
            assert "status" in output
            assert output["status"] in ["pause_for_code_review", "calling_expert_analysis"]
        finally:
            # Clean up temp file
            os.unlink(temp_file)

    # NOTE: Precommit test has been removed because the precommit tool has been
    # refactored to use a workflow-based pattern instead of accepting simple prompt/path fields.
    # The new precommit tool requires workflow fields like: step, step_number, total_steps,
    # next_step_required, findings, etc. See simulator_tests/test_precommitworkflow_validation.py
    # for comprehensive workflow testing.

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
    #         assert output["status"] in ["success", "continuation_available"]
    #         assert "Next Steps:" in output["content"]
    #         assert "Root cause" in output["content"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_normal_question(self):
        """Test analyze tool with normal question using real API."""
        skip_if_no_custom_api()

        tool = AnalyzeTool()

        # Create a temporary Python file demonstrating MVC pattern
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
# Model
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email

# View
class UserView:
    def display_user(self, user):
        return f"User: {user.name} ({user.email})"

# Controller
class UserController:
    def __init__(self, model, view):
        self.model = model
        self.view = view

    def get_user_display(self):
        return self.view.display_user(self.model)
"""
            )
            temp_file = f.name

        try:
            result = await tool.execute(
                {
                    "step": "What design patterns are used in this codebase?",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Initial architectural analysis",
                    "relevant_files": [temp_file],
                    "analysis_type": "architecture",
                    "model": "local-llama",
                }
            )

            assert len(result) == 1
            output = json.loads(result[0].text)
            assert "status" in output
            # Workflow analyze tool should process the analysis
            assert output["status"] in ["calling_expert_analysis", "pause_for_investigation"]
        finally:
            # Clean up temp file
            os.unlink(temp_file)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_empty_optional_fields(self):
        """Test tools work with empty optional fields using real API."""
        skip_if_no_custom_api()

        tool = ChatTool()

        # Test with no files parameter
        result = await tool.execute({"prompt": "Hello", "model": "local-llama"})

        assert len(result) == 1
        output = json.loads(result[0].text)
        assert output["status"] in ["success", "continuation_available"]
        assert "content" in output

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_thinking_modes_work(self):
        """Test that thinking modes are properly passed through using real API."""
        skip_if_no_custom_api()

        tool = ChatTool()

        result = await tool.execute(
            {
                "prompt": "Explain quantum computing briefly",
                "thinking_mode": "low",
                "temperature": 0.8,
                "model": "local-llama",
            }
        )

        assert len(result) == 1
        output = json.loads(result[0].text)
        assert output["status"] in ["success", "continuation_available"]
        assert "content" in output
        # Should contain some quantum-related content
        assert "quantum" in output["content"].lower() or "computing" in output["content"].lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_special_characters_in_prompts(self):
        """Test prompts with special characters work correctly using real API."""
        skip_if_no_custom_api()

        tool = ChatTool()

        special_prompt = (
            'Test with "quotes" and\nnewlines\tand tabs. Please just respond with the number that is the answer to 1+1.'
        )
        result = await tool.execute({"prompt": special_prompt, "model": "local-llama"})

        assert len(result) == 1
        output = json.loads(result[0].text)
        assert output["status"] in ["success", "continuation_available"]
        assert "content" in output
        # Should handle the special characters without crashing - the exact content doesn't matter as much as not failing
        assert len(output["content"]) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_mixed_file_paths(self):
        """Test handling of various file path formats using real API."""
        skip_if_no_custom_api()

        tool = AnalyzeTool()

        # Create multiple temporary files to test different path formats
        temp_files = []
        try:
            # Create first file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write("def function_one(): pass")
                temp_files.append(f.name)

            # Create second file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
                f.write("function functionTwo() { return 'hello'; }")
                temp_files.append(f.name)

            result = await tool.execute(
                {
                    "step": "Analyze these files",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Initial file analysis",
                    "relevant_files": temp_files,
                    "model": "local-llama",
                }
            )

            assert len(result) == 1
            output = json.loads(result[0].text)
            assert "status" in output
            # Should process the files
            assert output["status"] in [
                "calling_expert_analysis",
                "pause_for_investigation",
                "files_required_to_continue",
            ]
        finally:
            # Clean up temp files
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unicode_content(self):
        """Test handling of unicode content in prompts using real API."""
        skip_if_no_custom_api()

        tool = ChatTool()

        unicode_prompt = "Explain what these mean: 你好世界 (Chinese) and مرحبا بالعالم (Arabic)"
        result = await tool.execute({"prompt": unicode_prompt, "model": "local-llama"})

        assert len(result) == 1
        output = json.loads(result[0].text)
        assert output["status"] in ["success", "continuation_available"]
        assert "content" in output
        # Should mention hello or world or greeting in some form
        content_lower = output["content"].lower()
        assert "hello" in content_lower or "world" in content_lower or "greeting" in content_lower


if __name__ == "__main__":
    # Run integration tests by default when called directly
    pytest.main([__file__, "-v", "-m", "integration"])
