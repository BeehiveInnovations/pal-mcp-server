"""
Tests for dynamic context request and collaboration features
"""

import json
from unittest.mock import Mock, patch

import pytest

from tests.mock_helpers import create_mock_provider
from tools.analyze import AnalyzeTool
from tools.debug import DebugIssueTool
from tools.models import FilesNeededRequest, ToolOutput


class TestDynamicContextRequests:
    """Test the dynamic context request mechanism"""

    @pytest.fixture
    def analyze_tool(self):
        return AnalyzeTool()

    @pytest.fixture
    def debug_tool(self):
        return DebugIssueTool()

    @pytest.mark.asyncio
    @patch("tools.base.BaseTool.get_model_provider")
    async def test_clarification_request_parsing(self, mock_get_provider, analyze_tool):
        """Test that tools correctly parse clarification requests"""
        # Mock model to return a clarification request
        clarification_json = json.dumps(
            {
                "status": "files_required_to_continue",
                "mandatory_instructions": "I need to see the package.json file to understand dependencies",
                "files_needed": ["package.json", "package-lock.json"],
            }
        )

        mock_provider = create_mock_provider()
        mock_provider.get_provider_type.return_value = Mock(value="google")
        mock_provider.supports_thinking_mode.return_value = False
        mock_provider.generate_content.return_value = Mock(
            content=clarification_json, usage={}, model_name="gemini-2.5-flash-preview-05-20", metadata={}
        )
        mock_get_provider.return_value = mock_provider

        result = await analyze_tool.execute(
            {
                "files": ["/absolute/path/src/index.js"],
                "prompt": "Analyze the dependencies used in this project",
            }
        )

        assert len(result) == 1

        # Parse the response
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "files_required_to_continue"
        assert response_data["content_type"] == "json"

        # Parse the clarification request
        clarification = json.loads(response_data["content"])
        # Check that the enhanced instructions contain the original message and additional guidance
        expected_start = "I need to see the package.json file to understand dependencies"
        assert clarification["mandatory_instructions"].startswith(expected_start)
        assert "IMPORTANT GUIDANCE:" in clarification["mandatory_instructions"]
        assert "Use FULL absolute paths" in clarification["mandatory_instructions"]
        assert clarification["files_needed"] == ["package.json", "package-lock.json"]

    @pytest.mark.asyncio
    @patch("tools.base.BaseTool.get_model_provider")
    async def test_normal_response_not_parsed_as_clarification(self, mock_get_provider, debug_tool):
        """Test that normal responses are not mistaken for clarification requests"""
        normal_response = """
        ## Summary
        The error is caused by a missing import statement.

        ## Hypotheses (Ranked by Likelihood)

        ### 1. Missing Import (Confidence: High)
        **Root Cause:** The module 'utils' is not imported
        """

        mock_provider = create_mock_provider()
        mock_provider.get_provider_type.return_value = Mock(value="google")
        mock_provider.supports_thinking_mode.return_value = False
        mock_provider.generate_content.return_value = Mock(
            content=normal_response, usage={}, model_name="gemini-2.5-flash-preview-05-20", metadata={}
        )
        mock_get_provider.return_value = mock_provider

        result = await debug_tool.execute({"prompt": "NameError: name 'utils' is not defined"})

        assert len(result) == 1

        # Parse the response
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "success"
        assert response_data["content_type"] in ["text", "markdown"]
        assert "Summary" in response_data["content"]

    @pytest.mark.asyncio
    @patch("tools.base.BaseTool.get_model_provider")
    async def test_malformed_clarification_request_treated_as_normal(self, mock_get_provider, analyze_tool):
        """Test that malformed JSON clarification requests are treated as normal responses"""
        malformed_json = '{"status": "files_required_to_continue", "prompt": "Missing closing brace"'

        mock_provider = create_mock_provider()
        mock_provider.get_provider_type.return_value = Mock(value="google")
        mock_provider.supports_thinking_mode.return_value = False
        mock_provider.generate_content.return_value = Mock(
            content=malformed_json, usage={}, model_name="gemini-2.5-flash-preview-05-20", metadata={}
        )
        mock_get_provider.return_value = mock_provider

        result = await analyze_tool.execute({"files": ["/absolute/path/test.py"], "prompt": "What does this do?"})

        assert len(result) == 1

        # Should be treated as normal response due to JSON parse error
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "success"
        assert malformed_json in response_data["content"]

    @pytest.mark.asyncio
    @patch("tools.base.BaseTool.get_model_provider")
    async def test_clarification_with_suggested_action(self, mock_get_provider, debug_tool):
        """Test clarification request with suggested next action"""
        clarification_json = json.dumps(
            {
                "status": "files_required_to_continue",
                "mandatory_instructions": "I need to see the database configuration to diagnose the connection error",
                "files_needed": ["config/database.yml", "src/db.py"],
                "suggested_next_action": {
                    "tool": "debug",
                    "args": {
                        "prompt": "Connection timeout to database",
                        "files": [
                            "/config/database.yml",
                            "/src/db.py",
                            "/logs/error.log",
                        ],
                    },
                },
            }
        )

        mock_provider = create_mock_provider()
        mock_provider.get_provider_type.return_value = Mock(value="google")
        mock_provider.supports_thinking_mode.return_value = False
        mock_provider.generate_content.return_value = Mock(
            content=clarification_json, usage={}, model_name="gemini-2.5-flash-preview-05-20", metadata={}
        )
        mock_get_provider.return_value = mock_provider

        result = await debug_tool.execute(
            {
                "prompt": "Connection timeout to database",
                "files": ["/absolute/logs/error.log"],
            }
        )

        assert len(result) == 1

        response_data = json.loads(result[0].text)
        assert response_data["status"] == "files_required_to_continue"

        clarification = json.loads(response_data["content"])
        assert "suggested_next_action" in clarification
        assert clarification["suggested_next_action"]["tool"] == "debug"

    def test_tool_output_model_serialization(self):
        """Test ToolOutput model serialization"""
        output = ToolOutput(
            status="success",
            content="Test content",
            content_type="markdown",
            metadata={"tool_name": "test", "execution_time": 1.5},
        )

        json_str = output.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["status"] == "success"
        assert parsed["content"] == "Test content"
        assert parsed["content_type"] == "markdown"
        assert parsed["metadata"]["tool_name"] == "test"

    def test_clarification_request_model(self):
        """Test FilesNeededRequest model"""
        request = FilesNeededRequest(
            mandatory_instructions="Need more context",
            files_needed=["file1.py", "file2.py"],
            suggested_next_action={"tool": "analyze", "args": {}},
        )

        assert request.mandatory_instructions == "Need more context"
        assert len(request.files_needed) == 2
        assert request.suggested_next_action["tool"] == "analyze"

    def test_mandatory_instructions_enhancement(self):
        """Test that mandatory_instructions are enhanced with additional guidance"""
        from tools.base import BaseTool

        # Create a dummy tool instance for testing
        class TestTool(BaseTool):
            def get_name(self):
                return "test"

            def get_description(self):
                return "test"

            def get_request_model(self):
                return None

            def prepare_prompt(self, request):
                return ""

            def get_system_prompt(self):
                return ""

            def get_input_schema(self):
                return {}

        tool = TestTool()
        original = "I need additional files to proceed"
        enhanced = tool._enhance_mandatory_instructions(original)

        # Verify the original instructions are preserved
        assert enhanced.startswith(original)

        # Verify additional guidance is added
        assert "IMPORTANT GUIDANCE:" in enhanced
        assert "CRITICAL for providing accurate analysis" in enhanced
        assert "Use FULL absolute paths" in enhanced
        assert "continuation_id to continue" in enhanced

    @pytest.mark.asyncio
    @patch("tools.base.BaseTool.get_model_provider")
    async def test_error_response_format(self, mock_get_provider, analyze_tool):
        """Test error response format"""
        mock_get_provider.side_effect = Exception("API connection failed")

        result = await analyze_tool.execute({"files": ["/absolute/path/test.py"], "prompt": "Analyze this"})

        assert len(result) == 1

        response_data = json.loads(result[0].text)
        assert response_data["status"] == "error"
        assert "API connection failed" in response_data["content"]
        assert response_data["content_type"] == "text"


