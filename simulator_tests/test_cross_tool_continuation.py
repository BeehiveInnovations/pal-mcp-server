#!/usr/bin/env python3
"""
Cross-Tool Continuation Test

Tests comprehensive cross-tool continuation scenarios to ensure
conversation context is maintained when switching between different tools.
"""

from .conversation_base_test import ConversationBaseTest


class CrossToolContinuationTest(ConversationBaseTest):
    """Test comprehensive cross-tool continuation scenarios"""

    @property
    def test_name(self) -> str:
        return "cross_tool_continuation"

    @property
    def test_description(self) -> str:
        return "Cross-tool conversation continuation scenarios"

    def run_test(self) -> bool:
        """Test comprehensive cross-tool continuation scenarios"""
        try:
            self.logger.info("🔧 Test: Cross-tool continuation scenarios")

            # Setup test environment for conversation testing
            self.setUp()

            success_count = 0
            total_scenarios = 3

            # Scenario 1: chat -> thinkdeep -> codereview
            if self._test_chat_thinkdeep_codereview():
                success_count += 1

            # Scenario 2: analyze -> debug -> thinkdeep
            if self._test_analyze_debug_thinkdeep():
                success_count += 1

            # Scenario 3: Multi-file cross-tool continuation
            if self._test_multi_file_continuation():
                success_count += 1

            self.logger.info(
                f"  ✅ Cross-tool continuation scenarios completed: {success_count}/{total_scenarios} scenarios passed"
            )

            # Consider successful if at least one scenario worked
            return success_count > 0

        except Exception as e:
            self.logger.error(f"Cross-tool continuation test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()

    def _test_chat_thinkdeep_codereview(self) -> bool:
        """Test chat -> thinkdeep -> codereview scenario"""
        try:
            self.logger.info("  1: Testing chat -> thinkdeep -> codereview")

            # Start with chat
            chat_response, chat_id = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Look at this Python code and tell me what you think about it",
                    "files": [self.test_files["python"]],
                    "model": "flash",
                },
            )

            if not chat_response or not chat_id:
                self.logger.error("Failed to start chat conversation")
                return False

            # Continue with thinkdeep
            thinkdeep_response, _ = self.call_mcp_tool_direct(
                "thinkdeep",
                {
                    "prompt": "Please use low thinking mode. Think deeply about potential performance issues in this code",
                    "files": [self.test_files["python"]],  # Same file should be deduplicated
                    "continuation_id": chat_id,
                    "model": "flash",
                },
            )

            if not thinkdeep_response:
                self.logger.error("Failed chat -> thinkdeep continuation")
                return False

            # Continue with codereview
            codereview_response, _ = self.call_mcp_tool_direct(
                "codereview",
                {
                    "files": [self.test_files["python"]],  # Same file should be deduplicated
                    "prompt": "Building on our previous analysis, provide a comprehensive code review",
                    "continuation_id": chat_id,
                    "model": "flash",
                },
            )

            if not codereview_response:
                self.logger.error("Failed thinkdeep -> codereview continuation")
                return False

            self.logger.info("  ✅ chat -> thinkdeep -> codereview working")
            return True

        except Exception as e:
            self.logger.error(f"Chat -> thinkdeep -> codereview scenario failed: {e}")
            return False

    def _test_analyze_debug_thinkdeep(self) -> bool:
        """Test analyze -> debug -> thinkdeep scenario"""
        try:
            self.logger.info("  2: Testing analyze -> debug -> thinkdeep")

            # Start with analyze
            analyze_response, analyze_id = self.call_mcp_tool_direct(
                "analyze",
                {
                    "files": [self.test_files["python"]],
                    "prompt": "Analyze this code for quality and performance issues",
                    "model": "flash",
                },
            )

            if not analyze_response or not analyze_id:
                self.logger.warning("Failed to start analyze conversation, skipping scenario 2")
                return False

            # Continue with debug
            debug_response, _ = self.call_mcp_tool_direct(
                "debug",
                {
                    "files": [self.test_files["python"]],  # Same file should be deduplicated
                    "prompt": "Based on our analysis, help debug the performance issue in fibonacci",
                    "continuation_id": analyze_id,
                    "model": "flash",
                },
            )

            if not debug_response:
                self.logger.warning("  ⚠️ analyze -> debug continuation failed")
                return False

            # Continue with thinkdeep
            final_response, _ = self.call_mcp_tool_direct(
                "thinkdeep",
                {
                    "prompt": "Please use low thinking mode. Think deeply about the architectural implications of the issues we've found",
                    "files": [self.test_files["python"]],  # Same file should be deduplicated
                    "continuation_id": analyze_id,
                    "model": "flash",
                },
            )

            if not final_response:
                self.logger.warning("  ⚠️ debug -> thinkdeep continuation failed")
                return False

            self.logger.info("  ✅ analyze -> debug -> thinkdeep working")
            return True

        except Exception as e:
            self.logger.error(f"Analyze -> debug -> thinkdeep scenario failed: {e}")
            return False

    def _test_multi_file_continuation(self) -> bool:
        """Test multi-file cross-tool continuation"""
        try:
            self.logger.info("  3: Testing multi-file cross-tool continuation")

            # Start with both files
            multi_response, multi_id = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": "Please use low thinking mode. Analyze both the Python code and configuration file",
                    "files": [self.test_files["python"], self.test_files["config"]],
                    "model": "flash",
                },
            )

            if not multi_response or not multi_id:
                self.logger.warning("Failed to start multi-file conversation, skipping scenario 3")
                return False

            # Switch to codereview with same files (should use conversation history)
            multi_review, _ = self.call_mcp_tool_direct(
                "codereview",
                {
                    "files": [self.test_files["python"], self.test_files["config"]],  # Same files
                    "prompt": "Review both files in the context of our previous discussion",
                    "continuation_id": multi_id,
                    "model": "flash",
                },
            )

            if not multi_review:
                self.logger.warning("  ⚠️ Multi-file cross-tool continuation failed")
                return False

            self.logger.info("  ✅ Multi-file cross-tool continuation working")
            return True

        except Exception as e:
            self.logger.error(f"Multi-file continuation scenario failed: {e}")
            return False
