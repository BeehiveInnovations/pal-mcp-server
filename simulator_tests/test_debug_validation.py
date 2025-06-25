#!/usr/bin/env python3
"""
DebugWorkflow Tool Validation Test

Tests the debug tool's capabilities using the new workflow architecture.
This validates that the new workflow-based implementation maintains
all the functionality of the original debug tool.
"""

import json
from typing import Optional

from .conversation_base_test import ConversationBaseTest


class DebugValidationTest(ConversationBaseTest):
    """Test debug tool with new workflow architecture"""

    @property
    def test_name(self) -> str:
        return "debug_validation"

    @property
    def test_description(self) -> str:
        return "Debug tool validation with new workflow architecture"

    def run_test(self) -> bool:
        """Test debug tool capabilities"""
        # Set up the test environment
        self.setUp()

        try:
            self.logger.info("Test: DebugWorkflow tool validation (new architecture)")

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

            # Test 4: Certain confidence behavior
            if not self._test_certain_confidence():
                return False

            # Test 5: Context-aware file embedding
            if not self._test_context_aware_file_embedding():
                return False

            # Test 6: Multi-step file context optimization
            if not self._test_multi_step_file_context():
                return False

            self.logger.info("  ✅ All debug validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"DebugWorkflow validation test failed: {e}")
            return False

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

            # Validate step 1 response structure - expect pause_for_investigation for next_step_required=True
            if not self._validate_step_response(response1_data, 1, 4, True, "pause_for_investigation"):
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
                    "relevant_context": ["SessionManager.cleanup_expired_sessions"],
                    "hypothesis": "Dictionary is being modified during iteration causing RuntimeError",
                    "confidence": "high",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue investigation to step 2")
                return False

            response2_data = self._parse_debug_response(response2)
            if not self._validate_step_response(response2_data, 2, 4, True, "pause_for_investigation"):
                return False

            # Check investigation status tracking
            investigation_status = response2_data.get("investigation_status", {})
            if investigation_status.get("files_checked", 0) < 2:
                self.logger.error("Files checked count not properly tracked")
                return False

            if investigation_status.get("relevant_context", 0) != 1:
                self.logger.error("Relevant context not properly tracked")
                return False

            if investigation_status.get("current_confidence") != "high":
                self.logger.error("Confidence level not properly tracked")
                return False

            self.logger.info("    ✅ Step 2 successful with proper tracking")

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
                    "relevant_context": ["DataProcessor.process_batch"],
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
            if not self._validate_step_response(response3_data, 3, 4, True, "pause_for_investigation"):
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
                        "relevant_context": ["SessionManager.cleanup_expired_sessions"],
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
                    "relevant_context": ["SessionManager.cleanup_expired_sessions"],
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

            # Validate final response structure - expect calling_expert_analysis for next_step_required=False
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
            analysis_text = json.dumps(expert_analysis, ensure_ascii=False).lower()

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
            if not complete_investigation.get("relevant_context"):
                self.logger.error("Missing relevant context in complete investigation")
                return False

            if "SessionManager.cleanup_expired_sessions" not in complete_investigation["relevant_context"]:
                self.logger.error("Expected method not found in investigation summary")
                return False

            self.logger.info("    ✅ Complete investigation with expert analysis successful")
            return True

        except Exception as e:
            self.logger.error(f"Complete investigation test failed: {e}")
            return False

    def _test_certain_confidence(self) -> bool:
        """Test certain confidence behavior - should skip expert analysis"""
        try:
            self.logger.info("  1.4: Testing certain confidence behavior")

            # Test certain confidence - should skip expert analysis
            self.logger.info("    1.4.1: Certain confidence investigation")
            response_certain, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "I have confirmed the exact root cause with 100% certainty: dictionary modification during iteration.",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,  # Final step
                    "findings": "The bug is on line 44-47: for loop iterates over dict.items() while del modifies the dict inside the loop. Fix is simple: collect expired IDs first, then delete after iteration.",
                    "files_checked": [self.buggy_file],
                    "relevant_files": [self.buggy_file],
                    "relevant_context": ["SessionManager.cleanup_expired_sessions"],
                    "hypothesis": "Dictionary modification during iteration causes RuntimeError - fix is straightforward",
                    "confidence": "certain",  # This should skip expert analysis
                    "model": "flash",
                },
            )

            if not response_certain:
                self.logger.error("Failed to test certain confidence")
                return False

            response_certain_data = self._parse_debug_response(response_certain)
            if not response_certain_data:
                return False

            # Validate certain confidence response - should skip expert analysis
            if response_certain_data.get("status") != "certain_confidence_proceed_with_fix":
                self.logger.error(
                    f"Expected status 'certain_confidence_proceed_with_fix', got '{response_certain_data.get('status')}'"
                )
                return False

            if not response_certain_data.get("skip_expert_analysis"):
                self.logger.error("Expected skip_expert_analysis=true for certain confidence")
                return False

            expert_analysis = response_certain_data.get("expert_analysis", {})
            if expert_analysis.get("status") != "skipped_due_to_certain_confidence":
                self.logger.error("Expert analysis should be skipped for certain confidence")
                return False

            self.logger.info("    ✅ Certain confidence behavior working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Certain confidence test failed: {e}")
            return False

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool in-process - override for debug-specific response handling"""
        # Use in-process implementation to maintain conversation memory
        response_text, _ = self.call_mcp_tool_direct(tool_name, params)

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

            # Check next_steps guidance
            if not response_data.get("next_steps"):
                self.logger.error("Missing next_steps guidance in response")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating step response: {e}")
            return False

    def _test_context_aware_file_embedding(self) -> bool:
        """Test context-aware file embedding optimization"""
        try:
            self.logger.info("  1.5: Testing context-aware file embedding")

            # Create multiple test files for context testing
            file1_content = """#!/usr/bin/env python3
