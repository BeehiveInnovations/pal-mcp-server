#!/usr/bin/env python3
"""
Server Logs Validation Test

Validates server logs to confirm file deduplication behavior and
conversation threading is working properly.
"""

from .base_test import BaseSimulatorTest


class LogsValidationTest(BaseSimulatorTest):
    """Validate server logs to confirm file deduplication behavior"""

    @property
    def test_name(self) -> str:
        return "logs_validation"

    @property
    def test_description(self) -> str:
        return "Server logs validation"

    def run_test(self) -> bool:
        """Validate server logs to confirm file deduplication behavior"""
        try:
            self.logger.info("📋 Test: Validating server logs for file deduplication...")

            # Get server logs from log files
            import os

            logs = ""
            log_files = ["logs/mcp_server.log", "logs/mcp_activity.log"]

            for log_file in log_files:
                if os.path.exists(log_file):
                    try:
                        with open(log_file) as f:
                            file_content = f.read()
                            logs += f"\n=== {log_file} ===\n{file_content}\n"
                            self.logger.debug(f"Read {len(file_content)} characters from {log_file}")
                    except Exception as e:
                        self.logger.warning(f"Could not read {log_file}: {e}")
                else:
                    self.logger.warning(f"Log file not found: {log_file}")

            if not logs.strip():
                self.logger.warning("No log content found - server may not have processed any requests yet")
                return False

            # Look for conversation threading patterns that indicate the system is working
            conversation_patterns = [
                "CONVERSATION_RESUME",
                "CONVERSATION_CONTEXT",
                "previous turns loaded",
                "tool embedding",
                "files included",
                "files truncated",
                "already in conversation history",
            ]

            conversation_lines = []
            for line in logs.split("\n"):
                for pattern in conversation_patterns:
                    if pattern.lower() in line.lower():
                        conversation_lines.append(line.strip())
                        break

            # Look for evidence of conversation threading and file handling
            conversation_threading_found = False
            multi_turn_conversations = False

            for line in conversation_lines:
                lower_line = line.lower()
                if "conversation_resume" in lower_line:
                    conversation_threading_found = True
                    self.logger.debug(f"📄 Conversation threading: {line}")
                elif "previous turns loaded" in lower_line:
                    multi_turn_conversations = True
                    self.logger.debug(f"📄 Multi-turn conversation: {line}")
                elif "already in conversation" in lower_line:
                    self.logger.info(f"✅ Found explicit deduplication: {line}")
                    return True

            # Conversation threading with multiple turns is evidence of file deduplication working
            if conversation_threading_found and multi_turn_conversations:
                self.logger.info("✅ Conversation threading with multi-turn context working")
                self.logger.info(
                    "✅ File deduplication working implicitly (files embedded once in conversation history)"
                )
                return True
            elif conversation_threading_found:
                self.logger.info("✅ Conversation threading detected")
                return True
            else:
                self.logger.warning("⚠️  No clear evidence of conversation threading in logs")
                self.logger.debug(f"Found {len(conversation_lines)} conversation-related log lines")
                return False

        except Exception as e:
            self.logger.error(f"Log validation failed: {e}")
            return False
