#!/usr/bin/env python3
"""
Conversation Base Test Class for In-Process MCP Tool Testing

This class enables testing MCP tools within the same process to maintain conversation
memory state across tool calls. Unlike BaseSimulatorTest which runs each tool call
as a separate subprocess (losing memory state), this class calls tools directly
in-process, allowing conversation functionality to work correctly.

USAGE:
- Inherit from ConversationBaseTest instead of BaseSimulatorTest for conversation tests
- Use call_mcp_tool_direct() to call tools in-process
- Conversation memory persists across tool calls within the same test
- setUp() clears memory between test methods for proper isolation

EXAMPLE:
    class TestConversationFeature(ConversationBaseTest):
        def test_cross_tool_continuation(self):
            # Step 1: Call precommit tool
            result1, continuation_id = self.call_mcp_tool_direct("precommit", {
                "path": "/path/to/repo",
                "prompt": "Review these changes"
            })

            # Step 2: Continue with codereview tool - memory is preserved!
            result2, _ = self.call_mcp_tool_direct("codereview", {
                "files": ["/path/to/file.py"],
                "prompt": "Focus on security issues",
                "continuation_id": continuation_id
            })
"""

import asyncio
import json
from typing import Optional

from .base_test import BaseSimulatorTest


class ConversationBaseTest(BaseSimulatorTest):
    """Base class for conversation tests that require in-process tool calling"""

    def __init__(self, verbose: bool = False):
        super().__init__(verbose)
        self._tools = None
        self._loop = None

    def setUp(self):
        """Set up test environment - clears conversation memory between tests"""
        super().setup_test_files()

        # Clear conversation memory for test isolation
        self._clear_conversation_memory()

        # Import tools from server.py for in-process calling
        if self._tools is None:
            self._import_tools()

    def _clear_conversation_memory(self):
        """Clear all conversation memory to ensure test isolation"""
        try:
            from utils.storage_backend import get_storage_backend

            storage = get_storage_backend()
            # Clear all stored conversation threads
            with storage._lock:
                storage._store.clear()
            self.logger.debug("Cleared conversation memory for test isolation")
        except Exception as e:
            self.logger.warning(f"Could not clear conversation memory: {e}")

    def _import_tools(self):
        """Import tools from server.py for direct calling"""
        try:
            import os
            import sys

            # Add project root to Python path if not already there
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

            # Import and configure providers first (this is what main() does)
            from server import TOOLS, configure_providers

            configure_providers()

            self._tools = TOOLS
            self.logger.debug(f"Imported {len(self._tools)} tools for in-process testing")
        except ImportError as e:
            raise RuntimeError(f"Could not import tools from server.py: {e}")

    def _get_event_loop(self):
        """Get or create event loop for async tool execution"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def call_mcp_tool_direct(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """
        Call an MCP tool directly in-process without subprocess isolation.

        This method maintains conversation memory across calls, enabling proper
        testing of conversation functionality.

        Args:
            tool_name: Name of the tool to call (e.g., "precommit", "codereview")
            params: Parameters to pass to the tool

        Returns:
            tuple: (response_content, continuation_id) where continuation_id
                   can be used for follow-up calls
        """
        if self._tools is None:
            raise RuntimeError("Tools not imported. Call setUp() first.")

        if tool_name not in self._tools:
            raise ValueError(f"Tool '{tool_name}' not found. Available: {list(self._tools.keys())}")

        try:
            tool = self._tools[tool_name]
            self.logger.debug(f"Calling tool '{tool_name}' directly in-process")

            # Set up minimal model context if not provided
            if "model" not in params:
                params["model"] = "flash"  # Use fast model for testing

            # Execute tool directly using asyncio
            loop = self._get_event_loop()

            # Import required modules for model resolution (similar to server.py)
            from config import DEFAULT_MODEL
            from providers.registry import ModelProviderRegistry
            from utils.model_context import ModelContext

            # Resolve model (simplified version of server.py logic)
            model_name = params.get("model", DEFAULT_MODEL)
            provider = ModelProviderRegistry.get_provider_for_model(model_name)
            if not provider:
                # Fallback to available model for testing
                available_models = list(ModelProviderRegistry.get_available_models(respect_restrictions=True).keys())
                if available_models:
                    model_name = available_models[0]
                    params["model"] = model_name
                    self.logger.debug(f"Using fallback model for testing: {model_name}")

            # Create model context
            model_context = ModelContext(model_name)
            params["_model_context"] = model_context
            params["_resolved_model_name"] = model_name

            # Execute tool asynchronously
            result = loop.run_until_complete(tool.execute(params))

            if not result or len(result) == 0:
                return None, None

            # Extract response content
            response_text = result[0].text if hasattr(result[0], "text") else str(result[0])

            # Parse response to extract continuation_id
            continuation_id = self._extract_continuation_id_from_response(response_text)

            self.logger.debug(f"Tool '{tool_name}' completed successfully in-process")
            if self.verbose and response_text:
                self.logger.debug(f"Response preview: {response_text[:500]}...")
            return response_text, continuation_id

        except Exception as e:
            self.logger.error(f"Direct tool call failed for '{tool_name}': {e}")
            return None, None

    def _extract_continuation_id_from_response(self, response_text: str) -> Optional[str]:
        """Extract continuation_id from tool response"""
        try:
            # Parse the response as JSON to look for continuation metadata
            response_data = json.loads(response_text)

            # Look for continuation_id in various places
            if isinstance(response_data, dict):
                # Check top-level continuation_id (workflow tools)
                if "continuation_id" in response_data:
                    return response_data["continuation_id"]

                # Check metadata
                metadata = response_data.get("metadata", {})
                if "thread_id" in metadata:
                    return metadata["thread_id"]

                # Check continuation_offer
                continuation_offer = response_data.get("continuation_offer", {})
                if continuation_offer and "continuation_id" in continuation_offer:
                    return continuation_offer["continuation_id"]

                # Check follow_up_request
                follow_up = response_data.get("follow_up_request", {})
                if follow_up and "continuation_id" in follow_up:
                    return follow_up["continuation_id"]

                # Special case: files_required_to_continue may have nested content
                if response_data.get("status") == "files_required_to_continue":
                    content = response_data.get("content", "")
                    if isinstance(content, str):
                        try:
                            # Try to parse nested JSON
                            nested_data = json.loads(content)
                            if isinstance(nested_data, dict):
                                # Check for continuation in nested data
                                follow_up = nested_data.get("follow_up_request", {})
                                if follow_up and "continuation_id" in follow_up:
                                    return follow_up["continuation_id"]
                        except json.JSONDecodeError:
                            pass

            return None

        except (json.JSONDecodeError, AttributeError):
            # If response is not JSON or doesn't have expected structure, return None
            return None

    def tearDown(self):
        """Clean up after test"""
        super().cleanup_test_files()
        # Clear memory again for good measure
        self._clear_conversation_memory()

    @property
    def test_name(self) -> str:
        """Get the test name"""
        return self.__class__.__name__

    @property
    def test_description(self) -> str:
        """Get the test description"""
        return "In-process conversation test"
