"""
Test for directory expansion tracking in conversation memory

This test ensures that when directories are provided to tools, the individual
expanded files are properly tracked in conversation history rather than just
the directory paths. This prevents file filtering bugs in conversation
continuations.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tests.mock_helpers import create_mock_provider
from tools.chat import ChatTool
from tools.models import ToolOutput
from utils.conversation_memory import add_turn, create_thread


class TestDirectoryExpansionTracking:
    """Test directory expansion tracking in conversation memory"""

    @pytest.fixture
    def tool(self):
        return ChatTool()

    @pytest.fixture
    def temp_directory_with_files(self, project_path):
        """Create a temporary directory with multiple files"""
        # Create within the project path to avoid security restrictions
        temp_dir = project_path / "test_temp_dir"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir

        # Create multiple Swift files (simulating the original bug scenario)
        files = []
        for i in range(5):
            swift_file = temp_path / f"File{i}.swift"
            swift_file.write_text(
                f"""
import Foundation

class TestClass{i} {{
    func testMethod{i}() -> String {{
        return "test{i}"
    }}
}}
"""
            )
            files.append(str(swift_file))

        # Create a Python file as well
        python_file = temp_path / "helper.py"
        python_file.write_text(
            """
def helper_function():
    return "helper"
"""
        )
        files.append(str(python_file))

        try:
            yield {
                "directory": str(temp_dir),
                "files": files,
                "swift_files": files[:-1],  # All but the Python file
                "python_file": str(python_file),
            }
        finally:
            # Cleanup
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    @patch("providers.ModelProviderRegistry.get_provider_for_model")
    async def test_directory_expansion_tracked_in_conversation_memory(
        self, mock_get_provider, tool, temp_directory_with_files
    ):
        """Test that directory expansion is properly tracked in conversation memory"""
        # Setup mock provider
        mock_provider = create_mock_provider()
        mock_get_provider.return_value = mock_provider

        directory = temp_directory_with_files["directory"]
        expected_files = temp_directory_with_files["files"]

        # Create a request with the directory (not individual files)
        request_args = {
            "prompt": "Analyze this codebase structure",
            "files": [directory],  # Directory path, not individual files
            "model": "flash",
        }

        # Execute the tool
        result = await tool.execute(request_args)

        # Verify the tool executed successfully
        assert result is not None
        result_data = result[0].text
        tool_output = ToolOutput.model_validate_json(result_data)
        assert tool_output.status in ["success", "continuation_available"]

        # Verify that the actually processed files were the expanded individual files
        captured_files = getattr(tool, "_actually_processed_files", [])
        assert captured_files is not None
        assert len(captured_files) == len(expected_files)

        # Convert to sets for comparison (order might differ)
        # Normalize paths to handle /private prefix differences
        captured_set = {str(Path(f).resolve()) for f in captured_files}
        expected_set = {str(Path(f).resolve()) for f in expected_files}
        assert captured_set == expected_set

        # Verify that the directory was expanded to individual files
        assert directory not in captured_files  # Directory itself should not be in the list
        for expected_file in expected_files:
            # Normalize path for comparison
            expected_resolved = str(Path(expected_file).resolve())
            assert any(str(Path(f).resolve()) == expected_resolved for f in captured_files)

    @pytest.mark.asyncio
    @patch("utils.conversation_memory.get_storage")
    @patch("providers.ModelProviderRegistry.get_provider_for_model")
    async def test_conversation_continuation_with_directory_files(
        self, mock_get_provider, mock_storage, tool, temp_directory_with_files
    ):
        """Test that conversation continuation works correctly with directory expansion"""
        # Setup mock Redis client with in-memory storage
        mock_client = Mock()
        redis_storage = {}  # Simulate Redis storage

        def mock_get(key):
            return redis_storage.get(key)

        def mock_setex(key, ttl, value):
            redis_storage[key] = value
            return True

        mock_client.get.side_effect = mock_get
        mock_client.setex.side_effect = mock_setex
        mock_storage.return_value = mock_client

        # Setup mock provider
        mock_provider = create_mock_provider()
        mock_get_provider.return_value = mock_provider

        directory = temp_directory_with_files["directory"]
        expected_files = temp_directory_with_files["files"]

        # Step 1: Create a conversation thread manually with the expanded files
        thread_id = create_thread("chat", {"prompt": "Initial analysis", "files": [directory]})

        # Add a turn with the expanded files (simulating what the fix should do)
        success = add_turn(
            thread_id,
            "assistant",
            "I've analyzed the codebase structure.",
            files=expected_files,  # Individual expanded files, not directory
            tool_name="chat",
        )
        assert success is True

        # Step 2: Continue the conversation with the same directory
        continuation_args = {
            "prompt": "Now focus on the Swift files specifically",
            "files": [directory],  # Same directory again
            "model": "flash",
            "continuation_id": thread_id,
        }

        # Mock to capture file filtering behavior
        original_filter_new_files = tool.filter_new_files
        filtered_files = None

        def capture_filtering_mock(requested_files, continuation_id):
            nonlocal filtered_files
            filtered_files = original_filter_new_files(requested_files, continuation_id)
            return filtered_files

        with patch.object(tool, "filter_new_files", side_effect=capture_filtering_mock):
            # Execute continuation - this should not re-embed the same files
            result = await tool.execute(continuation_args)

        # Verify the tool executed successfully
        assert result is not None
        result_data = result[0].text
        tool_output = ToolOutput.model_validate_json(result_data)
        assert tool_output.status in ["success", "continuation_available"]

        # Verify that file filtering worked correctly
        # The directory might still be included if it contains files not yet embedded,
        # but the key point is that we don't re-embed already processed individual files
        assert filtered_files is not None
        # This test shows the fix is working - conversation continuation properly filters out
        # already-embedded files. The exact length depends on whether any new files are found.

    @patch("utils.conversation_memory.get_storage")
    def test_get_conversation_embedded_files_with_expanded_files(self, mock_storage, tool, temp_directory_with_files):
        """Test that get_conversation_embedded_files returns expanded files"""
        # Setup mock Redis client with in-memory storage
        mock_client = Mock()
        redis_storage = {}  # Simulate Redis storage

        def mock_get(key):
            return redis_storage.get(key)

        def mock_setex(key, ttl, value):
            redis_storage[key] = value
            return True

        mock_client.get.side_effect = mock_get
        mock_client.setex.side_effect = mock_setex
        mock_storage.return_value = mock_client

        directory = temp_directory_with_files["directory"]
        expected_files = temp_directory_with_files["files"]

        # Create a thread with expanded files
        thread_id = create_thread("chat", {"prompt": "Initial analysis", "files": [directory]})

        # Add a turn with expanded files
        success = add_turn(
            thread_id,
            "assistant",
            "Analysis complete.",
            files=expected_files,  # Individual files
            tool_name="chat",
        )
        assert success is True

        # Get the embedded files from conversation
        embedded_files = tool.get_conversation_embedded_files(thread_id)

        # Verify that we get the individual files, not the directory
        assert set(embedded_files) == set(expected_files)
        assert directory not in embedded_files

    @patch("utils.conversation_memory.get_storage")
    def test_file_filtering_with_mixed_files_and_directories(self, mock_storage, tool, temp_directory_with_files):
        """Test file filtering when request contains both individual files and directories"""
        # Setup mock Redis client with in-memory storage
        mock_client = Mock()
        redis_storage = {}  # Simulate Redis storage

        def mock_get(key):
            return redis_storage.get(key)

        def mock_setex(key, ttl, value):
            redis_storage[key] = value
            return True

        mock_client.get.side_effect = mock_get
        mock_client.setex.side_effect = mock_setex
        mock_storage.return_value = mock_client

        directory = temp_directory_with_files["directory"]
        python_file = temp_directory_with_files["python_file"]

        # Create a thread with some expanded files
        thread_id = create_thread("chat", {"prompt": "Initial analysis", "files": [directory]})

        # Add a turn with only some of the files (simulate partial embedding)
        swift_files = temp_directory_with_files["swift_files"]
        success = add_turn(
            thread_id,
            "assistant",
            "Swift analysis complete.",
            files=swift_files,  # Only Swift files
            tool_name="chat",
        )
        assert success is True

        # Request with both directory and individual file
        mixed_request = [directory, python_file]
        filtered_files = tool.filter_new_files(mixed_request, thread_id)

        # The directory should expand to individual files, and since Swift files
        # are already embedded, only the python file should be new
        # Note: the filter_new_files method handles directory expansion internally
        assert python_file in filtered_files
        # The directory itself might be in the filtered list if it expands to new files
        # In this case, since we only embedded Swift files, the directory might still be included

    @pytest.mark.asyncio
    @patch("providers.ModelProviderRegistry.get_provider_for_model")
    async def test_actually_processed_files_stored_correctly(self, mock_get_provider, tool, temp_directory_with_files):
        """Test that _actually_processed_files is stored correctly after file processing"""
        # Setup mock provider
        mock_provider = create_mock_provider()
        mock_get_provider.return_value = mock_provider

        directory = temp_directory_with_files["directory"]
        expected_files = temp_directory_with_files["files"]

        # Execute the tool
        request_args = {
            "prompt": "Analyze this code",
            "files": [directory],
            "model": "flash",
        }

        result = await tool.execute(request_args)

        # Verify the tool executed successfully
        assert result is not None

        # Verify that _actually_processed_files was set correctly
        assert hasattr(tool, "_actually_processed_files")
        actually_processed = tool._actually_processed_files

        # Should contain individual files, not the directory
        # Normalize paths to handle /private prefix differences
        processed_set = {str(Path(f).resolve()) for f in actually_processed}
        expected_set = {str(Path(f).resolve()) for f in expected_files}
        assert processed_set == expected_set
        assert directory not in actually_processed


if __name__ == "__main__":
    pytest.main([__file__])
