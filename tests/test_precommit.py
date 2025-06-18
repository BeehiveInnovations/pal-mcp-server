"""
Tests for the precommit tool
"""

import json
from unittest.mock import Mock, patch

import pytest

from tools.precommit import Precommit, PrecommitRequest


class TestPrecommitTool:
    """Test the precommit tool"""

    @pytest.fixture
    def tool(self):
        """Create tool instance"""
        return Precommit()

    def test_tool_metadata(self, tool):
        """Test tool metadata"""
        assert tool.get_name() == "precommit"
        assert "PRECOMMIT VALIDATION" in tool.get_description()
        assert "pre-commit" in tool.get_description()

        # Check schema
        schema = tool.get_input_schema()
        assert schema["type"] == "object"
        assert "path" in schema["properties"]
        assert "prompt" in schema["properties"]
        assert "compare_to" in schema["properties"]
        assert "review_type" in schema["properties"]

    def test_request_model_defaults(self):
        """Test request model default values"""
        request = PrecommitRequest(path="/some/absolute/path")
        assert request.path == "/some/absolute/path"
        assert request.prompt is None
        assert request.compare_to is None
        assert request.include_staged is True
        assert request.include_unstaged is True
        assert request.review_type == "full"
        assert request.severity_filter == "all"
        assert request.max_depth == 5
        assert request.files is None

    @pytest.mark.asyncio
    async def test_relative_path_rejected(self, tool):
        """Test that relative paths are rejected"""
        result = await tool.execute({"path": "./relative/path", "prompt": "Test"})
        assert len(result) == 1
        response = json.loads(result[0].text)
        assert response["status"] == "error"
        assert "must be FULL absolute paths" in response["content"]
        assert "./relative/path" in response["content"]

    @pytest.mark.asyncio
    @patch("tools.precommit.find_git_repositories")
    async def test_no_repositories_found(self, mock_find_repos, tool):
        """Test when no git repositories are found"""
        mock_find_repos.return_value = []

        request = PrecommitRequest(path="/absolute/path/no-git")
        result = await tool.prepare_prompt(request)

        assert result == "No git repositories found in the specified path."
        mock_find_repos.assert_called_once_with("/absolute/path/no-git", 5)

    @pytest.mark.asyncio
    @patch("tools.precommit.find_git_repositories")
    @patch("tools.precommit.get_git_status")
    @patch("tools.precommit.run_git_command")
    async def test_no_changes_found(self, mock_run_git, mock_status, mock_find_repos, tool):
        """Test when repositories have no changes"""
        mock_find_repos.return_value = ["/test/repo"]
        mock_status.return_value = {
            "branch": "main",
            "ahead": 0,
            "behind": 0,
            "staged_files": [],
            "unstaged_files": [],
            "untracked_files": [],
        }

        # No staged or unstaged files
        mock_run_git.side_effect = [
            (True, ""),  # staged files (empty)
            (True, ""),  # unstaged files (empty)
        ]

        request = PrecommitRequest(path="/absolute/repo/path")
        result = await tool.prepare_prompt(request)

        assert result == "No pending changes found in any of the git repositories."

    @pytest.mark.asyncio
    @patch("tools.precommit.find_git_repositories")
    @patch("tools.precommit.get_git_status")
    @patch("tools.precommit.run_git_command")
    async def test_staged_changes_review(
        self,
        mock_run_git,
        mock_status,
        mock_find_repos,
        tool,
    ):
        """Test reviewing staged changes"""
        mock_find_repos.return_value = ["/test/repo"]
        mock_status.return_value = {
            "branch": "feature",
            "ahead": 1,
            "behind": 0,
            "staged_files": ["main.py"],
            "unstaged_files": [],
            "untracked_files": [],
        }

        # Mock git commands
        mock_run_git.side_effect = [
            (True, "main.py\n"),  # staged files
            (
                True,
                "diff --git a/main.py b/main.py\n+print('hello')",
            ),  # diff for main.py
            (True, ""),  # unstaged files (empty)
        ]

        request = PrecommitRequest(
            path="/absolute/repo/path",
            prompt="Add hello message",
            review_type="security",
        )
        result = await tool.prepare_prompt(request)

        # Verify result structure
        assert "## Original Request" in result
        assert "Add hello message" in result
        assert "## Review Parameters" in result
        assert "Review Type: security" in result
        assert "## Repository Changes Summary" in result
        assert "Branch: feature" in result
        assert "## Git Diffs" in result

    @pytest.mark.asyncio
    @patch("tools.precommit.find_git_repositories")
    @patch("tools.precommit.get_git_status")
    @patch("tools.precommit.run_git_command")
    async def test_compare_to_invalid_ref(self, mock_run_git, mock_status, mock_find_repos, tool):
        """Test comparing to an invalid git ref"""
        mock_find_repos.return_value = ["/test/repo"]
        mock_status.return_value = {"branch": "main"}

        # Mock git commands - ref validation fails
        mock_run_git.side_effect = [
            (False, "fatal: not a valid ref"),  # rev-parse fails
        ]

        request = PrecommitRequest(path="/absolute/repo/path", compare_to="invalid-branch")
        result = await tool.prepare_prompt(request)

        # When all repos have errors and no changes, we get this message
        assert "No pending changes found in any of the git repositories." in result

    @pytest.mark.asyncio
    @patch("tools.precommit.Precommit.execute")
    async def test_execute_integration(self, mock_execute, tool):
        """Test execute method integration"""
        # Mock the execute to return a standardized response
        mock_execute.return_value = [
            Mock(text='{"status": "success", "content": "Review complete", "content_type": "text"}')
        ]

        result = await tool.execute({"path": ".", "review_type": "full"})

        assert len(result) == 1
        mock_execute.assert_called_once()

    def test_default_temperature(self, tool):
        """Test default temperature setting"""
        from config import TEMPERATURE_ANALYTICAL

        assert tool.get_default_temperature() == TEMPERATURE_ANALYTICAL

    @pytest.mark.asyncio
    @patch("tools.precommit.find_git_repositories")
    @patch("tools.precommit.get_git_status")
    @patch("tools.precommit.run_git_command")
    async def test_mixed_staged_unstaged_changes(
        self,
        mock_run_git,
        mock_status,
        mock_find_repos,
        tool,
    ):
        """Test reviewing both staged and unstaged changes"""
        mock_find_repos.return_value = ["/test/repo"]
        mock_status.return_value = {
            "branch": "develop",
            "ahead": 2,
            "behind": 1,
            "staged_files": ["file1.py"],
            "unstaged_files": ["file2.py"],
            "untracked_files": [],
        }

        # Mock git commands
        mock_run_git.side_effect = [
            (True, "file1.py\n"),  # staged files
            (True, "diff --git a/file1.py..."),  # diff for file1.py
            (True, "file2.py\n"),  # unstaged files
            (True, "diff --git a/file2.py..."),  # diff for file2.py
        ]

        request = PrecommitRequest(
            path="/absolute/repo/path",
            focus_on="error handling",
            severity_filter="high",
        )
        result = await tool.prepare_prompt(request)

        # Verify all sections are present
        assert "Review Type: full" in result
        assert "Severity Filter: high" in result
        assert "Focus Areas: error handling" in result
        assert "Reviewing: staged and unstaged changes" in result

    @pytest.mark.asyncio
    @patch("tools.precommit.find_git_repositories")
    @patch("tools.precommit.get_git_status")
    @patch("tools.precommit.run_git_command")
    async def test_files_parameter_with_context(
        self,
        mock_run_git,
        mock_status,
        mock_find_repos,
        tool,
    ):
        """Test review with additional context files"""
        mock_find_repos.return_value = ["/test/repo"]
        mock_status.return_value = {
            "branch": "main",
            "ahead": 0,
            "behind": 0,
            "staged_files": ["file1.py"],
            "unstaged_files": [],
            "untracked_files": [],
        }

        # Mock git commands - need to match all calls in prepare_prompt
        mock_run_git.side_effect = [
            (True, "file1.py\n"),  # staged files list
            (True, "diff --git a/file1.py..."),  # diff for file1.py
            (True, ""),  # unstaged files list (empty)
        ]

        # Mock the centralized file preparation method
        with patch.object(tool, "_prepare_file_content_for_prompt") as mock_prepare_files:
            mock_prepare_files.return_value = (
                "=== FILE: config.py ===\nCONFIG_VALUE = 42\n=== END FILE ===",
                ["/test/path/config.py"],
            )

            request = PrecommitRequest(
                path="/absolute/repo/path",
                files=["/absolute/repo/path/config.py"],
            )
            result = await tool.prepare_prompt(request)

        # Verify context files are included
        assert "## Context Files Summary" in result
        assert "✅ Included: 1 context files" in result
        assert "## Additional Context Files" in result
        assert "=== FILE: config.py ===" in result
        assert "CONFIG_VALUE = 42" in result

    @pytest.mark.asyncio
    @patch("tools.precommit.find_git_repositories")
    @patch("tools.precommit.get_git_status")
    @patch("tools.precommit.run_git_command")
    async def test_files_request_instruction(
        self,
        mock_run_git,
        mock_status,
        mock_find_repos,
        tool,
    ):
        """Test that file request instruction is added when no files provided"""
        mock_find_repos.return_value = ["/test/repo"]
        mock_status.return_value = {
            "branch": "main",
            "ahead": 0,
            "behind": 0,
            "staged_files": ["file1.py"],
            "unstaged_files": [],
            "untracked_files": [],
        }

        mock_run_git.side_effect = [
            (True, "file1.py\n"),  # staged files
            (True, "diff --git a/file1.py..."),  # diff for file1.py
            (True, ""),  # unstaged files (empty)
        ]

        # Request without files
        request = PrecommitRequest(path="/absolute/repo/path")
        result = await tool.prepare_prompt(request)

        # Should include instruction for requesting files
        assert "If you need additional context files" in result
        assert "standardized JSON response format" in result

        # Request with files - should not include instruction
        request_with_files = PrecommitRequest(path="/absolute/repo/path", files=["/some/file.py"])

        # Need to reset mocks for second call
        mock_find_repos.return_value = ["/test/repo"]
        mock_run_git.side_effect = [
            (True, "file1.py\n"),  # staged files
            (True, "diff --git a/file1.py..."),  # diff for file1.py
            (True, ""),  # unstaged files (empty)
        ]

        # Mock the centralized file preparation method to return empty (file not found)
        with patch.object(tool, "_prepare_file_content_for_prompt") as mock_prepare_files:
            mock_prepare_files.return_value = ("", [])
            result_with_files = await tool.prepare_prompt(request_with_files)

        assert "If you need additional context files" not in result_with_files