def process_data(data):
    \"\"\"Process incoming data\"\"\"
    result = []
    for item in data:
        if item.get('valid'):
            result.append(item['value'])
    return result
"""

            file2_content = """#!/usr/bin/env python3
def validate_input(data):
    \"\"\"Validate input data\"\"\"
    if not isinstance(data, list):
        raise ValueError("Data must be a list")

    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Items must be dictionaries")
        if 'value' not in item:
            raise ValueError("Items must have 'value' key")

    return True
"""

            # Create test files
            file1 = self.create_additional_test_file("data_processor.py", file1_content)
            file2 = self.create_additional_test_file("validator.py", file2_content)

            # Test 1: New conversation, intermediate step - should only reference files
            self.logger.info("    1.5.1: New conversation intermediate step (should reference only)")
            response1, continuation_id = self.call_mcp_tool(
                "debug",
                {
                    "step": "Starting investigation of data processing pipeline",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,  # Intermediate step
                    "findings": "Initial analysis of data processing components",
                    "files_checked": [file1, file2],
                    "relevant_files": [file1],  # This should be referenced, not embedded
                    "relevant_context": ["process_data"],
                    "hypothesis": "Investigating data flow",
                    "confidence": "low",
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start context-aware file embedding test")
                return False

            response1_data = self._parse_debug_response(response1)
            if not response1_data:
                return False

            # Check file context - should be reference_only for intermediate step
            file_context = response1_data.get("file_context", {})
            if file_context.get("type") != "reference_only":
                self.logger.error(f"Expected reference_only file context, got: {file_context.get('type')}")
                return False

            if "Files referenced but not embedded" not in file_context.get("context_optimization", ""):
                self.logger.error("Expected context optimization message for reference_only")
                return False

            self.logger.info("    ✅ Intermediate step correctly uses reference_only file context")

            # Test 2: Intermediate step with continuation - should still only reference
            self.logger.info("    1.5.2: Intermediate step with continuation (should reference only)")
            response2, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Continuing investigation with more detailed analysis",
                    "step_number": 2,
                    "total_steps": 3,
                    "next_step_required": True,  # Still intermediate
                    "continuation_id": continuation_id,
                    "findings": "Found potential issues in validation logic",
                    "files_checked": [file1, file2],
                    "relevant_files": [file1, file2],  # Both files referenced
                    "relevant_context": ["process_data", "validate_input"],
                    "hypothesis": "Validation might be too strict",
                    "confidence": "medium",
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            response2_data = self._parse_debug_response(response2)
            if not response2_data:
                return False

            # Check file context - should still be reference_only
            file_context2 = response2_data.get("file_context", {})
            if file_context2.get("type") != "reference_only":
                self.logger.error(f"Expected reference_only file context for step 2, got: {file_context2.get('type')}")
                return False

            # Should include reference note
            if not file_context2.get("note"):
                self.logger.error("Expected file reference note for intermediate step")
                return False

            reference_note = file_context2.get("note", "")
            if "data_processor.py" not in reference_note or "validator.py" not in reference_note:
                self.logger.error("File reference note should mention both files")
                return False

            self.logger.info("    ✅ Intermediate step with continuation correctly uses reference_only")

            # Test 3: Final step - should embed files for expert analysis
            self.logger.info("    1.5.3: Final step (should embed files)")
            response3, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Investigation complete - identified the root cause",
                    "step_number": 3,
                    "total_steps": 3,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Root cause: validator is rejecting valid data due to strict type checking",
                    "files_checked": [file1, file2],
                    "relevant_files": [file1, file2],  # Should be fully embedded
                    "relevant_context": ["process_data", "validate_input"],
                    "hypothesis": "Validation logic is too restrictive for valid edge cases",
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response3:
                self.logger.error("Failed to complete to final step")
                return False

            response3_data = self._parse_debug_response(response3)
            if not response3_data:
                return False

            # Check file context - should be fully_embedded for final step
            file_context3 = response3_data.get("file_context", {})
            if file_context3.get("type") != "fully_embedded":
                self.logger.error(
                    f"Expected fully_embedded file context for final step, got: {file_context3.get('type')}"
                )
                return False

            if "Full file content embedded for expert analysis" not in file_context3.get("context_optimization", ""):
                self.logger.error("Expected expert analysis optimization message for fully_embedded")
                return False

            # Should show files embedded count
            files_embedded = file_context3.get("files_embedded", 0)
            if files_embedded == 0:
                # This is OK - files might already be in conversation history
                self.logger.info(
                    "    ℹ️ Files embedded count is 0 - files already in conversation history (smart deduplication)"
                )
            else:
                self.logger.info(f"    ✅ Files embedded count: {files_embedded}")

            self.logger.info("    ✅ Final step correctly uses fully_embedded file context")

            # Verify expert analysis was called for final step
            if response3_data.get("status") != "calling_expert_analysis":
                self.logger.error("Final step should trigger expert analysis")
                return False

            if "expert_analysis" not in response3_data:
                self.logger.error("Expert analysis should be present in final step")
                return False

            self.logger.info("    ✅ Context-aware file embedding test completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Context-aware file embedding test failed: {e}")
            return False

    def _test_multi_step_file_context(self) -> bool:
        """Test multi-step workflow with proper file context transitions"""
        try:
            self.logger.info("  1.6: Testing multi-step file context optimization")

            # Create a complex scenario with multiple files
            config_content = """#!/usr/bin/env python3
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')
DEBUG_MODE = os.getenv('DEBUG', 'False').lower() == 'true'
MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', '10'))

