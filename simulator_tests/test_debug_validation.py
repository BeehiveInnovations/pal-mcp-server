#!/usr/bin/env python3
"""
Debug Tool Self-Investigation Validation Test

Tests the debug tool's systematic self-investigation capabilities including:
- Step-by-step investigation with proper JSON responses
- Progressive tracking of findings, files, and methods
- Hypothesis formation and confidence tracking
- Backtracking and revision capabilities
- Final expert analysis after investigation completion
"""

import json
from typing import Optional

from .base_test import BaseSimulatorTest


class DebugValidationTest(BaseSimulatorTest):
    """Test debug tool's self-investigation and expert analysis features"""

    @property
    def test_name(self) -> str:
        return "debug_validation"

    @property
    def test_description(self) -> str:
        return "Debug tool self-investigation pattern validation"

    def run_test(self) -> bool:
        """Test debug tool self-investigation capabilities"""
        try:
            self.logger.info("Test: Debug tool self-investigation validation")

            # Setup test files directory first
            self.setup_test_files()

            # Create a Python file with a subtle but realistic bug
            self._create_buggy_code()

            # Test 1: Single investigation session with multiple steps
            if not self._test_single_investigation_session():
                return False

            # Test 2: Investigation with backtracking
            if not self._test_investigation_with_backtracking():
                return False

            # Test 3: Complete investigation with expert analysis
            if not self._test_complete_investigation_with_analysis():
                return False

            self.logger.info("  ✅ All debug validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"Debug validation test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()

    def _create_buggy_code(self):
        """Create test files with a subtle bug for debugging"""
        # Create a Python file with dictionary iteration bug
        buggy_code = """#!/usr/bin/env python3
import json
from datetime import datetime, timedelta

class SessionManager:
    def __init__(self):
        self.active_sessions = {}
        self.session_timeout = 30 * 60  # 30 minutes in seconds

    def create_session(self, user_id, user_data):
        \"\"\"Create a new user session\"\"\"
        session_id = f"sess_{user_id}_{datetime.now().timestamp()}"

        session_info = {
            'user_id': user_id,
            'user_data': user_data,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(seconds=self.session_timeout)
        }

        self.active_sessions[session_id] = session_info
        return session_id

    def validate_session(self, session_id):
        \"\"\"Check if session is valid and not expired\"\"\"
        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions[session_id]
        current_time = datetime.now()

        # Check if session has expired
        if current_time > session['expires_at']:
            del self.active_sessions[session_id]
            return False

        return True

    def cleanup_expired_sessions(self):
        \"\"\"Remove expired sessions from memory\"\"\"
        current_time = datetime.now()
        expired_count = 0

        # BUG: Modifying dictionary while iterating over it
        for session_id, session in self.active_sessions.items():
            if current_time > session['expires_at']:
                del self.active_sessions[session_id]  # This causes RuntimeError
                expired_count += 1

        return expired_count
"""

        # Create test file with subtle bug
        self.buggy_file = self.create_additional_test_file("session_manager.py", buggy_code)
        self.logger.info(f"  ✅ Created test file with subtle bug: {self.buggy_file}")

        # Create error description
        error_description = """ISSUE DESCRIPTION:
Our session management system is experiencing intermittent failures during cleanup operations.

SYMPTOMS:
- Random RuntimeError: dictionary changed size during iteration
- Occurs during high load when many sessions expire simultaneously
- Error happens in cleanup_expired_sessions method
- Affects about 5% of cleanup operations

ERROR LOG:
RuntimeError: dictionary changed size during iteration
  File "session_manager.py", line 44, in cleanup_expired_sessions
    for session_id, session in self.active_sessions.items():
"""

        self.error_file = self.create_additional_test_file("error_description.txt", error_description)
        self.logger.info(f"  ✅ Created error description file: {self.error_file}")

    def _test_single_investigation_session(self) -> bool:
        """Test a complete investigation session with multiple steps"""
        try:
            self.logger.info("  1.1: Testing single investigation session")

            # Step 1: Start investigation
            self.logger.info("    1.1.1: Step 1 - Initial investigation")
            response1, continuation_id = self.call_mcp_tool(
                "debug",
                {
                    "step": "I need to investigate intermittent RuntimeError during session cleanup. Let me start by examining the error description and understanding the symptoms.",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "RuntimeError occurs during dictionary iteration in cleanup_expired_sessions method. Error happens intermittently during high load.",
                    "files_checked": [self.error_file],
                    "relevant_files": [self.error_file],
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to get initial investigation response")
                return False

            # Parse and validate JSON response
            response1_data = self._parse_debug_response(response1)
            if not response1_data:
                return False

            # Validate step 1 response structure
            if not self._validate_step_response(response1_data, 1, 4, True, "investigation_in_progress"):
                return False

            self.logger.info(f"    ✅ Step 1 successful, continuation_id: {continuation_id}")

            # Step 2: Examine the code
            self.logger.info("    1.1.2: Step 2 - Code examination")
            response2, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Now examining the session_manager.py file to understand the cleanup_expired_sessions implementation and identify the root cause.",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Found the issue: cleanup_expired_sessions modifies self.active_sessions dictionary while iterating over it with .items(). This causes RuntimeError when del is called during iteration.",
                    "files_checked": [self.error_file, self.buggy_file],
                    "relevant_files": [self.buggy_file],
                    "relevant_methods": ["SessionManager.cleanup_expired_sessions"],
                    "hypothesis": "Dictionary is being modified during iteration causing RuntimeError",
                    "confidence": "high",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue investigation to step 2")
                return False

            response2_data = self._parse_debug_response(response2)
            if not self._validate_step_response(response2_data, 2, 4, True, "investigation_in_progress"):
                return False

            # Check investigation status tracking
            investigation_status = response2_data.get("investigation_status", {})
            if investigation_status.get("files_checked", 0) < 2:
                self.logger.error("Files checked count not properly tracked")
                return False

            if investigation_status.get("relevant_methods", 0) != 1:
                self.logger.error("Relevant methods not properly tracked")
                return False

            if investigation_status.get("current_confidence") != "high":
                self.logger.error("Confidence level not properly tracked")
                return False

            self.logger.info("    ✅ Step 2 successful with proper tracking")

            # Step 3: Validate hypothesis
            self.logger.info("    1.1.3: Step 3 - Hypothesis validation")
            response3, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Confirming the bug pattern: the for loop iterates over self.active_sessions.items() while del self.active_sessions[session_id] modifies the dictionary inside the loop.",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Confirmed: Line 44-47 shows classic dictionary modification during iteration bug. The fix would be to collect expired session IDs first, then delete them after iteration completes.",
                    "files_checked": [self.buggy_file],
                    "relevant_files": [self.buggy_file],
                    "relevant_methods": ["SessionManager.cleanup_expired_sessions"],
                    "hypothesis": "Dictionary modification during iteration in cleanup_expired_sessions causes RuntimeError",
                    "confidence": "high",
                    "continuation_id": continuation_id,
                },
            )

            if not response3:
                self.logger.error("Failed to continue investigation to step 3")
                return False

            response3_data = self._parse_debug_response(response3)
            if not self._validate_step_response(response3_data, 3, 4, True, "investigation_in_progress"):
                return False

            self.logger.info("    ✅ Investigation session progressing successfully")

            # Store continuation_id for next test
            self.investigation_continuation_id = continuation_id
            return True

        except Exception as e:
            self.logger.error(f"Single investigation session test failed: {e}")
            return False

    def _test_investigation_with_backtracking(self) -> bool:
        """Test investigation with backtracking to revise findings"""
        try:
            self.logger.info("  1.2: Testing investigation with backtracking")

            # Start a new investigation for testing backtracking
            self.logger.info("    1.2.1: Start investigation for backtracking test")
            response1, continuation_id = self.call_mcp_tool(
                "debug",
                {
                    "step": "Investigating performance degradation in data processing pipeline",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial analysis shows slow database queries",
                    "files_checked": ["/db/queries.py"],
                    "relevant_files": ["/db/queries.py"],
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start backtracking test investigation")
                return False

            # Step 2: Wrong direction
            self.logger.info("    1.2.2: Step 2 - Wrong investigation path")
            response2, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Focusing on database optimization strategies",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Database queries seem optimized, might be looking in wrong place",
                    "files_checked": ["/db/queries.py", "/db/indexes.py"],
                    "relevant_files": [],
                    "hypothesis": "Database performance issues",
                    "confidence": "low",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            # Step 3: Backtrack from step 2
            self.logger.info("    1.2.3: Step 3 - Backtrack and revise approach")
            response3, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Backtracking - the issue might not be database related. Let me investigate the data processing algorithm instead.",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Found inefficient nested loops in data processor causing O(n²) complexity",
                    "files_checked": ["/processor/algorithm.py"],
                    "relevant_files": ["/processor/algorithm.py"],
                    "relevant_methods": ["DataProcessor.process_batch"],
                    "hypothesis": "Inefficient algorithm causing performance issues",
                    "confidence": "medium",
                    "backtrack_from_step": 2,  # Backtrack from step 2
                    "continuation_id": continuation_id,
                },
            )

            if not response3:
                self.logger.error("Failed to backtrack")
                return False

            response3_data = self._parse_debug_response(response3)
            if not self._validate_step_response(response3_data, 3, 4, True, "investigation_in_progress"):
                return False

            self.logger.info("    ✅ Backtracking working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Backtracking test failed: {e}")
            return False

    def _test_complete_investigation_with_analysis(self) -> bool:
        """Test complete investigation ending with expert analysis"""
        try:
            self.logger.info("  1.3: Testing complete investigation with expert analysis")

            # Use the continuation from first test
            continuation_id = getattr(self, "investigation_continuation_id", None)
            if not continuation_id:
                # Start fresh if no continuation available
                self.logger.info("    1.3.0: Starting fresh investigation")
                response0, continuation_id = self.call_mcp_tool(
                    "debug",
                    {
                        "step": "Investigating the dictionary iteration bug in session cleanup",
                        "step_number": 1,
                        "total_steps": 2,
                        "next_step_required": True,
                        "findings": "Found dictionary modification during iteration",
                        "files_checked": [self.buggy_file],
                        "relevant_files": [self.buggy_file],
                        "relevant_methods": ["SessionManager.cleanup_expired_sessions"],
                    },
                )
                if not response0 or not continuation_id:
                    self.logger.error("Failed to start fresh investigation")
                    return False

            # Final step - trigger expert analysis
            self.logger.info("    1.3.1: Final step - complete investigation")
            response_final, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Investigation complete. The root cause is confirmed: cleanup_expired_sessions modifies the dictionary while iterating, causing RuntimeError.",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step - triggers expert analysis
                    "findings": "Root cause identified: del self.active_sessions[session_id] on line 46 modifies dictionary during iteration starting at line 44. Fix: collect expired IDs first, then delete.",
                    "files_checked": [self.buggy_file],
                    "relevant_files": [self.buggy_file],
                    "relevant_methods": ["SessionManager.cleanup_expired_sessions"],
                    "hypothesis": "Dictionary modification during iteration causes RuntimeError in cleanup_expired_sessions",
                    "confidence": "high",
                    "continuation_id": continuation_id,
                    "model": "flash",  # Use flash for expert analysis
                },
            )

            if not response_final:
                self.logger.error("Failed to complete investigation")
                return False

            response_final_data = self._parse_debug_response(response_final)
            if not response_final_data:
                return False

            # Validate final response structure
            if response_final_data.get("status") != "calling_expert_analysis":
                self.logger.error(
                    f"Expected status 'calling_expert_analysis', got '{response_final_data.get('status')}'"
                )
                return False

            if not response_final_data.get("investigation_complete"):
                self.logger.error("Expected investigation_complete=true for final step")
                return False

            # Check for expert analysis
            if "expert_analysis" not in response_final_data:
                self.logger.error("Missing expert_analysis in final response")
                return False

            expert_analysis = response_final_data.get("expert_analysis", {})

            # Check for expected analysis content (checking common patterns)
            analysis_text = json.dumps(expert_analysis).lower()

            # Look for bug identification
            bug_indicators = ["dictionary", "iteration", "modify", "runtime", "error", "del"]
            found_indicators = sum(1 for indicator in bug_indicators if indicator in analysis_text)

            if found_indicators >= 3:
                self.logger.info("    ✅ Expert analysis identified the bug correctly")
            else:
                self.logger.warning(
                    f"    ⚠️ Expert analysis may not have fully identified the bug (found {found_indicators}/6 indicators)"
                )

            # Check complete investigation summary
            if "complete_investigation" not in response_final_data:
                self.logger.error("Missing complete_investigation in final response")
                return False

            complete_investigation = response_final_data["complete_investigation"]
            if not complete_investigation.get("relevant_methods"):
                self.logger.error("Missing relevant methods in complete investigation")
                return False

            if "SessionManager.cleanup_expired_sessions" not in complete_investigation["relevant_methods"]:
                self.logger.error("Expected method not found in investigation summary")
                return False

            self.logger.info("    ✅ Complete investigation with expert analysis successful")

            # Validate logs
            self.logger.info("  📋 Validating execution logs...")

            # Get server logs
            logs = self.get_recent_server_logs(500)

            # Look for debug tool execution patterns
            debug_patterns = [
                "debug tool",
                "investigation",
                "Expert analysis",
                "calling_expert_analysis",
            ]

            patterns_found = 0
            for pattern in debug_patterns:
                if pattern in logs:
                    patterns_found += 1
                    self.logger.debug(f"  ✅ Found log pattern: {pattern}")

            if patterns_found >= 2:
                self.logger.info(f"  ✅ Log validation passed ({patterns_found}/{len(debug_patterns)} patterns)")
            else:
                self.logger.warning(f"  ⚠️ Only found {patterns_found}/{len(debug_patterns)} log patterns")

            return True

        except Exception as e:
            self.logger.error(f"Complete investigation test failed: {e}")
            return False

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool via standalone server - override for debug-specific response handling"""
        # Use parent implementation to get the raw response
        response_text, _ = super().call_mcp_tool(tool_name, params)

        if not response_text:
            return None, None

        # Extract continuation_id from debug response specifically
        continuation_id = self._extract_debug_continuation_id(response_text)

        return response_text, continuation_id

    def _extract_debug_continuation_id(self, response_text: str) -> Optional[str]:
        """Extract continuation_id from debug response"""
        try:
            # Parse the response
            response_data = json.loads(response_text)
            return response_data.get("continuation_id")

        except json.JSONDecodeError as e:
            self.logger.debug(f"Failed to parse response for debug continuation_id: {e}")
            return None

    def _parse_debug_response(self, response_text: str) -> dict:
        """Parse debug tool JSON response"""
        try:
            # Parse the response - it should be direct JSON
            return json.loads(response_text)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse debug response as JSON: {e}")
            self.logger.error(f"Response text: {response_text[:500]}...")
            return {}

    def _validate_step_response(
        self,
        response_data: dict,
        expected_step: int,
        expected_total: int,
        expected_next_required: bool,
        expected_status: str,
    ) -> bool:
        """Validate a debug investigation step response structure"""
        try:
            # Check status
            if response_data.get("status") != expected_status:
                self.logger.error(f"Expected status '{expected_status}', got '{response_data.get('status')}'")
                return False

            # Check step number
            if response_data.get("step_number") != expected_step:
                self.logger.error(f"Expected step_number {expected_step}, got {response_data.get('step_number')}")
                return False

            # Check total steps
            if response_data.get("total_steps") != expected_total:
                self.logger.error(f"Expected total_steps {expected_total}, got {response_data.get('total_steps')}")
                return False

            # Check next_step_required
            if response_data.get("next_step_required") != expected_next_required:
                self.logger.error(
                    f"Expected next_step_required {expected_next_required}, got {response_data.get('next_step_required')}"
                )
                return False

            # Check investigation_status exists
            if "investigation_status" not in response_data:
                self.logger.error("Missing investigation_status in response")
                return False

            # Check output guidance exists
            if "output" not in response_data:
                self.logger.error("Missing output guidance in response")
                return False

            # Check next_steps guidance
            if not response_data.get("next_steps"):
                self.logger.error("Missing next_steps guidance in response")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating step response: {e}")
            return False
