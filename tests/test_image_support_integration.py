"""
Integration tests for native image support feature.

Tests the complete image support pipeline:
- Conversation memory integration with images
- Tool request validation and schema support
- Provider image processing capabilities
- Cross-tool image context preservation
"""

import os
import tempfile
import uuid
from unittest.mock import Mock, patch

import pytest

from tools.chat import ChatTool
from tools.debug import DebugIssueTool
from tools.shared.exceptions import ToolExecutionError
from utils.conversation_memory import (
    ConversationTurn,
    ThreadContext,
    add_turn,
    create_thread,
    get_conversation_image_list,
    get_thread,
)
from utils.model_context import ModelContext


@pytest.mark.no_mock_provider
class TestImageSupportIntegration:
    """Integration tests for the complete image support feature."""

    def test_conversation_turn_includes_images(self):
        """Test that ConversationTurn can store and track images."""
        turn = ConversationTurn(
            role="user",
            content="Please analyze this diagram",
            timestamp="2025-01-01T00:00:00Z",
            files=["code.py"],
            images=["diagram.png", "flowchart.jpg"],
            tool_name="chat",
        )

        assert turn.images == ["diagram.png", "flowchart.jpg"]
        assert turn.files == ["code.py"]
        assert turn.content == "Please analyze this diagram"

    def test_get_conversation_image_list_newest_first(self):
        """Test that image list prioritizes newest references."""
        # Create thread context with multiple turns
        context = ThreadContext(
            thread_id=str(uuid.uuid4()),
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:00:00Z",
            tool_name="chat",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Turn 1",
                    timestamp="2025-01-01T00:00:00Z",
                    images=["old_diagram.png", "shared.png"],
                ),
                ConversationTurn(
                    role="assistant", content="Turn 2", timestamp="2025-01-01T01:00:00Z", images=["middle.png"]
                ),
                ConversationTurn(
                    role="user",
                    content="Turn 3",
                    timestamp="2025-01-01T02:00:00Z",
                    images=["shared.png", "new_diagram.png"],  # shared.png appears again
                ),
            ],
            initial_context={},
        )

        image_list = get_conversation_image_list(context)

        # Should prioritize newest first, with duplicates removed (newest wins)
        expected = ["shared.png", "new_diagram.png", "middle.png", "old_diagram.png"]
        assert image_list == expected

    @patch("utils.conversation_memory.get_storage")
    def test_add_turn_with_images(self, mock_storage):
        """Test adding a conversation turn with images."""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Mock the Redis operations to return success
        mock_client.set.return_value = True

        thread_id = create_thread("test_tool", {"initial": "context"})

        # Set up initial thread context for add_turn to find
        initial_context = ThreadContext(
            thread_id=thread_id,
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:00:00Z",
            tool_name="test_tool",
            turns=[],  # Empty initially
            initial_context={"initial": "context"},
        )
        mock_client.get.return_value = initial_context.model_dump_json()

        success = add_turn(
            thread_id=thread_id,
            role="user",
            content="Analyze these screenshots",
            files=["app.py"],
            images=["screenshot1.png", "screenshot2.png"],
            tool_name="debug",
        )

        assert success

        # Mock thread context for get_thread call
        updated_context = ThreadContext(
            thread_id=thread_id,
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:00:00Z",
            tool_name="test_tool",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Analyze these screenshots",
                    timestamp="2025-01-01T00:00:00Z",
                    files=["app.py"],
                    images=["screenshot1.png", "screenshot2.png"],
                    tool_name="debug",
                )
            ],
            initial_context={"initial": "context"},
        )
        mock_client.get.return_value = updated_context.model_dump_json()

        # Retrieve and verify the thread
        context = get_thread(thread_id)
        assert context is not None
        assert len(context.turns) == 1

        turn = context.turns[0]
        assert turn.images == ["screenshot1.png", "screenshot2.png"]
        assert turn.files == ["app.py"]
        assert turn.content == "Analyze these screenshots"

    def test_chat_tool_schema_includes_images(self):
        """Test that ChatTool schema includes images field."""
        tool = ChatTool()
        schema = tool.get_input_schema()

        assert "images" in schema["properties"]
        images_field = schema["properties"]["images"]
        assert images_field["type"] == "array"
        assert images_field["items"]["type"] == "string"
        assert "visual context" in images_field["description"].lower()

    def test_debug_tool_schema_includes_images(self):
        """Test that DebugIssueTool schema includes images field."""
        tool = DebugIssueTool()
        schema = tool.get_input_schema()

        assert "images" in schema["properties"]
        images_field = schema["properties"]["images"]
        assert images_field["type"] == "array"
        assert images_field["items"]["type"] == "string"
        assert "screenshots" in images_field["description"].lower()

    def test_tool_image_validation_limits(self):
        """Test that tools validate image size limits using real provider resolution."""
        tool = ChatTool()

        # Create small test images (each 0.5MB, total 1MB)
        small_images = []
        for _ in range(2):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                # Write 0.5MB of data
                temp_file.write(b"\x00" * (512 * 1024))
                small_images.append(temp_file.name)

        try:
            # Test with an invalid model name that doesn't exist in any provider
            # Use model_context parameter name (not positional)
            result = tool._validate_image_limits(small_images, model_context=ModelContext("non-existent-model-12345"))
            # Should return error because model not available or doesn't support images
            assert result is not None
            assert result["status"] == "error"
            assert "is not available" in result["content"] or "does not support image processing" in result["content"]

            # Test that empty/None images always pass regardless of model
            result = tool._validate_image_limits([], model_context=ModelContext("gemini-2.5-pro"))
            assert result is None

            result = tool._validate_image_limits(None, model_context=ModelContext("gemini-2.5-pro"))
            assert result is None

        finally:
            # Clean up temp files
            for img_path in small_images:
                if os.path.exists(img_path):
                    os.unlink(img_path)

    def test_image_validation_model_specific_limits(self):
        """Test that different models have appropriate size limits using real provider resolution."""
        tool = ChatTool()

        # Test with Gemini model which has better image support in test environment
        # Create 15MB image (under default limits)
        small_image_path = None
        large_image_path = None

        try:
            # Create 15MB image
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_file.write(b"\x00" * (15 * 1024 * 1024))  # 15MB
                small_image_path = temp_file.name

            # Test with the default model from test environment (gemini-2.5-flash)
            result = tool._validate_image_limits([small_image_path], ModelContext("gemini-2.5-flash"))
            assert result is None  # Should pass for Gemini models

            # Create 150MB image (over typical limits)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_file.write(b"\x00" * (150 * 1024 * 1024))  # 150MB
                large_image_path = temp_file.name

            result = tool._validate_image_limits([large_image_path], ModelContext("gemini-2.5-flash"))
            # Large images should fail validation
            assert result is not None
            assert result["status"] == "error"
            assert "Image size limit exceeded" in result["content"]

        finally:
            # Clean up temp files
            if small_image_path and os.path.exists(small_image_path):
                os.unlink(small_image_path)
            if large_image_path and os.path.exists(large_image_path):
                os.unlink(large_image_path)

    @pytest.mark.asyncio
    async def test_chat_tool_execution_with_images(self):
        """Test that ChatTool can execute with images parameter using real provider resolution."""
        import importlib

        # Create a temporary image file for testing
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            # Write a simple PNG header (minimal valid PNG)
            png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
            temp_file.write(png_header)
            temp_image_path = temp_file.name

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for real provider resolution
            os.environ["OPENAI_API_KEY"] = "sk-test-key-images-test-not-real"
            os.environ["DEFAULT_MODEL"] = "gpt-4o"

            # Clear other provider keys to isolate to OpenAI
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            tool = ChatTool()

            # Test with real provider resolution
            with tempfile.TemporaryDirectory() as working_directory:
                with pytest.raises(ToolExecutionError) as exc_info:
                    await tool.execute(
                        {
                            "prompt": "What do you see in this image?",
                            "images": [temp_image_path],
                            "model": "gpt-4o",
                            "working_directory_absolute_path": working_directory,
                        }
                    )

            error_msg = exc_info.value.payload if hasattr(exc_info.value, "payload") else str(exc_info.value)

            # Should NOT be a mock-related error
            assert "MagicMock" not in error_msg
            assert "'<' not supported between instances" not in error_msg

            # Should be a real provider error (API key or network)
            assert any(
                phrase in error_msg
                for phrase in ["API", "key", "authentication", "provider", "network", "connection", "401", "403"]
            )

        finally:
            # Clean up temp file
            os.unlink(temp_image_path)

            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None

    @patch("utils.conversation_memory.get_storage")
    def test_cross_tool_image_context_preservation(self, mock_storage):
        """Test that images are preserved across different tools in conversation."""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Mock the Redis operations to return success
        mock_client.set.return_value = True

        # Create initial thread with chat tool
        thread_id = create_thread("chat", {"initial": "context"})

        # Set up initial thread context for add_turn to find
        initial_context = ThreadContext(
            thread_id=thread_id,
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:00:00Z",
            tool_name="chat",
            turns=[],  # Empty initially
            initial_context={"initial": "context"},
        )
        mock_client.get.return_value = initial_context.model_dump_json()

        # Add turn with images from chat tool
        add_turn(
            thread_id=thread_id,
            role="user",
            content="Here's my UI design",
            images=["design.png", "mockup.jpg"],
            tool_name="chat",
        )

        add_turn(
            thread_id=thread_id, role="assistant", content="I can see your design. It looks good!", tool_name="chat"
        )

        # Add turn with different images from debug tool
        add_turn(
            thread_id=thread_id,
            role="user",
            content="Now I'm getting this error",
            images=["error_screen.png"],
            files=["error.log"],
            tool_name="debug",
        )

        # Mock complete thread context for get_thread call
        complete_context = ThreadContext(
            thread_id=thread_id,
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:05:00Z",
            tool_name="chat",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Here's my UI design",
                    timestamp="2025-01-01T00:01:00Z",
                    images=["design.png", "mockup.jpg"],
                    tool_name="chat",
                ),
                ConversationTurn(
                    role="assistant",
                    content="I can see your design. It looks good!",
                    timestamp="2025-01-01T00:02:00Z",
                    tool_name="chat",
                ),
                ConversationTurn(
                    role="user",
                    content="Now I'm getting this error",
                    timestamp="2025-01-01T00:03:00Z",
                    images=["error_screen.png"],
                    files=["error.log"],
                    tool_name="debug",
                ),
            ],
            initial_context={"initial": "context"},
        )
        mock_client.get.return_value = complete_context.model_dump_json()

        # Retrieve thread and check image preservation
        context = get_thread(thread_id)
        assert context is not None

        # Get conversation image list (should prioritize newest first)
        image_list = get_conversation_image_list(context)
        expected = ["error_screen.png", "design.png", "mockup.jpg"]
        assert image_list == expected

        # Verify each turn has correct images
        assert context.turns[0].images == ["design.png", "mockup.jpg"]
        assert context.turns[1].images is None  # Assistant turn without images
        assert context.turns[2].images == ["error_screen.png"]

    def test_tool_request_base_class_has_images(self):
        """Test that base ToolRequest class includes images field."""
        from tools.shared.base_models import ToolRequest

        # Create request with images
        request = ToolRequest(images=["test.png", "test2.jpg"])
        assert request.images == ["test.png", "test2.jpg"]

        # Test default value
        request_no_images = ToolRequest()
        assert request_no_images.images is None

    def test_data_url_image_format_support(self):
        """Test that tools can handle data URL format images."""
        tool = ChatTool()

        # Test with data URL (base64 encoded 1x1 transparent PNG)
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        images = [data_url]

        # Test with a dummy model that doesn't exist in any provider
        result = tool._validate_image_limits(images, ModelContext("test-dummy-model-name"))
        # Should return error because model not available or doesn't support images
        assert result is not None
        assert result["status"] == "error"
        assert "is not available" in result["content"] or "does not support image processing" in result["content"]

        # Test with another non-existent model to check error handling
        result = tool._validate_image_limits(images, ModelContext("another-dummy-model"))
        # Should return error because model not available
        assert result is not None
        assert result["status"] == "error"

    def test_empty_images_handling(self):
        """Test that tools handle empty images lists gracefully."""
        tool = ChatTool()

        # Empty list should not fail validation (no need for provider setup)
        result = tool._validate_image_limits([], ModelContext("gemini-2.5-pro"))
        assert result is None

        # None should not fail validation (no need for provider setup)
        result = tool._validate_image_limits(None, ModelContext("gemini-2.5-pro"))
        assert result is None

    @patch("utils.conversation_memory.get_storage")
    def test_conversation_memory_thread_chaining_with_images(self, mock_storage):
        """Test that images work correctly with conversation thread chaining."""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        # Mock the Redis operations to return success
        mock_client.set.return_value = True

        # Create parent thread with images
        parent_thread_id = create_thread("chat", {"parent": "context"})

        # Set up initial parent thread context for add_turn to find
        parent_context = ThreadContext(
            thread_id=parent_thread_id,
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:00:00Z",
            tool_name="chat",
            turns=[],  # Empty initially
            initial_context={"parent": "context"},
        )
        mock_client.get.return_value = parent_context.model_dump_json()
        add_turn(
            thread_id=parent_thread_id,
            role="user",
            content="Parent thread with images",
            images=["parent1.png", "shared.png"],
            tool_name="chat",
        )

        # Create child thread linked to parent using a simple tool
        child_thread_id = create_thread("chat", {"prompt": "child context"}, parent_thread_id=parent_thread_id)
        add_turn(
            thread_id=child_thread_id,
            role="user",
            content="Child thread with more images",
            images=["child1.png", "shared.png"],  # shared.png appears again (should prioritize newer)
            tool_name="chat",
        )

        # Mock child thread context for get_thread call
        child_context = ThreadContext(
            thread_id=child_thread_id,
            created_at="2025-01-01T00:00:00Z",
            last_updated_at="2025-01-01T00:02:00Z",
            tool_name="debug",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Child thread with more images",
                    timestamp="2025-01-01T00:02:00Z",
                    images=["child1.png", "shared.png"],
                    tool_name="debug",
                )
            ],
            initial_context={"child": "context"},
            parent_thread_id=parent_thread_id,
        )
        mock_client.get.return_value = child_context.model_dump_json()

        # Get child thread and verify image collection works across chain
        child_context = get_thread(child_thread_id)
        assert child_context is not None
        assert child_context.parent_thread_id == parent_thread_id

        # Test image collection for child thread only
        child_images = get_conversation_image_list(child_context)
        assert child_images == ["child1.png", "shared.png"]
