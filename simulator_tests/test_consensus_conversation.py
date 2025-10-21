#!/usr/bin/env python3
"""
Consensus Conversation Continuation Test

Tests that the consensus tool properly handles conversation continuation
and builds conversation context correctly when using continuation_id.
"""

import json

from .conversation_base_test import ConversationBaseTest


class TestConsensusConversation(ConversationBaseTest):
    """Test consensus tool conversation continuation functionality"""

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple:
        """Call an MCP tool in-process"""
        response_text, continuation_id = self.call_mcp_tool_direct(tool_name, params)
        return response_text, continuation_id

    @property
    def test_name(self) -> str:
        return "consensus_conversation"

    @property
    def test_description(self) -> str:
        return "Test consensus tool conversation building and continuation"

    def get_server_logs(self):
        """Get server logs from local log file"""
        try:
            log_file_path = "logs/mcp_server.log"
            with open(log_file_path) as f:
                lines = f.readlines()
                # Return last 100 lines
                return [line.strip() for line in lines[-100:]]
        except Exception as e:
            self.logger.warning(f"Exception getting server logs: {e}")
            return []

    def run_test(self) -> bool:
        """Test consensus conversation continuation"""
        try:
            self.logger.info("Testing consensus tool conversation continuation")

            # Initialize for in-process tool calling
            self.setUp()

            # Setup test files for context
            self.setup_test_files()

            # Phase 1: Start conversation with chat tool (which properly creates continuation_id)
            self.logger.info("Phase 1: Starting conversation with chat tool")
            initial_response, continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Please use low thinking mode. I'm working on a web application and need advice on authentication. Can you look at this code?",
                    "absolute_file_paths": [self.test_files["python"]],
                    "model": "flash",
                },
            )

            # Validate initial response
            if not initial_response:
                self.logger.error("Failed to get initial chat response")
                return False

            if not continuation_id:
                self.logger.error("Failed to get continuation_id from initial chat")
                return False

            self.logger.info(f"Initial chat response preview: {initial_response[:200]}...")
            self.logger.info(f"Got continuation_id: {continuation_id}")

            # Phase 2: Use consensus with continuation_id to test conversation building
            self.logger.info("Phase 2: Using consensus with continuation_id to test conversation building")
            consensus_response, _ = self.call_mcp_tool(
                "consensus",
                {
                    "step": "Based on our previous discussion about authentication, I need expert consensus: Should we implement OAuth2 or stick with simple session-based auth?",
                    "step_number": 1,
                    "total_steps": 2,
                    "next_step_required": True,
                    "findings": "Initial analysis needed on OAuth2 vs session-based authentication approaches for our web application",
                    "models": [
                        {
                            "model": "flash",
                            "stance": "for",
                            "stance_prompt": "Focus on OAuth2 benefits: security, scalability, and industry standards.",
                        },
                        {
                            "model": "flash",
                            "stance": "against",
                            "stance_prompt": "Focus on OAuth2 complexity: implementation challenges and simpler alternatives.",
                        },
                    ],
                    "continuation_id": continuation_id,
                    "model": "flash",
                },
            )

            # Validate consensus response
            if not consensus_response:
                self.logger.error("Failed to get consensus response with continuation_id")
                return False

            self.logger.info(f"Consensus response preview: {consensus_response[:300]}...")

            # Log the full response for debugging if it's not JSON
            if not consensus_response.startswith("{"):
                self.logger.error(f"Consensus response is not JSON. Full response: {consensus_response}")
                return False

            # Parse consensus response
            try:
                consensus_data = json.loads(consensus_response)
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse consensus response as JSON. Full response: {consensus_response}")
                return False

            # Check for step 1 status (Claude analysis + first model consultation)
            expected_status = "analysis_and_first_model_consulted"
            if consensus_data.get("status") != expected_status:
                self.logger.error(
                    f"Consensus step 1 failed with status: {consensus_data.get('status')}, expected: {expected_status}"
                )
                if "error" in consensus_data:
                    self.logger.error(f"Error: {consensus_data['error']}")
                return False

            # Phase 3: Check server logs for conversation building
            self.logger.info("Phase 3: Checking server logs for conversation building")

            # Check for conversation-related log entries
            logs = self.get_server_logs()
            if not logs:
                self.logger.warning("Could not retrieve server logs for verification")
            else:
                # Look for conversation building indicators
                conversation_logs = [
                    line
                    for line in logs
                    if any(
                        keyword in line
                        for keyword in [
                            "CONVERSATION HISTORY",
                            "continuation_id",
                            "build_conversation_history",
                            "ThreadContext",
                            f"thread:{continuation_id}",
                        ]
                    )
                ]

                if conversation_logs:
                    self.logger.info(f"Found {len(conversation_logs)} conversation-related log entries")
                    # Show a few examples (truncated)
                    for i, log in enumerate(conversation_logs[:3]):
                        self.logger.info(f"  Conversation log {i+1}: {log[:100]}...")
                else:
                    self.logger.warning(
                        "No conversation-related logs found (may indicate conversation not properly built)"
                    )

                # Check for any ERROR entries related to consensus
                error_logs = [
                    line
                    for line in logs
                    if "ERROR" in line
                    and any(keyword in line for keyword in ["consensus", "conversation", continuation_id])
                ]

                if error_logs:
                    self.logger.error(f"Found {len(error_logs)} error logs related to consensus conversation:")
                    for error in error_logs:
                        self.logger.error(f"  ERROR: {error}")
                    return False

            # Phase 4: Verify response structure
            self.logger.info("Phase 4: Verifying consensus response structure")

            # Check that we have model response from step 1
            model_response = consensus_data.get("model_response")
            if not model_response:
                self.logger.error("Consensus step 1 response missing model_response")
                return False

            # Check that model response has expected structure
            if not model_response.get("model") or not model_response.get("verdict"):
                self.logger.error("Model response missing required fields (model or verdict)")
                return False

            # Check step information
            if consensus_data.get("step_number") != 1:
                self.logger.error(f"Expected step_number 1, got: {consensus_data.get('step_number')}")
                return False

            if not consensus_data.get("next_step_required"):
                self.logger.error("Expected next_step_required=True for step 1")
                return False

            self.logger.info(f"Consensus step 1 consulted model: {model_response.get('model')}")
            self.logger.info(f"Model stance: {model_response.get('stance', 'neutral')}")
            self.logger.info(f"Response status: {model_response.get('status', 'unknown')}")

            # Phase 5: Cross-tool continuation test
            self.logger.info("Phase 5: Testing cross-tool continuation from consensus")

            # Try to continue the conversation with a different tool
            chat_response, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Based on our consensus discussion about authentication, can you summarize the key points?",
                    "continuation_id": continuation_id,
                    "model": "flash",
                },
            )

            if not chat_response:
                self.logger.warning("Cross-tool continuation from consensus failed")
                # Don't fail the test for this - it's a bonus check
            else:
                self.logger.info("✓ Cross-tool continuation from consensus working")
                self.logger.info(f"Chat continuation preview: {chat_response[:200]}...")

            self.logger.info("✓ Consensus conversation continuation test completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Consensus conversation test failed with exception: {str(e)}")
            import traceback

            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
        finally:
            self.cleanup_test_files()
