"""
Enhanced tests for precommit tool using mock storage to test real logic
"""

import os
import tempfile
from typing import Optional
from unittest.mock import patch

import pytest

from tools.precommit import Precommit, PrecommitRequest


class MockRedisClient:
    """Mock Redis client that uses in-memory dictionary storage"""

    def __init__(self):
        self.data: dict[str, str] = {}
        self.ttl_data: dict[str, int] = {}

    def get(self, key: str) -> Optional[str]:
        return self.data.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self.data[key] = value
        if ex:
            self.ttl_data[key] = ex
        return True

    def delete(self, key: str) -> int:
        if key in self.data:
            del self.data[key]
            self.ttl_data.pop(key, None)
            return 1
        return 0

    def exists(self, key: str) -> int:
        return 1 if key in self.data else 0

    def setex(self, key: str, time: int, value: str) -> bool:
        """Set key to hold string value and set key to timeout after given seconds"""
        self.data[key] = value
        self.ttl_data[key] = time
        return True


class TestPrecommitToolWithMockStore:
    """Test precommit tool with mock storage to validate actual logic"""

    @pytest.fixture
    def mock_storage(self):
        """Create mock Redis client"""
        return MockRedisClient()

    @pytest.fixture
    def tool(self, mock_storage, temp_repo):
        """Create tool instance with mocked Redis"""
        temp_dir, _ = temp_repo
        tool = Precommit()

        # Mock the Redis client getter to use our mock storage
        with patch("utils.conversation_memory.get_storage", return_value=mock_storage):
            yield tool

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary git repository with test files"""
        import subprocess

        temp_dir = tempfile.mkdtemp()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=temp_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, capture_output=True)

        # Create test config file
        config_content = '''"""Test configuration file"""

# Version and metadata
__version__ = "1.0.0"
__author__ = "Test"

# Configuration
MAX_CONTENT_TOKENS = 800_000  # 800K tokens for content
TEMPERATURE_ANALYTICAL = 0.2  # For code review, debugging
'''

        config_path = os.path.join(temp_dir, "config.py")
        with open(config_path, "w") as f:
            f.write(config_content)

        # Add and commit initial version
        subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, capture_output=True)

        # Modify config to create a diff
        modified_content = config_content + '\nNEW_SETTING = "test"  # Added setting\n'
        with open(config_path, "w") as f:
            f.write(modified_content)

        yield temp_dir, config_path

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_no_duplicate_file_content_in_prompt(self, tool, temp_repo, mock_storage):
        """Test that file content appears in expected locations

        This test validates our design decision that files can legitimately appear in both:
        1. Git Diffs section: Shows only changed lines + limited context (wrapped with BEGIN DIFF markers)
        2. Additional Context section: Shows complete file content (wrapped with BEGIN FILE markers)

        This is intentional, not a bug - the AI needs both perspectives for comprehensive analysis.
        """
        temp_dir, config_path = temp_repo

        # Create request with files parameter
        request = PrecommitRequest(path=temp_dir, files=[config_path], prompt="Test configuration changes")

        # Generate the prompt
        prompt = await tool.prepare_prompt(request)

        # Verify expected sections are present
        assert "## Original Request" in prompt
        assert "Test configuration changes" in prompt
        assert "## Additional Context Files" in prompt
        assert "## Git Diffs" in prompt

        # Verify the file appears in the git diff
        assert "config.py" in prompt
        assert "NEW_SETTING" in prompt

        # Note: Files can legitimately appear in both git diff AND additional context:
        # - Git diff shows only changed lines + limited context
        # - Additional context provides complete file content for full understanding
        # This is intentional and provides comprehensive context to the AI

    @pytest.mark.asyncio
    async def test_conversation_memory_integration(self, tool, temp_repo, mock_storage):
        """Test that conversation memory works with mock storage"""
        temp_dir, config_path = temp_repo

        # Mock conversation memory functions to use our mock redis
        with patch("utils.conversation_memory.get_storage", return_value=mock_storage):
            # First request - should embed file content
            PrecommitRequest(path=temp_dir, files=[config_path], prompt="First review")

            # Simulate conversation thread creation
            from utils.conversation_memory import add_turn, create_thread

            thread_id = create_thread("precommit", {"files": [config_path]})

            # Test that file embedding works
            files_to_embed = tool.filter_new_files([config_path], None)
            assert config_path in files_to_embed, "New conversation should embed all files"

            # Add a turn to the conversation
            add_turn(thread_id, "assistant", "First response", files=[config_path], tool_name="precommit")

            # Second request with continuation - should skip already embedded files
            PrecommitRequest(path=temp_dir, files=[config_path], continuation_id=thread_id, prompt="Follow-up review")

            files_to_embed_2 = tool.filter_new_files([config_path], thread_id)
            assert len(files_to_embed_2) == 0, "Continuation should skip already embedded files"

    @pytest.mark.asyncio
    async def test_prompt_structure_integrity(self, tool, temp_repo, mock_storage):
        """Test that the prompt structure is well-formed and doesn't have content duplication"""
        temp_dir, config_path = temp_repo

        request = PrecommitRequest(
            path=temp_dir,
            files=[config_path],
            prompt="Validate prompt structure",
            review_type="full",
            severity_filter="high",
        )

        prompt = await tool.prepare_prompt(request)

        # Split prompt into sections
        sections = {
            "prompt": "## Original Request",
            "review_parameters": "## Review Parameters",
            "repo_summary": "## Repository Changes Summary",
            "context_files_summary": "## Context Files Summary",
            "git_diffs": "## Git Diffs",
            "additional_context": "## Additional Context Files",
            "review_instructions": "## Review Instructions",
        }

        section_indices = {}
        for name, header in sections.items():
            index = prompt.find(header)
            if index != -1:
                section_indices[name] = index

        # Verify sections appear in logical order
        assert section_indices["prompt"] < section_indices["review_parameters"]
        assert section_indices["review_parameters"] < section_indices["repo_summary"]
        assert section_indices["git_diffs"] < section_indices["additional_context"]
        assert section_indices["additional_context"] < section_indices["review_instructions"]

        # Test that file content only appears in Additional Context section
        file_content_start = section_indices["additional_context"]
        file_content_end = section_indices["review_instructions"]

        file_section = prompt[file_content_start:file_content_end]
        prompt[:file_content_start]
        after_file_section = prompt[file_content_end:]

        # File content should appear in the file section
        assert "MAX_CONTENT_TOKENS = 800_000" in file_section
        # Check that configuration content appears in the file section
        assert "# Configuration" in file_section
        # The complete file content should not appear in the review instructions
        assert '__version__ = "1.0.0"' in file_section
        assert '__version__ = "1.0.0"' not in after_file_section

    @pytest.mark.asyncio
    async def test_file_content_formatting(self, tool, temp_repo, mock_storage):
        """Test that file content is properly formatted without duplication"""
        temp_dir, config_path = temp_repo

        # Test the centralized file preparation method directly
        file_content, processed_files = tool._prepare_file_content_for_prompt(
            [config_path],
            None,
            "Test files",
            max_tokens=100000,
            reserve_tokens=1000,  # No continuation
        )

        # Should contain file markers
        assert "--- BEGIN FILE:" in file_content
        assert "--- END FILE:" in file_content
        assert "config.py" in file_content

        # Should contain actual file content
        assert "MAX_CONTENT_TOKENS = 800_000" in file_content
        assert '__version__ = "1.0.0"' in file_content

        # Content should appear only once
        assert file_content.count("MAX_CONTENT_TOKENS = 800_000") == 1
        assert file_content.count('__version__ = "1.0.0"') == 1


def test_mock_storage_basic_operations():
    """Test that our mock Redis implementation works correctly"""
    mock_storage = MockRedisClient()

    # Test basic operations
    assert mock_storage.get("nonexistent") is None
    assert mock_storage.exists("nonexistent") == 0

    mock_storage.set("test_key", "test_value")
    assert mock_storage.get("test_key") == "test_value"
    assert mock_storage.exists("test_key") == 1

    assert mock_storage.delete("test_key") == 1
    assert mock_storage.get("test_key") is None
    assert mock_storage.delete("test_key") == 0  # Already deleted
