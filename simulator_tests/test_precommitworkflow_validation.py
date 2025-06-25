#!/usr/bin/env python3
"""
PrecommitWorkflow Tool Validation Test

Tests the precommit tool's capabilities using the new workflow architecture.
This validates that the workflow-based pre-commit validation provides step-by-step
analysis with proper investigation guidance and expert analysis integration.
"""

import json
from typing import Optional

from .conversation_base_test import ConversationBaseTest


class PrecommitWorkflowValidationTest(ConversationBaseTest):
    """Test precommit tool with new workflow architecture"""

    @property
    def test_name(self) -> str:
        return "precommit_validation"

    @property
    def test_description(self) -> str:
        return "PrecommitWorkflow tool validation with new workflow architecture"

    def run_test(self) -> bool:
        """Test precommit tool capabilities"""
        # Set up the test environment
        self.setUp()

        try:
            self.logger.info("Test: PrecommitWorkflow tool validation (new architecture)")

            # Create test git repository structure with changes
            self._create_test_git_changes()

            # Test 1: Single validation session with multiple steps
            if not self._test_single_validation_session():
                return False

            # Test 2: Validation with backtracking
            if not self._test_validation_with_backtracking():
                return False

            # Test 3: Complete validation with expert analysis
            if not self._test_complete_validation_with_analysis():
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

            self.logger.info("  ✅ All precommit validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"PrecommitWorkflow validation test failed: {e}")
            return False

    def _create_test_git_changes(self):
        """Create test files simulating git changes for pre-commit validation"""
        # Create a new API endpoint with potential security issues
        new_api_code = """#!/usr/bin/env python3
from flask import Flask, request, jsonify
import sqlite3
import os

app = Flask(__name__)

@app.route('/api/user/<user_id>', methods=['GET'])
def get_user(user_id):
    \"\"\"Get user information by ID\"\"\"
    # Potential SQL injection vulnerability
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # BUG: Direct string interpolation creates SQL injection risk
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)

    result = cursor.fetchone()
    conn.close()

    if result:
        return jsonify({
            'id': result[0],
            'username': result[1],
            'email': result[2],
            'password_hash': result[3]  # Security issue: exposing password hash
        })
    else:
        return jsonify({'error': 'User not found'}), 404

@app.route('/api/admin/users', methods=['GET'])
def list_all_users():
    \"\"\"Admin endpoint to list all users\"\"\"
    # Missing authentication check
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email FROM users")

    users = []
    for row in cursor.fetchall():
        users.append({
            'id': row[0],
            'username': row[1],
            'email': row[2]
        })

    conn.close()
    return jsonify(users)

if __name__ == '__main__':
    # Debug mode in production is a security risk
    app.run(debug=True, host='0.0.0.0')
"""

        # Create configuration file with issues
        config_code = """#!/usr/bin/env python3
import os

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///users.db')

# Security settings
SECRET_KEY = "hardcoded-secret-key-123"  # Security issue: hardcoded secret
DEBUG_MODE = True  # Should be environment-based

# API settings
API_RATE_LIMIT = 1000  # Very high, no rate limiting effectively
MAX_FILE_UPLOAD = 50 * 1024 * 1024  # 50MB - quite large

# Missing important security headers configuration
CORS_ORIGINS = "*"  # Security issue: allows all origins
"""

        # Create test files
        self.api_file = self.create_additional_test_file("api_endpoints.py", new_api_code)
        self.config_file = self.create_additional_test_file("config.py", config_code)
        self.logger.info(f"  ✅ Created test files: {self.api_file}, {self.config_file}")

        # Create change description
        change_description = """COMMIT DESCRIPTION:
Added new user API endpoints and configuration for user management system.

CHANGES MADE:
- Added GET /api/user/<user_id> endpoint to retrieve user information
- Added GET /api/admin/users endpoint for admin user listing
- Added configuration file with database and security settings
- Set up Flask application with basic routing

REQUIREMENTS:
- User data should be retrievable by ID
- Admin should be able to list all users
- System should be configurable via environment variables
- Security should be properly implemented
"""

        self.changes_file = self.create_additional_test_file("commit_description.txt", change_description)
        self.logger.info(f"  ✅ Created change description: {self.changes_file}")

    def _test_single_validation_session(self) -> bool:
        """Test a complete validation session with multiple steps"""
        try:
            self.logger.info("  1.1: Testing single validation session")

            # Step 1: Start validation
            self.logger.info("    1.1.1: Step 1 - Initial validation plan")
            response1, continuation_id = self.call_mcp_tool(
                "precommit",
                {
                    "step": "I need to perform comprehensive pre-commit validation for new API endpoints. Let me start by analyzing the changes and identifying potential issues.",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "New user API endpoints and configuration added. Need to examine for security, performance, and best practices.",
                    "files_checked": [self.changes_file],
                    "relevant_files": [self.changes_file],
                    "path": self.test_dir,  # Required for step 1
                    "review_type": "full",
                    "severity_filter": "all",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to get initial validation response")
                return False

            # Parse and validate JSON response
            response1_data = self._parse_precommit_response(response1)
            if not response1_data:
                return False

            # Validate step 1 response structure - expect pause_for_validation for next_step_required=True
            if not self._validate_step_response(response1_data, 1, 4, True, "pause_for_validation"):
                return False

            self.logger.info(f"    ✅ Step 1 successful, continuation_id: {continuation_id}")

            # Step 2: Examine the code for issues
            self.logger.info("    1.1.2: Step 2 - Code examination")
            response2, _ = self.call_mcp_tool(
                "precommit",
                {
                    "step": "Now examining the API endpoint implementation and configuration for security vulnerabilities and best practices violations.",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Found multiple critical security issues: SQL injection vulnerability in get_user(), hardcoded secrets in config, missing authentication, and password hash exposure.",
                    "files_checked": [self.changes_file, self.api_file, self.config_file],
                    "relevant_files": [self.api_file, self.config_file],
                    "relevant_context": ["get_user", "list_all_users"],
                    "issues_found": [
                        {"severity": "critical", "description": "SQL injection vulnerability in user lookup"},
                        {"severity": "high", "description": "Hardcoded secret key in configuration"},
                        {"severity": "high", "description": "Password hash exposed in API response"},
                        {"severity": "medium", "description": "Missing authentication on admin endpoint"},
                    ],
                    "assessment": "Multiple critical security vulnerabilities found requiring immediate fixes",
                    "confidence": "high",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue validation to step 2")
                return False

            response2_data = self._parse_precommit_response(response2)
            if not self._validate_step_response(response2_data, 2, 4, True, "pause_for_validation"):
                return False

            # Check validation status tracking
            validation_status = response2_data.get("validation_status", {})
            if validation_status.get("files_checked", 0) < 3:
                self.logger.error("Files checked count not properly tracked")
                return False

            if validation_status.get("issues_identified", 0) != 4:
                self.logger.error("Issues found not properly tracked")
                return False

            if validation_status.get("assessment_confidence") != "high":
                self.logger.error("Confidence level not properly tracked")
                return False

            self.logger.info("    ✅ Step 2 successful with proper tracking")

            # Store continuation_id for next test
            self.validation_continuation_id = continuation_id
            return True

        except Exception as e:
            self.logger.error(f"Single validation session test failed: {e}")
            return False

    def _test_validation_with_backtracking(self) -> bool:
        """Test validation with backtracking to revise findings"""
        try:
            self.logger.info("  1.2: Testing validation with backtracking")

            # Start a new validation for testing backtracking
            self.logger.info("    1.2.1: Start validation for backtracking test")
            response1, continuation_id = self.call_mcp_tool(
                "precommit",
                {
                    "step": "Validating database connection optimization changes",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial analysis shows database connection pooling implementation",
                    "files_checked": ["/db/connection.py"],
                    "relevant_files": ["/db/connection.py"],
                    "path": self.test_dir,
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start backtracking test validation")
                return False

            # Step 2: Wrong direction
            self.logger.info("    1.2.2: Step 2 - Wrong validation focus")
            response2, _ = self.call_mcp_tool(
                "precommit",
                {
                    "step": "Focusing on connection pool size optimization",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Connection pool configuration seems reasonable, might be looking in wrong place",
                    "files_checked": ["/db/connection.py", "/config/database.py"],
                    "relevant_files": [],
                    "assessment": "Database configuration appears correct",
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
                "precommit",
                {
                    "step": "Backtracking - the issue might not be database configuration. Let me examine the actual SQL queries and data access patterns instead.",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Found inefficient N+1 query pattern in user data loading causing performance issues",
                    "files_checked": ["/models/user.py"],
                    "relevant_files": ["/models/user.py"],
                    "relevant_context": ["User.load_profile"],
                    "issues_found": [
                        {"severity": "medium", "description": "N+1 query pattern in user profile loading"}
                    ],
                    "assessment": "Query pattern optimization needed for performance",
                    "confidence": "medium",
                    "backtrack_from_step": 2,  # Backtrack from step 2
                    "continuation_id": continuation_id,
                },
            )

            if not response3:
                self.logger.error("Failed to backtrack")
                return False

            response3_data = self._parse_precommit_response(response3)
            if not self._validate_step_response(response3_data, 3, 4, True, "pause_for_validation"):
                return False

            self.logger.info("    ✅ Backtracking working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Backtracking test failed: {e}")
            return False

    def _test_complete_validation_with_analysis(self) -> bool:
        """Test complete validation ending with expert analysis"""
        try:
            self.logger.info("  1.3: Testing complete validation with expert analysis")

            # Use the continuation from first test
            continuation_id = getattr(self, "validation_continuation_id", None)
            if not continuation_id:
                # Start fresh if no continuation available
                self.logger.info("    1.3.0: Starting fresh validation")
                response0, continuation_id = self.call_mcp_tool(
                    "precommit",
                    {
                        "step": "Validating the security fixes for API endpoints",
                        "step_number": 1,
                        "total_steps": 2,
                        "next_step_required": True,
                        "findings": "Found critical security vulnerabilities in API implementation",
                        "files_checked": [self.api_file],
                        "relevant_files": [self.api_file],
                        "relevant_context": ["get_user", "list_all_users"],
                        "issues_found": [{"severity": "critical", "description": "SQL injection vulnerability"}],
                        "path": self.test_dir,
                    },
                )
                if not response0 or not continuation_id:
                    self.logger.error("Failed to start fresh validation")
                    return False

            # Final step - trigger expert analysis
            self.logger.info("    1.3.1: Final step - complete validation")
            response_final, _ = self.call_mcp_tool(
                "precommit",
                {
                    "step": "Validation complete. I have identified all critical security issues and missing safeguards in the new API endpoints.",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step - triggers expert analysis
                    "findings": "Comprehensive analysis complete: SQL injection, hardcoded secrets, missing authentication, password exposure, and insecure defaults all identified with specific fixes needed.",
                    "files_checked": [self.api_file, self.config_file],
                    "relevant_files": [self.api_file, self.config_file],
                    "relevant_context": ["get_user", "list_all_users", "SECRET_KEY", "DEBUG_MODE"],
                    "issues_found": [
                        {"severity": "critical", "description": "SQL injection vulnerability in user lookup query"},
                        {"severity": "high", "description": "Hardcoded secret key exposes application security"},
                        {"severity": "high", "description": "Password hash exposed in API response"},
                        {"severity": "medium", "description": "Missing authentication on admin endpoint"},
                        {"severity": "medium", "description": "Debug mode enabled in production configuration"},
                    ],
                    "confidence": "high",
                    "continuation_id": continuation_id,
                    "model": "flash",  # Use flash for expert analysis
                },
            )

            if not response_final:
                self.logger.error("Failed to complete validation")
                return False

            response_final_data = self._parse_precommit_response(response_final)
            if not response_final_data:
                return False

            # Validate final response structure - expect calling_expert_analysis for next_step_required=False
            if response_final_data.get("status") != "calling_expert_analysis":
                self.logger.error(
                    f"Expected status 'calling_expert_analysis', got '{response_final_data.get('status')}'"
                )
                return False

            if not response_final_data.get("validation_complete"):
                self.logger.error("Expected validation_complete=true for final step")
                return False

            # Check for expert analysis
            if "expert_analysis" not in response_final_data:
                self.logger.error("Missing expert_analysis in final response")
                return False

            expert_analysis = response_final_data.get("expert_analysis", {})

            # Check for expected analysis content (checking common patterns)
            analysis_text = json.dumps(expert_analysis, ensure_ascii=False).lower()

            # Look for security issue identification
            security_indicators = ["sql", "injection", "security", "hardcoded", "secret", "authentication"]
            found_indicators = sum(1 for indicator in security_indicators if indicator in analysis_text)

            if found_indicators >= 3:
                self.logger.info("    ✅ Expert analysis identified security issues correctly")
            else:
                self.logger.warning(
                    f"    ⚠️ Expert analysis may not have fully identified security issues (found {found_indicators}/6 indicators)"
                )

            # Check complete validation summary
            if "complete_validation" not in response_final_data:
                self.logger.error("Missing complete_validation in final response")
                return False

            complete_validation = response_final_data["complete_validation"]
            if not complete_validation.get("relevant_context"):
                self.logger.error("Missing relevant context in complete validation")
                return False

            if "get_user" not in complete_validation["relevant_context"]:
                self.logger.error("Expected function not found in validation summary")
                return False

            self.logger.info("    ✅ Complete validation with expert analysis successful")
            return True

        except Exception as e:
            self.logger.error(f"Complete validation test failed: {e}")
            return False

    def _test_certain_confidence(self) -> bool:
        """Test certain confidence behavior - should skip expert analysis"""
        try:
            self.logger.info("  1.4: Testing certain confidence behavior")

            # Test certain confidence - should skip expert analysis
            self.logger.info("    1.4.1: Certain confidence validation")
            response_certain, _ = self.call_mcp_tool(
                "precommit",
                {
                    "step": "I have confirmed all security issues with 100% certainty: SQL injection, hardcoded secrets, and missing authentication.",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,  # Final step
                    "findings": "All critical issues identified: parameterized queries needed, environment variables for secrets, authentication middleware required, and debug mode must be disabled for production.",
                    "files_checked": [self.api_file, self.config_file],
                    "relevant_files": [self.api_file, self.config_file],
                    "relevant_context": ["get_user", "list_all_users"],
                    "issues_found": [
                        {
                            "severity": "critical",
                            "description": "SQL injection vulnerability - fix with parameterized queries",
                        },
                        {"severity": "high", "description": "Hardcoded secret - use environment variables"},
                        {"severity": "medium", "description": "Missing authentication - add middleware"},
                    ],
                    "assessment": "Critical security vulnerabilities identified with clear fixes - changes must not be committed until resolved",
                    "confidence": "certain",  # This should skip expert analysis
                    "path": self.test_dir,
                    "model": "flash",
                },
            )

            if not response_certain:
                self.logger.error("Failed to test certain confidence")
                return False

            response_certain_data = self._parse_precommit_response(response_certain)
            if not response_certain_data:
                return False

            # Validate certain confidence response - should skip expert analysis
            if response_certain_data.get("status") != "validation_complete_ready_for_commit":
                self.logger.error(
                    f"Expected status 'validation_complete_ready_for_commit', got '{response_certain_data.get('status')}'"
                )
                return False

            if not response_certain_data.get("skip_expert_analysis"):
                self.logger.error("Expected skip_expert_analysis=true for certain confidence")
                return False

            expert_analysis = response_certain_data.get("expert_analysis", {})
            if expert_analysis.get("status") != "skipped_due_to_certain_validation_confidence":
                self.logger.error("Expert analysis should be skipped for certain confidence")
                return False

            self.logger.info("    ✅ Certain confidence behavior working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Certain confidence test failed: {e}")
            return False

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool in-process - override for precommit-specific response handling"""
        # Use in-process implementation to maintain conversation memory
        response_text, _ = self.call_mcp_tool_direct(tool_name, params)

        if not response_text:
            return None, None

        # Extract continuation_id from precommit response specifically
        continuation_id = self._extract_precommit_continuation_id(response_text)

        return response_text, continuation_id

    def _extract_precommit_continuation_id(self, response_text: str) -> Optional[str]:
        """Extract continuation_id from precommit response"""
        try:
            # Parse the response
            response_data = json.loads(response_text)
            return response_data.get("continuation_id")

        except json.JSONDecodeError as e:
            self.logger.debug(f"Failed to parse response for precommit continuation_id: {e}")
            return None

    def _parse_precommit_response(self, response_text: str) -> dict:
        """Parse precommit tool JSON response"""
        try:
            # Parse the response - it should be direct JSON
            return json.loads(response_text)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse precommit response as JSON: {e}")
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
        """Validate a precommit validation step response structure"""
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

            # Check validation_status exists
            if "validation_status" not in response_data:
                self.logger.error("Missing validation_status in response")
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
            auth_file_content = """#!/usr/bin/env python3
from functools import wraps
from flask import request, jsonify

def require_auth(f):
    \"\"\"Authentication decorator\"\"\"
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No token provided'}), 401

        # Validate token here
        if not validate_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)
    return decorated_function

def validate_token(token):
    \"\"\"Validate authentication token\"\"\"
    # Token validation logic
    return token.startswith('Bearer ')
"""

            middleware_file_content = """#!/usr/bin/env python3
from flask import Flask, request, g
import time

def add_security_headers(app):
    \"\"\"Add security headers to all responses\"\"\"
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

def rate_limiting_middleware(app):
    \"\"\"Basic rate limiting\"\"\"
    @app.before_request
    def limit_remote_addr():
        # Simple rate limiting logic
        pass
"""

            # Create test files
            auth_file = self.create_additional_test_file("auth.py", auth_file_content)
            middleware_file = self.create_additional_test_file("middleware.py", middleware_file_content)

            # Test 1: New conversation, intermediate step - should only reference files
            self.logger.info("    1.5.1: New conversation intermediate step (should reference only)")
            response1, continuation_id = self.call_mcp_tool(
                "precommit",
                {
                    "step": "Starting validation of new authentication and security middleware",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,  # Intermediate step
                    "findings": "Initial analysis of authentication and middleware components",
                    "files_checked": [auth_file, middleware_file],
                    "relevant_files": [auth_file],  # This should be referenced, not embedded
                    "relevant_context": ["require_auth"],
                    "assessment": "Investigating security implementation",
                    "confidence": "low",
                    "path": self.test_dir,
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start context-aware file embedding test")
                return False

            response1_data = self._parse_precommit_response(response1)
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
                "precommit",
                {
                    "step": "Continuing validation with detailed security analysis",
                    "step_number": 2,
                    "total_steps": 3,
                    "next_step_required": True,  # Still intermediate
                    "continuation_id": continuation_id,
                    "findings": "Found potential issues in token validation and missing security headers",
                    "files_checked": [auth_file, middleware_file],
                    "relevant_files": [auth_file, middleware_file],  # Both files referenced
                    "relevant_context": ["require_auth", "validate_token", "add_security_headers"],
                    "issues_found": [
                        {"severity": "medium", "description": "Basic token validation might be insufficient"}
                    ],
                    "assessment": "Security implementation needs improvement",
                    "confidence": "medium",
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            response2_data = self._parse_precommit_response(response2)
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
            if "auth.py" not in reference_note or "middleware.py" not in reference_note:
                self.logger.error("File reference note should mention both files")
                return False

            self.logger.info("    ✅ Intermediate step with continuation correctly uses reference_only")

            # Test 3: Final step - should embed files for expert analysis
            self.logger.info("    1.5.3: Final step (should embed files)")
            response3, _ = self.call_mcp_tool(
                "precommit",
                {
                    "step": "Validation complete - identified security gaps and improvement areas",
                    "step_number": 3,
                    "total_steps": 3,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Security implementation has several gaps: token validation is basic, missing CSRF protection, and rate limiting is not implemented",
                    "files_checked": [auth_file, middleware_file],
                    "relevant_files": [auth_file, middleware_file],  # Should be fully embedded
                    "relevant_context": ["require_auth", "validate_token", "add_security_headers"],
                    "issues_found": [
                        {"severity": "medium", "description": "Token validation needs strengthening"},
                        {"severity": "low", "description": "Missing CSRF protection"},
                        {"severity": "low", "description": "Rate limiting not implemented"},
                    ],
                    "assessment": "Security implementation needs improvements but is acceptable for commit with follow-up tasks",
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response3:
                self.logger.error("Failed to complete to final step")
                return False

            response3_data = self._parse_precommit_response(response3)
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

            # Create a complex scenario with multiple files for pre-commit validation
            database_content = """#!/usr/bin/env python3
import sqlite3
import os
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self):
        self.db_path = os.getenv('DATABASE_PATH', 'app.db')

    @contextmanager
    def get_connection(self):
        \"\"\"Get database connection with proper cleanup\"\"\"
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            yield conn
        finally:
            if conn:
                conn.close()

    def create_user(self, username, email, password_hash):
        \"\"\"Create a new user\"\"\"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Proper parameterized query
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash)
            )
            conn.commit()
            return cursor.lastrowid
"""

            tests_content = """#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
from database_manager import DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager()

    @patch('sqlite3.connect')
    def test_create_user(self, mock_connect):
        \"\"\"Test user creation\"\"\"
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 123
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        user_id = self.db_manager.create_user('testuser', 'test@example.com', 'hashed_password')

        self.assertEqual(user_id, 123)
        mock_cursor.execute.assert_called_once_with(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            ('testuser', 'test@example.com', 'hashed_password')
        )

if __name__ == '__main__':
    unittest.main()
"""

            # Create test files
            db_file = self.create_additional_test_file("database_manager.py", database_content)
            test_file = self.create_additional_test_file("test_database.py", tests_content)

            # Step 1: Start validation (new conversation)
            self.logger.info("    1.6.1: Step 1 - Start validation")
            response1, continuation_id = self.call_mcp_tool(
                "precommit",
                {
                    "step": "Validating new database manager implementation and corresponding tests",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "New database manager with connection handling and user creation functionality",
                    "files_checked": [db_file],
                    "relevant_files": [db_file],
                    "relevant_context": [],
                    "assessment": "Examining database implementation for best practices",
                    "confidence": "low",
                    "path": self.test_dir,
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start multi-step file context test")
                return False

            response1_data = self._parse_precommit_response(response1)

            # Validate step 1 - should use reference_only
            file_context1 = response1_data.get("file_context", {})
            if file_context1.get("type") != "reference_only":
                self.logger.error("Step 1 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 1: reference_only file context")

            # Step 2: Expand validation
            self.logger.info("    1.6.2: Step 2 - Expand validation")
            response2, _ = self.call_mcp_tool(
                "precommit",
                {
                    "step": "Found good database implementation - now examining test coverage",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                    "findings": "Database manager uses proper parameterized queries and context managers. Test file provides good coverage with mocking.",
                    "files_checked": [db_file, test_file],
                    "relevant_files": [db_file, test_file],
                    "relevant_context": ["DatabaseManager.create_user", "TestDatabaseManager.test_create_user"],
                    "assessment": "Implementation looks solid with proper testing",
                    "confidence": "medium",
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            response2_data = self._parse_precommit_response(response2)

            # Validate step 2 - should still use reference_only
            file_context2 = response2_data.get("file_context", {})
            if file_context2.get("type") != "reference_only":
                self.logger.error("Step 2 should use reference_only file context")
                return False

            # Should reference both files
            reference_note = file_context2.get("note", "")
            if "database_manager.py" not in reference_note or "test_database.py" not in reference_note:
                self.logger.error("Step 2 should reference both files in note")
                return False

            self.logger.info("    ✅ Step 2: reference_only file context with multiple files")

            # Step 3: Deep analysis
            self.logger.info("    1.6.3: Step 3 - Deep analysis")
            response3, _ = self.call_mcp_tool(
                "precommit",
                {
                    "step": "Performing comprehensive security and best practices analysis",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                    "findings": "Code follows security best practices: parameterized queries prevent SQL injection, proper resource cleanup with context managers, environment-based configuration.",
                    "files_checked": [db_file, test_file],
                    "relevant_files": [db_file, test_file],
                    "relevant_context": ["DatabaseManager.get_connection", "DatabaseManager.create_user"],
                    "issues_found": [],  # No issues found
                    "assessment": "High quality implementation with proper security measures and testing",
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response3:
                self.logger.error("Failed to continue to step 3")
                return False

            response3_data = self._parse_precommit_response(response3)

            # Validate step 3 - should still use reference_only
            file_context3 = response3_data.get("file_context", {})
            if file_context3.get("type") != "reference_only":
                self.logger.error("Step 3 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 3: reference_only file context")

            # Step 4: Final validation with expert consultation
            self.logger.info("    1.6.4: Step 4 - Final step with expert analysis")
            response4, _ = self.call_mcp_tool(
                "precommit",
                {
                    "step": "Validation complete - code is ready for commit",
                    "step_number": 4,
                    "total_steps": 4,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Comprehensive validation complete: secure implementation with parameterized queries, proper resource management, good test coverage, and no security vulnerabilities identified.",
                    "files_checked": [db_file, test_file],
                    "relevant_files": [db_file, test_file],
                    "relevant_context": ["DatabaseManager", "TestDatabaseManager"],
                    "issues_found": [],
                    "assessment": "Code meets all security and quality standards - approved for commit",
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response4:
                self.logger.error("Failed to complete to final step")
                return False

            response4_data = self._parse_precommit_response(response4)

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