# Bug: This will cause issues when MAX_CONNECTIONS is not a valid integer
CACHE_SIZE = MAX_CONNECTIONS * 2  # Problematic if MAX_CONNECTIONS is invalid
"""

            server_content = """#!/usr/bin/env python3
from config import DATABASE_URL, DEBUG_MODE, CACHE_SIZE
import sqlite3

class DatabaseServer:
    def __init__(self):
        self.connection_pool = []
        self.cache_size = CACHE_SIZE  # This will fail if CACHE_SIZE is invalid

    def connect(self):
        try:
            conn = sqlite3.connect(DATABASE_URL)
            self.connection_pool.append(conn)
            return conn
        except Exception as e:
            print(f"Connection failed: {e}")
            return None
"""

            # Create test files
            config_file = self.create_additional_test_file("config.py", config_content)
            server_file = self.create_additional_test_file("database_server.py", server_content)

            # Step 1: Start investigation (new conversation)
            self.logger.info("    1.6.1: Step 1 - Start investigation")
            response1, continuation_id = self.call_mcp_tool(
                "debug",
                {
                    "step": "Investigating application startup failures in production environment",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Application fails to start with configuration errors",
                    "files_checked": [config_file],
                    "relevant_files": [config_file],
                    "relevant_context": [],
                    "hypothesis": "Configuration issue causing startup failure",
                    "confidence": "low",
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start multi-step file context test")
                return False

            response1_data = self._parse_debug_response(response1)

            # Validate step 1 - should use reference_only
            file_context1 = response1_data.get("file_context", {})
            if file_context1.get("type") != "reference_only":
                self.logger.error("Step 1 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 1: reference_only file context")

            # Step 2: Expand investigation
            self.logger.info("    1.6.2: Step 2 - Expand investigation")
            response2, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Found configuration issue - investigating database server initialization",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                    "findings": "MAX_CONNECTIONS environment variable contains invalid value, causing CACHE_SIZE calculation to fail",
                    "files_checked": [config_file, server_file],
                    "relevant_files": [config_file, server_file],
                    "relevant_context": ["DatabaseServer.__init__"],
                    "hypothesis": "Invalid environment variable causing integer conversion error",
                    "confidence": "medium",
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            response2_data = self._parse_debug_response(response2)

            # Validate step 2 - should still use reference_only
            file_context2 = response2_data.get("file_context", {})
            if file_context2.get("type") != "reference_only":
                self.logger.error("Step 2 should use reference_only file context")
                return False

            # Should reference both files
            reference_note = file_context2.get("note", "")
            if "config.py" not in reference_note or "database_server.py" not in reference_note:
                self.logger.error("Step 2 should reference both files in note")
                return False

            self.logger.info("    ✅ Step 2: reference_only file context with multiple files")

            # Step 3: Deep analysis
            self.logger.info("    1.6.3: Step 3 - Deep analysis")
            response3, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Analyzing the exact error propagation path and impact",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                    "findings": "Error occurs in config.py line 8 when MAX_CONNECTIONS is not numeric, then propagates to DatabaseServer.__init__",
                    "files_checked": [config_file, server_file],
                    "relevant_files": [config_file, server_file],
                    "relevant_context": ["DatabaseServer.__init__"],
                    "hypothesis": "Need proper error handling and validation for environment variables",
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response3:
                self.logger.error("Failed to continue to step 3")
                return False

            response3_data = self._parse_debug_response(response3)

            # Validate step 3 - should still use reference_only
            file_context3 = response3_data.get("file_context", {})
            if file_context3.get("type") != "reference_only":
                self.logger.error("Step 3 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 3: reference_only file context")

            # Step 4: Final analysis with expert consultation
            self.logger.info("    1.6.4: Step 4 - Final step with expert analysis")
            response4, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Investigation complete - root cause identified with solution",
                    "step_number": 4,
                    "total_steps": 4,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Root cause: config.py assumes MAX_CONNECTIONS env var is always a valid integer. Fix: add try/except with default value and proper validation.",
                    "files_checked": [config_file, server_file],
                    "relevant_files": [config_file, server_file],
                    "relevant_context": ["DatabaseServer.__init__"],
                    "hypothesis": "Environment variable validation needed with proper error handling",
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response4:
                self.logger.error("Failed to complete to final step")
                return False

            response4_data = self._parse_debug_response(response4)

            # Validate step 4 - should use fully_embedded for expert analysis
            file_context4 = response4_data.get("file_context", {})
            if file_context4.get("type") != "fully_embedded":
                self.logger.error("Step 4 (final) should use fully_embedded file context")
                return False

            if "expert analysis" not in file_context4.get("context_optimization", "").lower():
                self.logger.error("Final step should mention expert analysis in context optimization")
                return False

            # Verify expert analysis was triggered
            if response4_data.get("status") != "calling_expert_analysis":
                self.logger.error("Final step should trigger expert analysis")
                return False

            # Check that expert analysis has file context
            expert_analysis = response4_data.get("expert_analysis", {})
            if not expert_analysis:
                self.logger.error("Expert analysis should be present in final step")
                return False

            self.logger.info("    ✅ Step 4: fully_embedded file context with expert analysis")

            # Validate the complete workflow progression
            progression_summary = {
                "step_1": "reference_only (new conversation, intermediate)",
                "step_2": "reference_only (continuation, intermediate)",
                "step_3": "reference_only (continuation, intermediate)",
                "step_4": "fully_embedded (continuation, final)",
            }

            self.logger.info("    📋 File context progression:")
            for step, context_type in progression_summary.items():
                self.logger.info(f"      {step}: {context_type}")

            self.logger.info("    ✅ Multi-step file context optimization test completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Multi-step file context test failed: {e}")
            return False