class TestCollaborationWorkflow:
    """Test complete collaboration workflows"""

    @pytest.mark.asyncio
    @patch("tools.base.BaseTool.get_model_provider")
    async def test_dependency_analysis_triggers_clarification(self, mock_get_provider):
        """Test that asking about dependencies without package files triggers clarification"""
        tool = AnalyzeTool()

        # Mock Gemini to request package.json when asked about dependencies
        clarification_json = json.dumps(
            {
                "status": "files_required_to_continue",
                "mandatory_instructions": "I need to see the package.json file to analyze npm dependencies",
                "files_needed": ["package.json", "package-lock.json"],
            }
        )

        mock_provider = create_mock_provider()
        mock_provider.get_provider_type.return_value = Mock(value="google")
        mock_provider.supports_thinking_mode.return_value = False
        mock_provider.generate_content.return_value = Mock(
            content=clarification_json, usage={}, model_name="gemini-2.5-flash-preview-05-20", metadata={}
        )
        mock_get_provider.return_value = mock_provider

        # Ask about dependencies with only source files
        result = await tool.execute(
            {
                "files": ["/absolute/path/src/index.js"],
                "prompt": "What npm packages and versions does this project use?",
            }
        )

        response = json.loads(result[0].text)
        assert (
            response["status"] == "files_required_to_continue"
        ), "Should request clarification when asked about dependencies without package files"

        clarification = json.loads(response["content"])
        assert "package.json" in str(clarification["files_needed"]), "Should specifically request package.json"

    @pytest.mark.asyncio
    @patch("tools.base.BaseTool.get_model_provider")
    async def test_multi_step_collaboration(self, mock_get_provider):
        """Test a multi-step collaboration workflow"""
        tool = DebugIssueTool()

        # Step 1: Initial request returns clarification needed
        clarification_json = json.dumps(
            {
                "status": "files_required_to_continue",
                "mandatory_instructions": "I need to see the configuration file to understand the connection settings",
                "files_needed": ["config.py"],
            }
        )

        mock_provider = create_mock_provider()
        mock_provider.get_provider_type.return_value = Mock(value="google")
        mock_provider.supports_thinking_mode.return_value = False
        mock_provider.generate_content.return_value = Mock(
            content=clarification_json, usage={}, model_name="gemini-2.5-flash-preview-05-20", metadata={}
        )
        mock_get_provider.return_value = mock_provider

        result1 = await tool.execute(
            {
                "prompt": "Database connection timeout",
                "error_context": "Timeout after 30s",
            }
        )

        response1 = json.loads(result1[0].text)
        assert response1["status"] == "files_required_to_continue"

        # Step 2: Claude would provide additional context and re-invoke
        # This simulates the second call with more context
        final_response = """
        ## Summary
        The database connection timeout is caused by incorrect host configuration.

        ## Hypotheses (Ranked by Likelihood)

        ### 1. Incorrect Database Host (Confidence: High)
        **Root Cause:** The config.py file shows the database host is set to 'localhost' but the database is running on a different server.
        """

        mock_provider.generate_content.return_value = Mock(
            content=final_response, usage={}, model_name="gemini-2.5-flash-preview-05-20", metadata={}
        )

        result2 = await tool.execute(
            {
                "prompt": "Database connection timeout",
                "error_context": "Timeout after 30s",
                "files": ["/absolute/path/config.py"],  # Additional context provided
            }
        )

        response2 = json.loads(result2[0].text)
        assert response2["status"] == "success"
        assert "incorrect host configuration" in response2["content"].lower()
