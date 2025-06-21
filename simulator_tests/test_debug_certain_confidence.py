#!/usr/bin/env python3
"""
Debug Tool Certain Confidence Simulator Test

Tests the debug tool's 'certain' confidence feature in a realistic simulation:
- Multi-step investigation leading to certain confidence
- Validation that expert analysis is skipped for obvious bugs
- Verification that certain confidence is always trusted
- Ensures token optimization works correctly for minimal fixes
"""

import json
from typing import Optional

from .conversation_base_test import ConversationBaseTest


class DebugCertainConfidenceTest(ConversationBaseTest):
    """Test debug tool's certain confidence optimization feature"""

    @property
    def test_name(self) -> str:
        return "debug_certain_confidence"

    @property
    def test_description(self) -> str:
        return "Debug tool certain confidence optimization validation"

    def run_test(self) -> bool:
        """Test debug tool certain confidence capabilities"""
        # Set up the test environment
        self.setUp()

        try:
            self.logger.info("Test: Debug tool certain confidence validation")

            # Create test files with obvious bugs for certain scenarios
            self._create_obvious_bug_scenarios()

            # Test 1: Obvious import error with certain confidence
            if not self._test_obvious_import_error_certain():
                return False

            # Test 2: Certain confidence is always trusted
            if not self._test_certain_always_trusted():
                return False

            # Test 3: Regular high confidence still triggers expert analysis
            if not self._test_regular_high_confidence_expert_analysis():
                return False

            # Test 4: Multi-step investigation ending in certain
            if not self._test_multi_step_investigation_certain():
                return False

            self.logger.info("  ✅ All debug certain confidence tests passed")
            return True

        except Exception as e:
            self.logger.error(f"Debug certain confidence test failed: {e}")
            return False

    def _create_obvious_bug_scenarios(self):
        """Create test files with obvious bugs perfect for certain confidence"""

        # Scenario 1: Missing import statement (very obvious)
        missing_import_code = """#!/usr/bin/env python3
import os
import sys
# import hashlib  # <-- Missing import!

class UserAuth:
    def __init__(self, secret_key):
        self.secret_key = secret_key

    def hash_password(self, password):
        # This will fail with NameError: name 'hashlib' is not defined
        salt = os.urandom(32)
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)

    def verify_password(self, password, stored_hash):
        # This function also uses hashlib
        return hashlib.pbkdf2_hmac('sha256', password.encode(), stored_hash[:32], 100000) == stored_hash[32:]
"""

        # Scenario 2: Typo in method name (obvious once spotted)
        typo_bug_code = """#!/usr/bin/env python3
class Calculator:
    def __init__(self):
        self.history = []

    def add_numbers(self, a, b):
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result

    def calculate_total(self, numbers):
        total = 0
        for num in numbers:
            # Typo: should be add_numbers, not add_number
            total = self.add_number(total, num)  # NameError: no method 'add_number'
        return total
"""

        # Scenario 3: Indentation error (Python syntax error)
        indentation_error_code = """#!/usr/bin/env python3
def process_data(data_list):
    results = []
    for item in data_list:
        if item > 0:
            processed = item * 2
        results.append(processed)  # IndentationError: unindent does not match any outer indentation level
    return results

def main():
    data = [1, 2, 3, 4, 5]
    print(process_data(data))
"""

        # Create test files
        self.missing_import_file = self.create_additional_test_file("user_auth.py", missing_import_code)
        self.typo_bug_file = self.create_additional_test_file("calculator.py", typo_bug_code)
        self.indentation_file = self.create_additional_test_file("data_processor.py", indentation_error_code)

        self.logger.info("  ✅ Created obvious bug scenarios:")
        self.logger.info(f"    - Missing import: {self.missing_import_file}")
        self.logger.info(f"    - Method typo: {self.typo_bug_file}")
        self.logger.info(f"    - Indentation error: {self.indentation_file}")

        # Create error logs for context
        import_error_log = """ERROR: User authentication failing during login
Traceback (most recent call last):
  File "user_auth.py", line 12, in hash_password
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
NameError: name 'hashlib' is not defined

This happens every time a user tries to log in. The error occurs in the password hashing function.
"""

        self.error_log_file = self.create_additional_test_file("error.log", import_error_log)
        self.logger.info(f"    - Error log: {self.error_log_file}")

    def _test_obvious_import_error_certain(self) -> bool:
        """Test certain confidence with obvious missing import error"""
        try:
            self.logger.info("  1.1: Testing obvious import error with certain confidence")

            # Step 1: Initial investigation
            self.logger.info("    1.1.1: Step 1 - Initial problem description")
            response1, continuation_id = self.call_mcp_tool_direct(
                "debug",
                {
                    "step": "Investigating NameError in user authentication - users cannot log in due to 'name hashlib is not defined' error.",
                    "step_number": 1,
                    "total_steps": 2,
                    "next_step_required": True,
                    "findings": "NameError occurs in hash_password method when trying to use hashlib.pbkdf2_hmac. Error happens on every login attempt.",
                    "files_checked": [self.error_log_file],
                    "relevant_files": [self.error_log_file],
                    "hypothesis": "Missing import statement for hashlib module",
                    "confidence": "medium",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to get initial investigation response")
                return False

            response1_data = self._parse_debug_response(response1)
            if not self._validate_investigation_response(response1_data, 1, True, "pause_for_investigation"):
                return False

            self.logger.info(f"    ✅ Step 1 successful, continuation_id: {continuation_id}")

            # Step 2: Examine code and identify obvious fix - use certain confidence
            self.logger.info("    1.1.2: Step 2 - Found exact issue and simple fix (certain)")
            response2, _ = self.call_mcp_tool_direct(
                "debug",
                {
                    "step": "Found the exact issue and the minimal fix required",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step
                    "findings": "Missing 'import hashlib' statement at the top of user_auth.py file. The error occurs because hashlib is used in hash_password() method on line 12 but never imported. Simple one-line fix: add 'import hashlib' after line 2.",
                    "files_checked": [self.error_log_file, self.missing_import_file],
                    "relevant_files": [self.missing_import_file],
                    "relevant_context": ["UserAuth.hash_password", "UserAuth.verify_password"],
                    "hypothesis": "Missing 'import hashlib' statement causes NameError when hash_password method executes",
                    "confidence": "certain",  # Use certain - should skip expert analysis
                    "continuation_id": continuation_id,
                    "model": "flash",  # Specify model for consistency
                },
            )

            if not response2:
                self.logger.error("Failed to complete investigation with certain confidence")
                return False

            response2_data = self._parse_debug_response(response2)
            if not response2_data:
                return False

            # Validate certain response structure
            expected_status = "certain_confidence_proceed_with_fix"
            if response2_data.get("status") != expected_status:
                self.logger.error(f"Expected status '{expected_status}', got '{response2_data.get('status')}'")
                return False

            if not response2_data.get("investigation_complete"):
                self.logger.error("Expected investigation_complete=true for certain confidence")
                return False

            if not response2_data.get("skip_expert_analysis"):
                self.logger.error("Expected skip_expert_analysis=true for certain confidence")
                return False

            # Verify expert analysis is marked as skipped
            expert_analysis = response2_data.get("expert_analysis", {})
            if expert_analysis.get("status") != "skipped_due_to_certain_confidence":
                self.logger.error("Expert analysis should be marked as skipped for certain confidence")
                return False

            # Check for proper investigation summary
            complete_investigation = response2_data.get("complete_investigation", {})
            if complete_investigation.get("confidence_level") != "certain":
                self.logger.error("Expected confidence_level='certain' in complete investigation")
                return False

            if complete_investigation.get("steps_taken") != 2:
                self.logger.error("Expected steps_taken=2 in complete investigation")
                return False

            # Verify next steps guidance
            next_steps = response2_data.get("next_steps", "")
            if "CERTAIN confidence" not in next_steps:
                self.logger.error("Expected 'CERTAIN confidence' in next_steps guidance")
                return False

            if "minimal fix" not in next_steps:
                self.logger.error("Expected 'minimal fix' guidance in next_steps")
                return False

            self.logger.info("    ✅ Certain confidence skipped expert analysis correctly")
            return True

        except Exception as e:
            self.logger.error(f"Obvious import error certain test failed: {e}")
            return False

    def _test_certain_always_trusted(self) -> bool:
        """Test that certain confidence is always trusted regardless of complexity"""
        try:
            self.logger.info("  1.2: Testing that certain confidence is always trusted")

            # Single step investigation with certain - should always be trusted
            self.logger.info("    1.2.1: Direct certain confidence (always trusted)")
            response, _ = self.call_mcp_tool_direct(
                "debug",
                {
                    "step": "Found the exact root cause and minimal fix for this complex issue",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,  # Final step
                    "findings": "After thorough investigation, identified that the issue is caused by method name typo in Calculator.calculate_total() - calls self.add_number() instead of self.add_numbers(). Simple fix: change line 14 from 'add_number' to 'add_numbers'.",
                    "files_checked": [self.typo_bug_file],
                    "relevant_files": [self.typo_bug_file],
                    "relevant_context": ["Calculator.calculate_total", "Calculator.add_numbers"],
                    "hypothesis": "Method name typo in calculate_total() calls non-existent add_number() instead of add_numbers()",
                    "confidence": "certain",  # Should always be trusted
                    "model": "flash",
                },
            )

            if not response:
                self.logger.error("Failed to get certain confidence response")
                return False

            response_data = self._parse_debug_response(response)
            if not response_data:
                return False

            # Verify certain is trusted regardless of complexity
            if response_data.get("status") != "certain_confidence_proceed_with_fix":
                self.logger.error("Certain confidence should always be trusted")
                return False

            if not response_data.get("skip_expert_analysis"):
                self.logger.error("Expert analysis should be skipped for certain confidence")
                return False

            # Ensure expert analysis is marked as skipped
            expert_analysis = response_data.get("expert_analysis", {})
            if expert_analysis.get("status") != "skipped_due_to_certain_confidence":
                self.logger.error("Expert analysis status should indicate certain skip")
                return False

            self.logger.info("    ✅ Certain confidence always trusted correctly")
            return True

        except Exception as e:
            self.logger.error(f"Certain always trusted test failed: {e}")
            return False

    def _test_regular_high_confidence_expert_analysis(self) -> bool:
        """Test that regular 'high' confidence still triggers expert analysis"""
        try:
            self.logger.info("  1.3: Testing that regular 'high' confidence triggers expert analysis")

            # Investigation with regular high confidence (not certain)
            self.logger.info("    1.3.1: High confidence (not certain) - should trigger expert analysis")
            response, _ = self.call_mcp_tool_direct(
                "debug",
                {
                    "step": "Identified likely root cause with strong evidence",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,  # Final step
                    "findings": "IndentationError in data_processor.py line 8 - results.append(processed) is incorrectly indented. Should align with the 'if' statement above it.",
                    "files_checked": [self.indentation_file],
                    "relevant_files": [self.indentation_file],
                    "relevant_context": ["process_data"],
                    "hypothesis": "Incorrect indentation causes IndentationError in process_data function",
                    "confidence": "high",  # Regular high confidence, NOT certain
                    "model": "flash",
                },
            )

            if not response:
                self.logger.error("Failed to get high confidence response")
                return False

            response_data = self._parse_debug_response(response)
            if not response_data:
                return False

            # Verify that regular high confidence triggers expert analysis
            if response_data.get("status") != "calling_expert_analysis":
                self.logger.error(
                    f"Expected 'calling_expert_analysis' for high confidence, got '{response_data.get('status')}'"
                )
                return False

            if response_data.get("skip_expert_analysis"):
                self.logger.error("Expert analysis should NOT be skipped for regular high confidence")
                return False

            # Verify expert analysis was called
            expert_analysis = response_data.get("expert_analysis", {})
            if not expert_analysis:
                self.logger.error("Expected expert analysis for regular high confidence")
                return False

            # Check that expert analysis has content
            if "status" not in expert_analysis:
                self.logger.error("Expert analysis should have status field")
                return False

            self.logger.info("    ✅ Regular high confidence triggers expert analysis correctly")
            return True

        except Exception as e:
            self.logger.error(f"Regular high confidence test failed: {e}")
            return False

    def _test_multi_step_investigation_certain(self) -> bool:
        """Test multi-step investigation that ends with certain confidence"""
        try:
            self.logger.info("  1.4: Testing multi-step investigation ending with certain")

            # Step 1: Start investigation
            self.logger.info("    1.4.1: Step 1 - Initial investigation")
            response1, continuation_id = self.call_mcp_tool_direct(
                "debug",
                {
                    "step": "Investigating Python syntax error in data processing module",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,
                    "findings": "IndentationError reported when running data_processor.py - 'unindent does not match any outer indentation level'",
                    "files_checked": [self.indentation_file],
                    "relevant_files": [],
                    "hypothesis": "Indentation inconsistency in Python code",
                    "confidence": "low",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start multi-step investigation")
                return False

            # Step 2: Examine code structure
            self.logger.info("    1.4.2: Step 2 - Code examination")
            response2, _ = self.call_mcp_tool_direct(
                "debug",
                {
                    "step": "Examining the indentation structure in process_data function",
                    "step_number": 2,
                    "total_steps": 3,
                    "next_step_required": True,
                    "findings": "Found the issue: line 8 'results.append(processed)' is indented incorrectly. It should align with the 'if' statement, not be at the same level as the 'for' loop.",
                    "files_checked": [self.indentation_file],
                    "relevant_files": [self.indentation_file],
                    "relevant_context": ["process_data"],
                    "hypothesis": "Line 8 has incorrect indentation level causing IndentationError",
                    "confidence": "medium",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            # Step 3: Confirm fix with certain confidence
            self.logger.info("    1.4.3: Step 3 - Confirmed fix (certain)")
            response3, _ = self.call_mcp_tool_direct(
                "debug",
                {
                    "step": "Confirmed the exact issue and simple fix",
                    "step_number": 3,
                    "total_steps": 3,
                    "next_step_required": False,  # Final step
                    "findings": "Confirmed: line 8 'results.append(processed)' needs to be indented 4 more spaces to align with line 6 'if item > 0:'. This is a simple indentation fix.",
                    "files_checked": [self.indentation_file],
                    "relevant_files": [self.indentation_file],
                    "relevant_context": ["process_data"],
                    "hypothesis": "IndentationError on line 8 due to incorrect indentation level - needs 4 more spaces",
                    "confidence": "certain",  # Final step with certain
                    "continuation_id": continuation_id,
                    "model": "flash",
                },
            )

            if not response3:
                self.logger.error("Failed to complete multi-step investigation")
                return False

            response3_data = self._parse_debug_response(response3)
            if not response3_data:
                return False

            # Validate multi-step certain response
            if response3_data.get("status") != "certain_confidence_proceed_with_fix":
                self.logger.error("Expected certain status for final step")
                return False

            if not response3_data.get("skip_expert_analysis"):
                self.logger.error("Expected expert analysis to be skipped for certain")
                return False

            # Verify investigation preserves steps (at least the current step)
            complete_investigation = response3_data.get("complete_investigation", {})
            steps_taken = complete_investigation.get("steps_taken", 0)
            if steps_taken < 1:
                self.logger.error("Expected at least 1 step in complete investigation")
                return False

            # Check that work summary includes progression
            work_summary = complete_investigation.get("work_summary", "")
            if "Total steps:" not in work_summary and "Steps taken:" not in work_summary:
                self.logger.error("Work summary should show steps information")
                return False

            self.logger.info("    ✅ Multi-step investigation with certain ending successful")
            return True

        except Exception as e:
            self.logger.error(f"Multi-step investigation certain test failed: {e}")
            return False

    def call_mcp_tool_direct(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool directly in-process to maintain conversation memory"""
        try:
            # Get the tool instance
            if tool_name not in self._tools:
                self.logger.error(f"Tool '{tool_name}' not found in available tools")
                return None, None

            tool = self._tools[tool_name]

            # Execute the tool with proper async handling
            loop = self._get_event_loop()

            # Call the tool's execute method
            result = loop.run_until_complete(tool.execute(params))

            if not result or len(result) == 0:
                self.logger.error(f"Tool '{tool_name}' returned empty result")
                return None, None

            # Extract the text content from the result
            response_text = result[0].text if hasattr(result[0], "text") else str(result[0])

            # Extract continuation_id from debug response if present
            continuation_id = self._extract_debug_continuation_id(response_text)

            return response_text, continuation_id

        except Exception as e:
            self.logger.error(f"Failed to call tool '{tool_name}' directly: {e}")
            return None, None

    def _extract_debug_continuation_id(self, response_text: str) -> Optional[str]:
        """Extract continuation_id from debug response"""
        try:
            response_data = json.loads(response_text)
            return response_data.get("continuation_id")
        except json.JSONDecodeError as e:
            self.logger.debug(f"Failed to parse response for debug continuation_id: {e}")
            return None

    def _parse_debug_response(self, response_text: str) -> dict:
        """Parse debug tool JSON response"""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse debug response as JSON: {e}")
            self.logger.error(f"Response text: {response_text[:500]}...")
            return {}

    def _validate_investigation_response(
        self,
        response_data: dict,
        expected_step: int,
        expected_next_required: bool,
        expected_status: str,
    ) -> bool:
        """Validate debug investigation response structure"""
        try:
            # Check status
            if response_data.get("status") != expected_status:
                self.logger.error(f"Expected status '{expected_status}', got '{response_data.get('status')}'")
                return False

            # Check step number
            if response_data.get("step_number") != expected_step:
                self.logger.error(f"Expected step_number {expected_step}, got {response_data.get('step_number')}")
                return False

            # Check next_step_required
            if response_data.get("next_step_required") != expected_next_required:
                self.logger.error(
                    f"Expected next_step_required {expected_next_required}, got {response_data.get('next_step_required')}"
                )
                return False

            # Basic structure checks
            if "investigation_status" not in response_data:
                self.logger.error("Missing investigation_status in response")
                return False

            if not response_data.get("next_steps"):
                self.logger.error("Missing next_steps guidance in response")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating investigation response: {e}")
            return False
