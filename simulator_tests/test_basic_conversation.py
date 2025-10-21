#!/usr/bin/env python3
"""
Basic Conversation Flow Test

Tests basic conversation continuity with the chat tool, including:
- Initial chat with file analysis
- Continuing conversation with same file (deduplication)
- Adding additional files to ongoing conversation
"""

from .base_test import BaseSimulatorTest


class BasicConversationTest(BaseSimulatorTest):
    """Test basic conversation flow with chat tool"""

    @property
    def test_name(self) -> str:
        return "basic_conversation"

    @property
    def test_description(self) -> str:
        return "Basic conversation flow with chat tool"

    def run_test(self) -> bool:
        """Test basic conversation flow with chat tool"""
        try:
            self.logger.info("Test: Basic conversation flow")

            # Setup test files
            self.setup_test_files()

            # Initial chat tool call with file
            self.logger.info("  1.1: Initial chat with file analysis")
            response1, continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Analyze this Python code and explain what it does",
                    "absolute_file_paths": [self.test_files["python"]],
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to get initial response with continuation_id")
                return False

            self.logger.info(f"  ✅ Got continuation_id: {continuation_id}")

            # Continue conversation with same file (should be deduplicated)
            self.logger.info("  1.2: Continue conversation with same file")
            response2, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Now focus on the Calculator class specifically. Are there any improvements you'd suggest?",
                    "absolute_file_paths": [self.test_files["python"]],  # Same file - should be deduplicated
                    "continuation_id": continuation_id,
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to continue conversation")
                return False

            # Continue with additional file
            self.logger.info("  1.3: Continue conversation with additional file")
            response3, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Now also analyze this configuration file and see how it might relate to the Python code",
                    "absolute_file_paths": [self.test_files["python"], self.test_files["config"]],
                    "continuation_id": continuation_id,
                    "model": "flash",
                },
            )

            if not response3:
                self.logger.error("Failed to continue with additional file")
                return False

            self.logger.info("  ✅ Basic conversation flow working")
            return True

        except Exception as e:
            self.logger.error(f"Basic conversation flow test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()
