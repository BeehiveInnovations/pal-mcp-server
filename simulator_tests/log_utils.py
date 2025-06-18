"""
Centralized log utility for simulator tests.

This module provides common log reading and parsing functionality
used across multiple simulator test files to reduce code duplication.
"""

import logging
import re
import subprocess
from typing import Optional, Union


class LogUtils:
    """Centralized logging utilities for simulator tests."""

    # Log file paths
    MAIN_LOG_FILE = "logs/mcp_server.log"
    ACTIVITY_LOG_FILE = "logs/mcp_activity.log"

    @classmethod
    def get_server_logs_since(cls, since_time: Optional[str] = None) -> str:
        """
        Get server logs from both main and activity log files.

        Args:
            since_time: Currently ignored, returns all available logs

        Returns:
            Combined logs from both log files
        """
        try:
            main_logs = ""
            activity_logs = ""

            # Read main server log
            try:
                with open(cls.MAIN_LOG_FILE) as f:
                    main_logs = f.read()
            except FileNotFoundError:
                pass

            # Read activity log
            try:
                with open(cls.ACTIVITY_LOG_FILE) as f:
                    activity_logs = f.read()
            except FileNotFoundError:
                pass

            return main_logs + "\n" + activity_logs

        except Exception as e:
            logging.warning(f"Failed to read server logs: {e}")
            return ""

    @classmethod
    def get_recent_server_logs(cls, lines: int = 500) -> str:
        """
        Get recent server logs from the main log file.

        Args:
            lines: Number of recent lines to retrieve (default: 500)

        Returns:
            Recent log content as string
        """
        try:
            with open(cls.MAIN_LOG_FILE) as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return "".join(recent_lines)
        except FileNotFoundError:
            logging.warning(f"Log file {cls.MAIN_LOG_FILE} not found")
            return ""
        except Exception as e:
            logging.warning(f"Failed to read recent server logs: {e}")
            return ""

    @classmethod
    def get_server_logs_subprocess(cls, lines: int = 500) -> str:
        """
        Get server logs using subprocess (alternative method).

        Args:
            lines: Number of recent lines to retrieve

        Returns:
            Recent log content as string
        """
        try:
            result = subprocess.run(
                ["tail", "-n", str(lines), cls.MAIN_LOG_FILE], capture_output=True, text=True, timeout=10
            )
            return result.stdout + result.stderr
        except Exception as e:
            logging.warning(f"Failed to get server logs via subprocess: {e}")
            return ""

    @classmethod
    def check_server_logs_for_errors(cls, lines: int = 500) -> list[str]:
        """
        Check server logs for error messages.

        Args:
            lines: Number of recent lines to check

        Returns:
            List of error messages found
        """
        logs = cls.get_recent_server_logs(lines)
        error_patterns = [r"ERROR.*", r"CRITICAL.*", r"Failed.*", r"Exception.*", r"Error:.*"]

        errors = []
        for line in logs.split("\n"):
            for pattern in error_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    errors.append(line.strip())
                    break

        return errors

    @classmethod
    def extract_conversation_usage_logs(cls, logs: str) -> list[dict[str, int]]:
        """
        Extract token budget calculation information from logs.

        Args:
            logs: Log content to parse

        Returns:
            List of dictionaries containing token usage data
        """
        usage_data = []
        pattern = r"\[CONVERSATION_DEBUG\] Token budget calculation:"

        for line in logs.split("\n"):
            if re.search(pattern, line):
                # Parse the token usage information
                usage_info = {}

                # Extract total capacity
                capacity_match = re.search(r"Total capacity: ([\d,]+)", line)
                if capacity_match:
                    usage_info["total_capacity"] = int(capacity_match.group(1).replace(",", ""))

                # Extract content allocation
                content_match = re.search(r"Content allocation: ([\d,]+)", line)
                if content_match:
                    usage_info["content_allocation"] = int(content_match.group(1).replace(",", ""))

                # Extract conversation tokens
                conv_match = re.search(r"Conversation tokens: ([\d,]+)", line)
                if conv_match:
                    usage_info["conversation_tokens"] = int(conv_match.group(1).replace(",", ""))

                # Extract remaining tokens
                remaining_match = re.search(r"Remaining tokens: ([\d,]+)", line)
                if remaining_match:
                    usage_info["remaining_tokens"] = int(remaining_match.group(1).replace(",", ""))

                if usage_info:
                    usage_data.append(usage_info)

        return usage_data

    @classmethod
    def extract_conversation_token_usage(cls, logs: str) -> list[int]:
        """
        Extract conversation token usage values from logs.

        Args:
            logs: Log content to parse

        Returns:
            List of token usage values
        """
        pattern = r"Conversation history token usage:\s*([\d,]+)"
        usage_values = []

        for match in re.finditer(pattern, logs):
            usage_value = int(match.group(1).replace(",", ""))
            usage_values.append(usage_value)

        return usage_values

    @classmethod
    def extract_thread_creation_logs(cls, logs: str) -> list[dict[str, str]]:
        """
        Extract thread creation logs with parent relationships.

        Args:
            logs: Log content to parse

        Returns:
            List of dictionaries with thread relationship data
        """
        thread_data = []
        pattern = r"\[THREAD\] Created new thread (\w+)(?: with parent (\w+))?"

        for match in re.finditer(pattern, logs):
            thread_info = {"thread_id": match.group(1), "parent_id": match.group(2) if match.group(2) else None}
            thread_data.append(thread_info)

        return thread_data

    @classmethod
    def extract_history_traversal_logs(cls, logs: str) -> list[dict[str, Union[str, int]]]:
        """
        Extract conversation history traversal logs.

        Args:
            logs: Log content to parse

        Returns:
            List of dictionaries with traversal data
        """
        traversal_data = []
        pattern = r"\[THREAD\] Retrieved chain of (\d+) messages for thread (\w+)"

        for match in re.finditer(pattern, logs):
            traversal_info = {"chain_length": int(match.group(1)), "thread_id": match.group(2)}
            traversal_data.append(traversal_info)

        return traversal_data

    @classmethod
    def validate_file_deduplication_in_logs(cls, logs: str, tool_name: str, test_file: str) -> bool:
        """
        Validate that logs show file deduplication behavior.

        Args:
            logs: Log content to parse
            tool_name: Name of the tool being tested
            test_file: Name of the test file to check for deduplication

        Returns:
            True if deduplication evidence is found, False otherwise
        """
        # Look for embedding calculation
        embedding_pattern = f"Calculating embeddings for {test_file}"
        has_embedding = bool(re.search(embedding_pattern, logs))

        # Look for filtering message
        filtering_pattern = f"Filtering {test_file} to prevent duplication"
        has_filtering = bool(re.search(filtering_pattern, logs))

        # Look for skip message
        skip_pattern = f"Skipping {test_file} \\(already processed"
        has_skip = bool(re.search(skip_pattern, logs))

        # Look for tool-specific processing
        tool_pattern = f"\\[{tool_name.upper()}\\].*{test_file}"
        has_tool_processing = bool(re.search(tool_pattern, logs, re.IGNORECASE))

        # Deduplication is confirmed if we see evidence of processing and filtering/skipping
        return has_embedding and (has_filtering or has_skip) and has_tool_processing

    @classmethod
    def search_logs_for_pattern(
        cls, pattern: str, logs: Optional[str] = None, case_sensitive: bool = False
    ) -> list[str]:
        """
        Search logs for a specific pattern.

        Args:
            pattern: Regex pattern to search for
            logs: Log content to search (if None, reads recent logs)
            case_sensitive: Whether the search should be case sensitive

        Returns:
            List of matching lines
        """
        if logs is None:
            logs = cls.get_recent_server_logs()

        flags = 0 if case_sensitive else re.IGNORECASE
        matches = []

        for line in logs.split("\n"):
            if re.search(pattern, line, flags):
                matches.append(line.strip())

        return matches

    @classmethod
    def get_log_file_info(cls) -> dict[str, dict[str, Union[str, int, bool]]]:
        """
        Get information about log files.

        Returns:
            Dictionary with file information for each log file
        """
        import os

        file_info = {}

        for log_file in [cls.MAIN_LOG_FILE, cls.ACTIVITY_LOG_FILE]:
            if os.path.exists(log_file):
                stat = os.stat(log_file)
                file_info[log_file] = {
                    "exists": True,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "last_modified": stat.st_mtime,
                    "readable": os.access(log_file, os.R_OK),
                }
            else:
                file_info[log_file] = {
                    "exists": False,
                    "size_bytes": 0,
                    "size_mb": 0,
                    "last_modified": 0,
                    "readable": False,
                }

        return file_info
