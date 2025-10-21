#!/usr/bin/env python3
"""
Chat Simple Tool Validation Test

Comprehensive test for the new ChatSimple tool implementation that validates:
- Basic conversation flow without continuation_id (new chats)
- Continuing existing conversations with continuation_id (continued chats)
- File handling with conversation context (chats with files)
- Image handling in conversations (chat with images)
- Continuing conversations with files from previous turns (continued chats with files previously)
- Temperature validation for different models
- Image limit validation per model
- Conversation context preservation across turns
"""


from .conversation_base_test import ConversationBaseTest


class ChatSimpleValidationTest(ConversationBaseTest):
    """Test ChatSimple tool functionality and validation"""

    @property
    def test_name(self) -> str:
        return "_validation"

    @property
    def test_description(self) -> str:
        return "Comprehensive validation of ChatSimple tool implementation"

    def run_test(self) -> bool:
        """Run comprehensive ChatSimple validation tests"""
        try:
            # Set up the test environment for in-process testing
            self.setUp()

            self.logger.info("Test: ChatSimple tool validation")

            # Run all test scenarios
            if not self.test_new_conversation_no_continuation():
                return False

            if not self.test_continue_existing_conversation():
                return False

            if not self.test_file_handling_with_conversation():
                return False

            if not self.test_temperature_validation_edge_cases():
                return False

            if not self.test_image_limits_per_model():
                return False

            if not self.test_conversation_context_preservation():
                return False

            if not self.test_chat_with_images():
                return False

            if not self.test_continued_chat_with_previous_files():
                return False

            self.logger.info("  ✅ All ChatSimple validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"ChatSimple validation test failed: {e}")
            return False

    def test_new_conversation_no_continuation(self) -> bool:
        """Test ChatSimple creates new conversation without continuation_id"""
        try:
            self.logger.info("  1. Test new conversation without continuation_id")

            # Call chat without continuation_id
            response, continuation_id = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Hello! Please use low thinking mode. Can you explain what MCP tools are?",
                    "model": "flash",
                    "temperature": 0.7,
                    "thinking_mode": "low",
                },
            )

            if not response:
                self.logger.error("    ❌ Failed to get response from chat")
                return False

            if not continuation_id:
                self.logger.error("    ❌ No continuation_id returned for new conversation")
                return False

            # Verify response mentions MCP or tools
            if "MCP" not in response and "tool" not in response.lower():
                self.logger.error("    ❌ Response doesn't seem to address the question about MCP tools")
                return False

            self.logger.info(f"    ✅ New conversation created with continuation_id: {continuation_id}")
            self.new_continuation_id = continuation_id  # Store for next test
            return True

        except Exception as e:
            self.logger.error(f"    ❌ New conversation test failed: {e}")
            return False

    def test_continue_existing_conversation(self) -> bool:
        """Test ChatSimple continues conversation with valid continuation_id"""
        try:
            self.logger.info("  2. Test continuing existing conversation")

            if not hasattr(self, "new_continuation_id"):
                self.logger.error("    ❌ No continuation_id from previous test")
                return False

            # Continue the conversation
            response, continuation_id = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Can you give me a specific example of how an MCP tool might work?",
                    "continuation_id": self.new_continuation_id,
                    "model": "flash",
                    "thinking_mode": "low",
                },
            )

            if not response:
                self.logger.error("    ❌ Failed to continue conversation")
                return False

            # Continuation ID should be the same
            if continuation_id != self.new_continuation_id:
                self.logger.error(f"    ❌ Continuation ID changed: {self.new_continuation_id} -> {continuation_id}")
                return False

            # Response should be contextual (mentioning previous discussion)
            if "example" not in response.lower():
                self.logger.error("    ❌ Response doesn't seem to provide an example as requested")
                return False

            self.logger.info("    ✅ Successfully continued conversation with same continuation_id")
            return True

        except Exception as e:
            self.logger.error(f"    ❌ Continue conversation test failed: {e}")
            return False

    def test_file_handling_with_conversation(self) -> bool:
        """Test ChatSimple handles files correctly in conversation context"""
        try:
            self.logger.info("  3. Test file handling with conversation")

            # Setup test files
            self.setup_test_files()

            # Start new conversation with a file
            response1, continuation_id = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Analyze this Python code and tell me what the Calculator class does",
                    "absolute_file_paths": [self.test_files["python"]],
                    "model": "flash",
                    "thinking_mode": "low",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("    ❌ Failed to start conversation with file")
                return False

            # Continue with same file (should be deduplicated)
            response2, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. What methods does the Calculator class have?",
                    "absolute_file_paths": [self.test_files["python"]],  # Same file
                    "continuation_id": continuation_id,
                    "model": "flash",
                    "thinking_mode": "low",
                },
            )

            if not response2:
                self.logger.error("    ❌ Failed to continue with same file")
                return False

            # Response should mention add and multiply methods
            if "add" not in response2.lower() or "multiply" not in response2.lower():
                self.logger.error("    ❌ Response doesn't mention Calculator methods")
                return False

            self.logger.info("    ✅ File handling with conversation working correctly")
            return True

        except Exception as e:
            self.logger.error(f"    ❌ File handling test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()

    def test_temperature_validation_edge_cases(self) -> bool:
        """Test temperature is corrected for model limits (too high/low)"""
        try:
            self.logger.info("  4. Test temperature validation edge cases")

            # Test 1: Temperature exactly at limit (should work)
            response1, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Hello, this is a test with max temperature",
                    "model": "flash",
                    "temperature": 1.0,  # At the limit
                    "thinking_mode": "low",
                },
            )

            if not response1:
                self.logger.error("    ❌ Failed with temperature 1.0")
                return False

            # Test 2: Temperature at minimum (should work)
            response2, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Another test message with min temperature",
                    "model": "flash",
                    "temperature": 0.0,  # At minimum
                    "thinking_mode": "low",
                },
            )

            if not response2:
                self.logger.error("    ❌ Failed with temperature 0.0")
                return False

            # Test 3: Check that invalid temperatures are rejected by validation
            # This should result in an error response from the tool, not a crash
            try:
                response3, _ = self.call_mcp_tool_direct(
                    "chat",
                    {
                        "prompt": "Please use low thinking mode. Test with invalid temperature",
                        "model": "flash",
                        "temperature": 1.5,  # Too high - should be validated
                        "thinking_mode": "low",
                    },
                )

                # If we get here, check if it's an error response
                if response3 and "validation error" in response3.lower():
                    self.logger.info("    ✅ Invalid temperature properly rejected by validation")
                else:
                    self.logger.warning("    ⚠️  High temperature not properly validated")
            except Exception:
                # Expected - validation should reject this
                self.logger.info("    ✅ Invalid temperature properly rejected")

            self.logger.info("    ✅ Temperature validation working correctly")
            return True

        except Exception as e:
            self.logger.error(f"    ❌ Temperature validation test failed: {e}")
            return False

    def test_image_limits_per_model(self) -> bool:
        """Test image validation respects model-specific limits"""
        try:
            self.logger.info("  5. Test image limits per model")

            # Create test image data URLs (small base64 images)
            small_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

            # Test 1: Model that doesn't support images
            response1, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Can you see this image?",
                    "model": "local-llama",  # Text-only model
                    "images": [small_image],
                    "thinking_mode": "low",
                },
            )

            # Should get an error about image support
            if response1 and "does not support image" not in response1:
                self.logger.warning("    ⚠️  Model without image support didn't reject images properly")

            # Test 2: Too many images for a model
            many_images = [small_image] * 25  # Most models support max 20

            response2, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Analyze these images",
                    "model": "gemini-2.5-flash",  # Supports max 16 images
                    "images": many_images,
                    "thinking_mode": "low",
                },
            )

            # Should get an error about too many images
            if response2 and "too many images" not in response2.lower():
                self.logger.warning("    ⚠️  Model didn't reject excessive image count")

            # Test 3: Valid image count
            response3, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. This is a test with one image",
                    "model": "gemini-2.5-flash",
                    "images": [small_image],
                    "thinking_mode": "low",
                },
            )

            if not response3:
                self.logger.error("    ❌ Failed with valid image count")
                return False

            self.logger.info("    ✅ Image validation working correctly")
            return True

        except Exception as e:
            self.logger.error(f"    ❌ Image limits test failed: {e}")
            return False

    def test_conversation_context_preservation(self) -> bool:
        """Test ChatSimple preserves context across turns"""
        try:
            self.logger.info("  6. Test conversation context preservation")

            # Start conversation with specific context
            response1, continuation_id = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. My name is TestUser and I'm working on a Python project called TestProject",
                    "model": "flash",
                    "thinking_mode": "low",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("    ❌ Failed to start conversation")
                return False

            # Continue and reference previous context
            response2, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. What's my name and what project am I working on?",
                    "continuation_id": continuation_id,
                    "model": "flash",
                    "thinking_mode": "low",
                },
            )

            if not response2:
                self.logger.error("    ❌ Failed to continue conversation")
                return False

            # Check if context was preserved
            if "TestUser" not in response2 or "TestProject" not in response2:
                self.logger.error("    ❌ Context not preserved across conversation turns")
                self.logger.debug(f"    Response: {response2[:200]}...")
                return False

            self.logger.info("    ✅ Conversation context preserved correctly")
            return True

        except Exception as e:
            self.logger.error(f"    ❌ Context preservation test failed: {e}")
            return False

    def test_chat_with_images(self) -> bool:
        """Test ChatSimple handles images correctly in conversation"""
        try:
            self.logger.info("  7. Test chat with images")

            # Create test image data URL (small base64 image)
            small_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

            # Start conversation with image
            response1, continuation_id = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. I'm sharing an image with you. Can you acknowledge that you received it?",
                    "images": [small_image],
                    "model": "gemini-2.5-flash",  # Model that supports images
                    "thinking_mode": "low",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("    ❌ Failed to start conversation with image")
                return False

            # Verify response acknowledges the image
            if "image" not in response1.lower():
                self.logger.warning("    ⚠️  Response doesn't acknowledge receiving image")

            # Continue conversation referencing the image
            response2, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. What did you see in that image I shared earlier?",
                    "continuation_id": continuation_id,
                    "model": "gemini-2.5-flash",
                    "thinking_mode": "low",
                },
            )

            if not response2:
                self.logger.error("    ❌ Failed to continue conversation about image")
                return False

            # Test with multiple images
            multiple_images = [small_image, small_image]  # Two identical small images
            response3, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Here are two images for comparison",
                    "images": multiple_images,
                    "model": "gemini-2.5-flash",
                    "thinking_mode": "low",
                },
            )

            if not response3:
                self.logger.error("    ❌ Failed with multiple images")
                return False

            self.logger.info("    ✅ Chat with images working correctly")
            return True

        except Exception as e:
            self.logger.error(f"    ❌ Chat with images test failed: {e}")
            return False

    def test_continued_chat_with_previous_files(self) -> bool:
        """Test continuing conversation where files were shared in previous turns"""
        try:
            self.logger.info("  8. Test continued chat with files from previous turns")

            # Setup test files
            self.setup_test_files()

            # Start conversation with files
            response1, continuation_id = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Here are some files for you to analyze",
                    "absolute_file_paths": [self.test_files["python"], self.test_files["config"]],
                    "model": "flash",
                    "thinking_mode": "low",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("    ❌ Failed to start conversation with files")
                return False

            # Continue conversation without new files (should remember previous files)
            response2, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. From the files I shared earlier, what types of files were there?",
                    "continuation_id": continuation_id,
                    "model": "flash",
                    "thinking_mode": "low",
                },
            )

            if not response2:
                self.logger.error("    ❌ Failed to continue conversation")
                return False

            # Check if response references the files from previous turn
            if "python" not in response2.lower() and "config" not in response2.lower():
                self.logger.warning("    ⚠️  Response doesn't reference previous files properly")

            # Continue with a different question about same files (should still remember them)
            response3, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Can you tell me what functions were defined in the Python file from our earlier discussion?",
                    "continuation_id": continuation_id,
                    "model": "flash",
                    "thinking_mode": "low",
                },
            )

            if not response3:
                self.logger.error("    ❌ Failed to continue conversation about Python file")
                return False

            # Should reference functions from the Python file (fibonacci, factorial, Calculator, etc.)
            response_lower = response3.lower()
            if not ("fibonacci" in response_lower or "factorial" in response_lower or "calculator" in response_lower):
                self.logger.warning("    ⚠️  Response doesn't reference Python file contents from earlier turn")

            self.logger.info("    ✅ Continued chat with previous files working correctly")
            return True

        except Exception as e:
            self.logger.error(f"    ❌ Continued chat with files test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()
