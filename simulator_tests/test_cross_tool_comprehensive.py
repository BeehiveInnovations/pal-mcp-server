#!/usr/bin/env python3
"""
Comprehensive Cross-Tool Test

Tests file deduplication, conversation continuation, and file handling
across all available MCP tools using realistic workflows with low thinking mode.
Validates:
1. Cross-tool conversation continuation
2. File deduplication across different tools
3. Mixed file scenarios (old + new files)
4. Conversation history preservation
5. Proper tool chaining with context
"""


from .conversation_base_test import ConversationBaseTest


class CrossToolComprehensiveTest(ConversationBaseTest):
    """Comprehensive test across all MCP tools"""

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple:
        """Call an MCP tool in-process"""
        # Use the new method for workflow tools
        workflow_tools = ["analyze", "debug", "codereview", "precommit", "refactor", "thinkdeep"]
        if tool_name in workflow_tools:
            response_text, continuation_id = super().call_mcp_tool(tool_name, params)
        else:
            response_text, continuation_id = self.call_mcp_tool_direct(tool_name, params)
        return response_text, continuation_id

    @property
    def test_name(self) -> str:
        return "cross_tool_comprehensive"

    @property
    def test_description(self) -> str:
        return "Comprehensive cross-tool file deduplication and continuation"

    def run_test(self) -> bool:
        """Comprehensive cross-tool test with all MCP tools"""
        try:
            self.logger.info("📄 Test: Comprehensive cross-tool file deduplication and continuation")

            # Initialize for in-process tool calling
            self.setUp()

            # Setup test files
            self.setup_test_files()

            # Create short test files for quick testing
            python_code = """def login(user, pwd):
    # Security issue: plain text password
    if user == "admin" and pwd == "123":
        return True
    return False

def hash_pwd(pwd):
    # Weak hashing
    return str(hash(pwd))
"""

            config_file = """{
    "db_password": "weak123",
    "debug": true,
    "secret_key": "test"
}"""

            auth_file = self.create_additional_test_file("auth.py", python_code)
            config_file_path = self.create_additional_test_file("config.json", config_file)

            # Get timestamp for log filtering
            import datetime

            start_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            # Tool chain: chat → analyze → debug → codereview → precommit
            # Each step builds on the previous with cross-tool continuation

            current_continuation_id = None
            responses = []

            # Step 1: Start with chat tool to understand the codebase
            self.logger.info("  Step 1: chat tool - Initial codebase exploration")
            chat_params = {
                "prompt": "List security issues in auth.py",
                "files": [auth_file],
                "thinking_mode": "low",
                "model": "flash",
            }

            response1, continuation_id1 = self.call_mcp_tool("chat", chat_params)
            if not response1 or not continuation_id1:
                self.logger.error("  ❌ Step 1: chat tool failed")
                return False

            self.logger.info(f"  ✅ Step 1: chat completed with continuation_id: {continuation_id1[:8]}...")
            responses.append(("chat", response1, continuation_id1))
            current_continuation_id = continuation_id1

            # Step 2: Use analyze tool to do deeper analysis (fresh conversation)
            self.logger.info("  Step 2: analyze tool - Deep code analysis (fresh)")
            analyze_params = {
                "step": "Starting comprehensive code analysis to find security vulnerabilities in the authentication system",
                "step_number": 1,
                "total_steps": 2,
                "next_step_required": True,
                "findings": "Initial analysis will focus on security vulnerabilities in authentication code",
                "relevant_files": [auth_file],
                "thinking_mode": "low",
                "model": "flash",
            }

            response2, continuation_id2 = self.call_mcp_tool("analyze", analyze_params)
            if not response2:
                self.logger.error("  ❌ Step 2: analyze tool failed")
                return False

            self.logger.info(
                f"  ✅ Step 2: analyze completed with continuation_id: {continuation_id2[:8] if continuation_id2 else 'None'}..."
            )
            responses.append(("analyze", response2, continuation_id2))

            # Step 3: Continue chat conversation with config file
            self.logger.info("  Step 3: chat continuation - Add config file context")
            chat_continue_params = {
                "continuation_id": current_continuation_id,
                "prompt": "Check config.json too",
                "files": [auth_file, config_file_path],  # Old + new file
                "thinking_mode": "low",
                "model": "flash",
            }

            response3, _ = self.call_mcp_tool("chat", chat_continue_params)
            if not response3:
                self.logger.error("  ❌ Step 3: chat continuation failed")
                return False

            self.logger.info("  ✅ Step 3: chat continuation completed")
            responses.append(("chat_continue", response3, current_continuation_id))

            # Step 4: Use debug tool to identify specific issues
            self.logger.info("  Step 4: debug tool - Identify specific problems")
            debug_params = {
                "step": "Starting debug investigation to identify and fix authentication security issues",
                "step_number": 1,
                "total_steps": 2,
                "next_step_required": True,
                "findings": "Investigating authentication vulnerabilities found in previous analysis",
                "relevant_files": [auth_file, config_file_path],
                "thinking_mode": "low",
                "model": "flash",
            }

            response4, continuation_id4 = self.call_mcp_tool("debug", debug_params)
            if not response4:
                self.logger.error("  ❌ Step 4: debug tool failed")
                return False

            self.logger.info(
                f"  ✅ Step 4: debug completed with continuation_id: {continuation_id4[:8] if continuation_id4 else 'None'}..."
            )
            responses.append(("debug", response4, continuation_id4))

            # Step 5: Cross-tool continuation - continue debug with chat context
            if continuation_id4:
                self.logger.info("  Step 5: debug continuation - Additional analysis")
                debug_continue_params = {
                    "step": "Continuing debug investigation to fix password hashing implementation",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,
                    "findings": "Building on previous analysis to fix weak password hashing",
                    "continuation_id": continuation_id4,
                    "relevant_files": [auth_file, config_file_path],
                    "thinking_mode": "low",
                    "model": "flash",
                }

                response5, _ = self.call_mcp_tool("debug", debug_continue_params)
                if response5:
                    self.logger.info("  ✅ Step 5: debug continuation completed")
                    responses.append(("debug_continue", response5, continuation_id4))

            # Step 6: Use codereview for comprehensive review
            self.logger.info("  Step 6: codereview tool - Comprehensive code review")
            codereview_params = {
                "step": "Starting comprehensive security code review of authentication system",
                "step_number": 1,
                "total_steps": 2,
                "next_step_required": True,
                "findings": "Performing thorough security review of authentication code and configuration",
                "relevant_files": [auth_file, config_file_path],
                "thinking_mode": "low",
                "model": "flash",
            }

            response6, continuation_id6 = self.call_mcp_tool("codereview", codereview_params)
            if not response6:
                self.logger.error("  ❌ Step 6: codereview tool failed")
                return False

            self.logger.info(
                f"  ✅ Step 6: codereview completed with continuation_id: {continuation_id6[:8] if continuation_id6 else 'None'}..."
            )
            responses.append(("codereview", response6, continuation_id6))

            # Step 7: Create improved version and use precommit
            self.logger.info("  Step 7: precommit tool - Pre-commit validation")

            # Create a short improved version
            improved_code = """import hashlib

def secure_login(user, pwd):
    # Better: hashed password check
    hashed = hashlib.sha256(pwd.encode()).hexdigest()
    if user == "admin" and hashed == "expected_hash":
        return True
    return False
"""

            improved_file = self.create_additional_test_file("auth_improved.py", improved_code)

            precommit_params = {
                "step": "Starting pre-commit validation of improved authentication code",
                "step_number": 1,
                "total_steps": 2,
                "next_step_required": True,
                "findings": "Validating improved authentication implementation before commit",
                "path": self.test_dir,
                "relevant_files": [auth_file, config_file_path, improved_file],
                "thinking_mode": "low",
                "model": "flash",
            }

            response7, continuation_id7 = self.call_mcp_tool("precommit", precommit_params)
            if not response7:
                self.logger.error("  ❌ Step 7: precommit tool failed")
                return False

            self.logger.info(
                f"  ✅ Step 7: precommit completed with continuation_id: {continuation_id7[:8] if continuation_id7 else 'None'}..."
            )
            responses.append(("precommit", response7, continuation_id7))

            # Validate comprehensive results
            self.logger.info("  📋 Validating comprehensive cross-tool results...")
            logs = self.get_server_logs_since(start_time)

            # Validation criteria
            tools_used = [r[0] for r in responses]
            continuation_ids_created = [r[2] for r in responses if r[2]]

            # Check for various log patterns
            conversation_logs = [
                line for line in logs.split("\n") if "conversation" in line.lower() or "history" in line.lower()
            ]
            embedding_logs = [
                line
                for line in logs.split("\n")
                if "📁" in line or "embedding" in line.lower() or "file" in line.lower()
            ]
            continuation_logs = [
                line for line in logs.split("\n") if "continuation" in line.lower() or "resuming" in line.lower()
            ]
            cross_tool_logs = [
                line
                for line in logs.split("\n")
                if any(tool in line.lower() for tool in ["chat", "analyze", "debug", "codereview", "precommit"])
            ]

            # File mentions
            auth_file_mentioned = any("auth.py" in line for line in logs.split("\n"))
            config_file_mentioned = any("config.json" in line for line in logs.split("\n"))
            improved_file_mentioned = any("auth_improved.py" in line for line in logs.split("\n"))

            # Print comprehensive diagnostics
            self.logger.info(f"   Tools used: {len(tools_used)} ({', '.join(tools_used)})")
            self.logger.info(f"   Continuation IDs created: {len(continuation_ids_created)}")
            self.logger.info(f"   Conversation logs found: {len(conversation_logs)}")
            self.logger.info(f"   File embedding logs found: {len(embedding_logs)}")
            self.logger.info(f"   Continuation logs found: {len(continuation_logs)}")
            self.logger.info(f"   Cross-tool activity logs: {len(cross_tool_logs)}")
            self.logger.info(f"   Auth file mentioned: {auth_file_mentioned}")
            self.logger.info(f"   Config file mentioned: {config_file_mentioned}")
            self.logger.info(f"   Improved file mentioned: {improved_file_mentioned}")

            if self.verbose:
                self.logger.debug("  📋 Sample tool activity logs:")
                for log in cross_tool_logs[:10]:  # Show first 10
                    if log.strip():
                        self.logger.debug(f"    {log.strip()}")

                self.logger.debug("  📋 Sample continuation logs:")
                for log in continuation_logs[:5]:  # Show first 5
                    if log.strip():
                        self.logger.debug(f"    {log.strip()}")

            # Comprehensive success criteria
            success_criteria = [
                len(tools_used) >= 5,  # Used multiple tools
                len(continuation_ids_created) >= 3,  # Created multiple continuation threads
                len(embedding_logs) > 10,  # Significant file embedding activity
                len(continuation_logs) > 0,  # Evidence of continuation
                auth_file_mentioned,  # Original file processed
                config_file_mentioned,  # Additional file processed
                improved_file_mentioned,  # New file processed
                len(conversation_logs) > 5,  # Conversation history activity
            ]

            passed_criteria = sum(success_criteria)
            total_criteria = len(success_criteria)

            self.logger.info(f"   Success criteria met: {passed_criteria}/{total_criteria}")

            # Allow for slight variations in log output (7/8 is sufficient for comprehensive test)
            if passed_criteria >= total_criteria - 1:  # Allow 1 missing criterion
                self.logger.info("  ✅ Comprehensive cross-tool test: PASSED")
                if passed_criteria < total_criteria:
                    self.logger.info(
                        f"  ℹ️ Note: {total_criteria - passed_criteria} criterion not met (acceptable variation)"
                    )
                return True
            else:
                self.logger.warning("  ⚠️ Comprehensive cross-tool test: FAILED")
                self.logger.warning("  💡 Check logs for detailed cross-tool activity")
                return False

        except Exception as e:
            self.logger.error(f"Comprehensive cross-tool test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()
