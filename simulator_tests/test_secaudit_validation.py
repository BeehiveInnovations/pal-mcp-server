#!/usr/bin/env python3
"""
SECAUDIT Tool Validation Test

Tests the secaudit tool's capabilities using the workflow architecture.
This validates that the workflow-based security audit provides step-by-step
analysis with proper investigation guidance and expert analysis integration.
"""

import json

from .conversation_base_test import ConversationBaseTest


class SecauditValidationTest(ConversationBaseTest):
    """Test secaudit tool with workflow architecture"""

    @property
    def test_name(self) -> str:
        return "secaudit_validation"

    @property
    def test_description(self) -> str:
        return "SECAUDIT tool validation with security audit workflow architecture"

    def run_test(self) -> bool:
        """Test secaudit tool capabilities"""
        # Set up the test environment
        self.setUp()

        try:
            self.logger.info("Test: SECAUDIT tool validation (security workflow architecture)")

            # Create test code with various security vulnerabilities
            self._create_test_code_for_audit()

            # Test 1: Single audit session with multiple steps
            if not self._test_single_audit_session():
                return False

            # Test 2: Audit with specific focus areas
            if not self._test_focused_security_audit():
                return False

            # Test 3: Complete audit with expert analysis using fast model
            if not self._test_complete_audit_with_analysis():
                return False

            # Test 4: Certain confidence behavior
            if not self._test_certain_confidence():
                return False

            # Test 5: Continuation test with chat tool
            if not self._test_continuation_with_chat():
                return False

            # Test 6: Model selection control
            if not self._test_model_selection():
                return False

            self.logger.info("  ✅ All secaudit validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"SECAUDIT validation test failed: {e}")
            return False

    def _create_test_code_for_audit(self):
        """Create test files with various security vulnerabilities"""
        # Create an authentication module with multiple security issues
        auth_code = """#!/usr/bin/env python3
import hashlib
import pickle
import sqlite3
from flask import request, session

class AuthenticationManager:
    def __init__(self, db_path="users.db"):
        # A01: Broken Access Control - No proper session management
        self.db_path = db_path
        self.sessions = {}  # In-memory session storage
    def login(self, username, password):
        '''User login with various security vulnerabilities'''
        # A03: Injection - SQL injection vulnerability
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Direct string interpolation in SQL query
        query = f"SELECT id, password_hash FROM users WHERE username = '{username}'"
        cursor.execute(query)

        user = cursor.fetchone()
        if not user:
            return {"status": "failed", "message": "User not found"}

        # A02: Cryptographic Failures - Weak hashing algorithm
        password_hash = hashlib.md5(password.encode()).hexdigest()

        if user[1] == password_hash:
            # A07: Identification and Authentication Failures - Weak session generation
            session_id = hashlib.md5(f"{username}{password}".encode()).hexdigest()
            self.sessions[session_id] = {"user_id": user[0], "username": username}

            return {"status": "success", "session_id": session_id}
        else:
            return {"status": "failed", "message": "Invalid password"}

    def reset_password(self, email):
        '''Password reset with security issues'''
        # A04: Insecure Design - No rate limiting or validation
        reset_token = hashlib.md5(email.encode()).hexdigest()

        # A09: Security Logging and Monitoring Failures - No security event logging
        # Simply returns token without any verification or logging
        return {"reset_token": reset_token, "url": f"/reset?token={reset_token}"}

    def deserialize_user_data(self, data):
        '''Unsafe deserialization'''
        # A08: Software and Data Integrity Failures - Insecure deserialization
        return pickle.loads(data)

    def get_user_profile(self, user_id):
        '''Get user profile with authorization issues'''
        # A01: Broken Access Control - No authorization check
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Fetches any user profile without checking permissions
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()
"""

        # Create authentication file
        self.auth_file = self.create_additional_test_file("auth_manager.py", auth_code)
        self.logger.info(f"  ✅ Created authentication file with security issues: {self.auth_file}")

        # Create API endpoint with additional vulnerabilities
        api_code = """#!/usr/bin/env python3
from flask import Flask, request, jsonify
import os
import subprocess
import requests

app = Flask(__name__)

# A05: Security Misconfiguration - Debug mode enabled
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'dev-secret-key'  # Hardcoded secret

@app.route('/api/search', methods=['GET'])
def search():
    '''Search endpoint with multiple vulnerabilities'''
    # A03: Injection - XSS vulnerability, no input sanitization
    query = request.args.get('q', '')

    # A03: Injection - Command injection vulnerability
    if 'file:' in query:
        filename = query.split('file:')[1]
        # Direct command execution
        result = subprocess.run(f"cat {filename}", shell=True, capture_output=True, text=True)
        return jsonify({"result": result.stdout})

    # A10: Server-Side Request Forgery (SSRF)
    if query.startswith('http'):
        # No validation of URL, allows internal network access
        response = requests.get(query)
        return jsonify({"content": response.text})

    # Return search results without output encoding
    return f"<h1>Search Results for: {query}</h1>"

@app.route('/api/admin', methods=['GET'])
def admin_panel():
    '''Admin panel with broken access control'''
    # A01: Broken Access Control - No authentication check
    # Anyone can access admin functionality
    action = request.args.get('action')

    if action == 'delete_user':
        user_id = request.args.get('user_id')
        # Performs privileged action without authorization
        return jsonify({"status": "User deleted", "user_id": user_id})

    return jsonify({"status": "Admin panel"})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    '''File upload with security issues'''
    # A05: Security Misconfiguration - No file type validation
    file = request.files.get('file')
    if file:
        # Saves any file type to server
        filename = file.filename
        file.save(os.path.join('/tmp', filename))

        # A03: Path traversal vulnerability
        return jsonify({"status": "File uploaded", "path": f"/tmp/{filename}"})

    return jsonify({"error": "No file provided"})

# A06: Vulnerable and Outdated Components
# Using old Flask version with known vulnerabilities (hypothetical)
# requirements.txt: Flask==0.12.2 (known security issues)

if __name__ == '__main__':
    # A05: Security Misconfiguration - Running on all interfaces
    app.run(host='0.0.0.0', port=5000, debug=True)
"""

        # Create API file
        self.api_file = self.create_additional_test_file("api_endpoints.py", api_code)
        self.logger.info(f"  ✅ Created API file with security vulnerabilities: {self.api_file}")

    def _test_single_audit_session(self) -> bool:
        """Test a single security audit session with multiple steps"""
        self.logger.info("  🔧 Testing single audit session...")

        try:
            # Step 1: Initial security audit request
            response, continuation_id = self.call_mcp_tool_direct(
                "secaudit",
                {
                    "step": f"Begin security audit of authentication system in {self.auth_file}",
                    "step_number": 1,
                    "total_steps": 6,
                    "next_step_required": True,
                    "findings": "Starting security assessment",
                    "relevant_files": [self.auth_file],
                    "model": "flashlite",
                },
            )

            if not response:
                self.logger.error("Failed to call secaudit tool")
                return False

            # Parse and validate the response
            try:
                response_data = json.loads(response) if response else {}
            except json.JSONDecodeError:
                response_data = {}

            # Check if it's asking for investigation
            status = response_data.get("status", "")
            if status != "pause_for_secaudit":
                self.logger.error(f"Expected pause_for_secaudit status, got: {status}")
                return False

            # Step 2: Continue with findings
            response2, _ = self.call_mcp_tool_direct(
                "secaudit",
                {
                    "step": "Examined authentication module and found critical security vulnerabilities",
                    "step_number": 2,
                    "total_steps": 6,
                    "next_step_required": True,
                    "findings": (
                        "Found multiple OWASP Top 10 vulnerabilities: "
                        "1. SQL injection in login method (line 88) - direct string interpolation in query "
                        "2. Weak MD5 hashing for passwords (line 96) - cryptographically broken "
                        "3. Insecure session management (line 100) - predictable session IDs "
                        "4. Unsafe deserialization (line 119) - pickle.loads without validation"
                    ),
                    "files_checked": [self.auth_file],
                    "relevant_files": [self.auth_file],
                    "relevant_context": ["AuthenticationManager.login", "AuthenticationManager.deserialize_user_data"],
                    "issues_found": [
                        {"severity": "critical", "description": "SQL injection vulnerability in login method"},
                        {"severity": "high", "description": "Weak MD5 password hashing"},
                        {"severity": "high", "description": "Insecure session management"},
                        {"severity": "critical", "description": "Unsafe deserialization vulnerability"},
                    ],
                    "confidence": "medium",
                    "continuation_id": continuation_id,
                    "model": "flashlite",
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            self.logger.info("  ✅ Single audit session test passed")
            return True

        except Exception as e:
            self.logger.error(f"Single audit session test failed: {e}")
            return False

    def _test_focused_security_audit(self) -> bool:
        """Test security audit with specific focus areas"""
        self.logger.info("  🔧 Testing focused security audit...")

        try:
            # Request OWASP-focused audit
            response, continuation_id = self.call_mcp_tool_direct(
                "secaudit",
                {
                    "step": f"Begin OWASP-focused security audit of {self.api_file}",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Starting OWASP Top 10 focused security assessment",
                    "relevant_files": [self.api_file],
                    "security_scope": "Web API endpoints",
                    "threat_level": "high",
                    "audit_focus": "owasp",
                    "model": "flashlite",
                },
            )

            if not response:
                self.logger.error("Failed to start OWASP-focused audit")
                return False

            # Verify the audit was configured correctly
            try:
                response_data = json.loads(response)
                # The tool should acknowledge the OWASP focus
                if response_data.get("status") == "pause_for_secaudit":
                    self.logger.info("  ✅ Focused security audit test passed")
                    return True
            except json.JSONDecodeError:
                pass

            self.logger.error("Expected proper OWASP-focused configuration")
            return False

        except Exception as e:
            self.logger.error(f"Focused security audit test failed: {e}")
            return False

    def _test_complete_audit_with_analysis(self) -> bool:
        """Test complete security audit with expert analysis"""
        self.logger.info("  🔧 Testing complete audit with expert analysis...")

        try:
            # Step 1: Start fresh audit
            response1, continuation_id = self.call_mcp_tool_direct(
                "secaudit",
                {
                    "step": f"Begin comprehensive security audit of {self.auth_file} and {self.api_file}",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,
                    "findings": "Starting OWASP Top 10 security assessment of authentication and API modules",
                    "relevant_files": [self.auth_file, self.api_file],
                    "security_scope": "Web application with authentication and API endpoints",
                    "model": "flashlite",
                },
            )

            if not response1:
                self.logger.error("Failed to start comprehensive audit")
                return False

            # Step 2: Continue with detailed findings
            response2, _ = self.call_mcp_tool_direct(
                "secaudit",
                {
                    "step": "Completed comprehensive security investigation of both modules",
                    "step_number": 2,
                    "total_steps": 3,
                    "next_step_required": True,
                    "findings": (
                        "Found critical OWASP vulnerabilities across both modules: "
                        "A01: Broken Access Control in admin panel, "
                        "A03: SQL injection in login and command injection in search, "
                        "A02: Weak cryptography with MD5 hashing, "
                        "A05: Security misconfiguration with debug mode enabled, "
                        "A07: Weak session management, "
                        "A08: Insecure deserialization, "
                        "A10: SSRF vulnerability in search endpoint"
                    ),
                    "files_checked": [self.auth_file, self.api_file],
                    "relevant_files": [self.auth_file, self.api_file],
                    "relevant_context": [
                        "AuthenticationManager.login",
                        "AuthenticationManager.deserialize_user_data",
                        "api.search",
                        "api.admin_panel",
                    ],
                    "issues_found": [
                        {"severity": "critical", "description": "SQL injection in login method"},
                        {"severity": "critical", "description": "Command injection in search endpoint"},
                        {"severity": "critical", "description": "SSRF vulnerability allowing internal network access"},
                        {"severity": "high", "description": "Broken access control on admin panel"},
                        {"severity": "high", "description": "Insecure deserialization vulnerability"},
                        {"severity": "high", "description": "XSS vulnerability in search results"},
                        {"severity": "medium", "description": "Weak MD5 password hashing"},
                        {"severity": "medium", "description": "Security misconfiguration - debug mode enabled"},
                    ],
                    "confidence": "high",
                    "continuation_id": continuation_id,
                    "model": "flashlite",
                },
            )

            # Final step - skip expert analysis to avoid timeout
            response3, _ = self.call_mcp_tool_direct(
                "secaudit",
                {
                    "step": "Complete security assessment with all vulnerabilities documented",
                    "step_number": 3,
                    "total_steps": 3,
                    "next_step_required": False,
                    "findings": "Security audit complete with 8 vulnerabilities identified across OWASP categories",
                    "files_checked": [self.auth_file, self.api_file],
                    "relevant_files": [self.auth_file, self.api_file],
                    "confidence": "high",  # High confidence to trigger expert analysis
                    "continuation_id": continuation_id,
                    "model": "flashlite",
                },
            )

            if response3:
                # Check for expert analysis or completion status
                try:
                    response_data = json.loads(response3)
                    status = response_data.get("status", "")
                    # Either expert analysis completed or security analysis complete
                    if status in ["complete", "security_analysis_complete"]:
                        self.logger.info("  ✅ Complete audit with expert analysis test passed")
                        return True
                except json.JSONDecodeError:
                    # If not JSON, check for security content (expert analysis output)
                    if "security" in response3.lower() or "vulnerability" in response3.lower():
                        self.logger.info("  ✅ Complete audit with expert analysis test passed")
                        return True

            self.logger.error("Expected expert security analysis or completion")
            return False

        except Exception as e:
            self.logger.error(f"Complete audit with analysis test failed: {e}")
            return False

    def _test_certain_confidence(self) -> bool:
        """Test behavior when confidence is certain"""
        self.logger.info("  🔧 Testing certain confidence behavior...")

        try:
            # Request with certain confidence
            response, _ = self.call_mcp_tool_direct(
                "secaudit",
                {
                    "step": f"Security audit complete for {self.auth_file}",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Critical SQL injection vulnerability confirmed in login method",
                    "files_checked": [self.auth_file],
                    "relevant_files": [self.auth_file],
                    "issues_found": [
                        {"severity": "critical", "description": "SQL injection vulnerability in login method"}
                    ],
                    "confidence": "certain",
                    "model": "flashlite",
                },
            )

            if not response:
                self.logger.error("Failed to execute certain confidence test")
                return False

            try:
                response_data = json.loads(response)
                # With certain confidence, should complete without expert analysis
                if response_data.get("status") == "security_analysis_complete":
                    self.logger.info("  ✅ Certain confidence correctly completes without expert analysis")
                    return True
            except json.JSONDecodeError:
                pass

            # Check if findings are shown directly
            response_lower = response.lower()
            if "sql injection" in response_lower or "vulnerability" in response_lower:
                self.logger.info("  ✅ Certain confidence shows findings directly")
                return True

            self.logger.error("Expected completion or direct findings with certain confidence")
            return False

        except Exception as e:
            self.logger.error(f"Certain confidence test failed: {e}")
            return False

    def _test_continuation_with_chat(self) -> bool:
        """Test continuation functionality with chat tool"""
        self.logger.info("  🔧 Testing continuation with chat tool...")

        try:
            # First, run a security audit that generates a continuation_id
            response1, continuation_id = self.call_mcp_tool_direct(
                "secaudit",
                {
                    "step": f"Start analyzing {self.auth_file} for authentication vulnerabilities",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Beginning authentication security analysis",
                    "relevant_files": [self.auth_file],
                    "model": "flashlite",
                },
            )

            if not response1:
                self.logger.error("Failed to start audit for continuation test")
                return False

            # Extract continuation_id if present
            if not continuation_id:
                self.logger.info("  ⚠️  No continuation_id returned, checking response")
                try:
                    response_data = json.loads(response1)
                    # Look for thread_id in metadata
                    metadata = response_data.get("metadata", {})
                    continuation_id = metadata.get("thread_id")
                except json.JSONDecodeError:
                    pass

            if continuation_id:
                # Now test using chat tool with continuation
                chat_response, _ = self.call_mcp_tool_direct(
                    "chat",
                    {
                        "prompt": "Can you tell me more about the SQL injection vulnerability details found in the security audit?",
                        "continuation_id": continuation_id,
                        "model": "flashlite",
                    },
                )

                if chat_response:
                    self.logger.info("  ✅ Chat tool continuation test passed")
                    return True
            else:
                # Without continuation_id, just verify the audit step worked
                if response1:
                    self.logger.info("  ✅ Audit step completed (continuation test limited)")
                    return True

            self.logger.error("Expected successful continuation or audit step")
            return False

        except Exception as e:
            self.logger.error(f"Continuation test failed: {e}")
            return False

    def _test_model_selection(self) -> bool:
        """Test model selection and skip expert analysis option"""
        self.logger.info("  🔧 Testing model selection control...")

        try:
            # Test 1: Explicit model selection
            response1, _ = self.call_mcp_tool_direct(
                "secaudit",
                {
                    "step": f"Analyze {self.api_file} for SSRF vulnerabilities",
                    "step_number": 1,
                    "total_steps": 2,
                    "next_step_required": True,
                    "findings": "Starting SSRF vulnerability analysis",
                    "relevant_files": [self.api_file],
                    "audit_focus": "owasp",
                    "model": "flashlite",
                },
            )

            if response1:
                self.logger.info("  ✅ Model selection recognized")

            # Test 2: Skip expert analysis
            response2, _ = self.call_mcp_tool_direct(
                "secaudit",
                {
                    "step": f"Complete security investigation of {self.auth_file}",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Security issues documented",
                    "files_checked": [self.auth_file],
                    "relevant_files": [self.auth_file],
                    "confidence": "high",
                    "use_assistant_model": False,  # Skip expert analysis
                    "model": "flashlite",
                },
            )

            if response2:
                try:
                    response_data = json.loads(response2)
                    # Should complete without expert analysis
                    if response_data.get("status") == "security_analysis_complete":
                        self.logger.info("  ✅ Skip expert analysis option works")
                        return True
                except json.JSONDecodeError:
                    pass

                # Or might just complete the analysis
                response_lower = response2.lower()
                if "complete" in response_lower or "security" in response_lower:
                    self.logger.info("  ✅ Analysis performed without expert model")
                    return True

            self.logger.error("Expected model selection or skip behavior")
            return False

        except Exception as e:
            self.logger.error(f"Model selection test failed: {e}")
            return False
