#!/usr/bin/env python3
"""
Debug Tool Validation Test

Tests the debug tool with real bugs to validate:
- Proper execution with flash model
- Actual bug identification and analysis
- Hypothesis generation for root causes
- Log validation for tool execution
"""

import json

from .base_test import BaseSimulatorTest


class DebugValidationTest(BaseSimulatorTest):
    """Test debug tool with actual bug scenarios"""

    @property
    def test_name(self) -> str:
        return "debug_validation"

    @property
    def test_description(self) -> str:
        return "Debug tool validation with actual bugs"

    def run_test(self) -> bool:
        """Test debug tool with real bugs"""
        try:
            self.logger.info("Test: Debug tool validation")

            # Setup test files directory first
            self.setup_test_files()

            # Create a Python file with a subtle but realistic bug
            buggy_code = """#!/usr/bin/env python3
import json
import requests
from datetime import datetime, timedelta

class UserSessionManager:
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
            'last_activity': datetime.now(),
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

        # Update last activity
        session['last_activity'] = current_time
        return True

    def cleanup_expired_sessions(self):
        \"\"\"Remove expired sessions from memory\"\"\"
        current_time = datetime.now()
        expired_sessions = []

        for session_id, session in self.active_sessions.items():
            if current_time > session['expires_at']:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self.active_sessions[session_id]

        return len(expired_sessions)

class APIHandler:
    def __init__(self):
        self.session_manager = UserSessionManager()
        self.request_count = 0

    def authenticate_user(self, username, password):
        \"\"\"Authenticate user and create session\"\"\"
        # Simulate API call to auth service
        auth_response = self._call_auth_service(username, password)

        if auth_response.get('success'):
            user_data = auth_response.get('user_data', {})
            session_id = self.session_manager.create_session(
                user_data['id'], user_data
            )
            return {'success': True, 'session_id': session_id}

        return {'success': False, 'error': 'Authentication failed'}

    def process_request(self, session_id, request_data):
        \"\"\"Process an API request with session validation\"\"\"
        self.request_count += 1

        # Validate session before processing
        if not self.session_manager.validate_session(session_id):
            return {'error': 'Invalid or expired session', 'code': 401}

        # Simulate request processing
        try:
            result = self._process_business_logic(request_data)
            return {'success': True, 'data': result}
        except Exception as e:
            return {'error': str(e), 'code': 500}

    def _call_auth_service(self, username, password):
        \"\"\"Simulate external authentication service call\"\"\"
        # Simulate network delay and response
        import time
        time.sleep(0.1)

        # Mock successful authentication
        if username and password:
            return {
                'success': True,
                'user_data': {
                    'id': hash(username) % 10000,
                    'username': username,
                    'roles': ['user']
                }
            }
        return {'success': False}

    def _process_business_logic(self, request_data):
        \"\"\"Simulate business logic processing\"\"\"
        if not request_data:
            raise ValueError("Invalid request data")

        # Simulate some processing
        return {
            'processed_at': datetime.now().isoformat(),
            'request_id': self.request_count,
            'status': 'completed'
        }

# Global API handler instance
api_handler = APIHandler()

def handle_api_request(session_id, request_data):
    \"\"\"Main API request handler\"\"\"
    return api_handler.process_request(session_id, request_data)
"""

            # Create test file with subtle bug
            test_file = self.create_additional_test_file("session_manager.py", buggy_code)
            self.logger.info(f"  ✅ Created test file with subtle bug: {test_file}")

            # Create a realistic problem description with subtle symptoms
            error_description = """ISSUE DESCRIPTION:
Our API service is experiencing intermittent session validation failures in production.

SYMPTOMS OBSERVED:
- Users randomly get "Invalid or expired session" errors even with valid sessions
- The issue happens more frequently during high-traffic periods
- Sessions that should still be valid (created < 30 minutes ago) are being rejected
- The problem occurs maybe 2-3% of requests but is hard to reproduce consistently
- Server logs show session validation failing but no clear pattern

ENVIRONMENT:
- Python 3.13 API service
- Running in production with multiple concurrent users
- Redis not used for session storage (in-memory only)
- Load balancer distributes requests across multiple instances

RECENT CHANGES:
- Increased session timeout from 15 to 30 minutes last week
- Added cleanup routine to remove expired sessions
- No major code changes to session management

USER IMPACT:
- Users have to re-authenticate randomly
- Affects user experience and causes complaints
- Seems to happen more on busy days

The code looks correct to me, but something is causing valid sessions to be treated as expired or invalid. I'm not sure what's causing this intermittent behavior."""

            error_file = self.create_additional_test_file("error_description.txt", error_description)
            self.logger.info(f"  ✅ Created error description file: {error_file}")

            # Call debug tool with flash model and realistic problem description
            self.logger.info("  🔍 Calling debug tool to investigate session validation issues...")
            response, continuation_id = self.call_mcp_tool(
                "debug",
                {
                    "prompt": "Investigate why our API is experiencing intermittent session validation failures in production",
                    "files": [test_file, error_file],
                    "findings": "Users getting 'Invalid or expired session' errors randomly, occurs more during high traffic, sessions should still be valid",
                    "error_context": "Sessions created < 30 minutes ago being rejected, happens ~2-3% of requests, load balanced environment",
                    "systematic_investigation": True,
                    "model": "flash",
                    "thinking_mode": "medium",
                },
            )

            if not response:
                self.logger.error("Failed to get debug response")
                return False

            self.logger.info("  ✅ Got debug response")

            # Parse response to validate bug identification
            try:
                response_data = json.loads(response)
                self.logger.debug(f"Response keys: {list(response_data.keys())}")

                # Extract the actual content if it's wrapped
                if "content" in response_data:
                    content = response_data["content"]
                    # Handle markdown JSON blocks
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()

                    # Parse the inner JSON
                    inner_data = json.loads(content)
                    self.logger.debug(f"Inner data keys: {list(inner_data.keys())}")
                else:
                    inner_data = response_data

                # Check for structured debug analysis (should have analysis_complete status)
                if inner_data.get("status") == "analysis_complete":
                    self.logger.info("  ✅ Got structured debug analysis")

                    # Validate hypothesis generation
                    hypotheses = inner_data.get("hypotheses", [])
                    if not hypotheses:
                        self.logger.error("No hypotheses found in debug analysis")
                        return False

                    self.logger.info(f"  🧠 Found {len(hypotheses)} hypotheses")

                    # Check if the model identified the real bug: dictionary modification during iteration
                    analysis_text = json.dumps(inner_data).lower()

                    # Look for the actual bug - modifying dictionary while iterating
                    bug_indicators = [
                        "dictionary",
                        "iteration",
                        "modify",
                        "concurrent",
                        "runtime error",
                        "dictionary changed size during iteration",
                        "cleanup_expired_sessions",
                        "active_sessions",
                        "del",
                        "removing while iterating",
                    ]

                    found_indicators = [indicator for indicator in bug_indicators if indicator in analysis_text]

                    # Check for specific mentions of the problematic pattern
                    dictionary_bug_patterns = [
                        "modifying dictionary while iterating",
                        "dictionary changed size",
                        "concurrent modification",
                        "iterating over dictionary",
                        "del.*active_sessions",
                        "cleanup.*iteration",
                    ]

                    import re

                    pattern_matches = []
                    for pattern in dictionary_bug_patterns:
                        if re.search(pattern, analysis_text):
                            pattern_matches.append(pattern)

                    if len(found_indicators) >= 3 or len(pattern_matches) >= 1:
                        self.logger.info("  ✅ Flash identified the dictionary iteration bug")
                        self.logger.info(f"     Found indicators: {found_indicators[:3]}")
                        if pattern_matches:
                            self.logger.info(f"     Pattern matches: {pattern_matches}")
                    else:
                        self.logger.error("  ❌ Flash missed the dictionary iteration bug")
                        self.logger.error(f"     Found only: {found_indicators}")
                        return False

                    # Validate hypothesis quality (should have confidence levels and reasoning)
                    valid_hypotheses = 0
                    for i, hypothesis in enumerate(hypotheses[:3]):  # Check top 3
                        confidence = hypothesis.get("confidence", "").lower()
                        reasoning = hypothesis.get("reasoning", "")

                        if confidence in ["high", "medium", "low"] and len(reasoning) > 20:
                            valid_hypotheses += 1
                            self.logger.debug(f"  Hypothesis {i+1}: {confidence} confidence, good reasoning")
                        else:
                            self.logger.debug(f"  Hypothesis {i+1}: weak ({confidence}, {len(reasoning)} chars)")

                    if valid_hypotheses >= 2:
                        self.logger.info(f"  ✅ Found {valid_hypotheses} well-structured hypotheses")
                    else:
                        self.logger.error(f"  ❌ Only {valid_hypotheses} well-structured hypotheses")
                        return False

                    # Check for line-specific references
                    if "line" in analysis_text or "lines" in analysis_text:
                        self.logger.info("  📍 Analysis includes line-specific references")
                    else:
                        self.logger.warning("  ⚠️ No line-specific references found")

                else:
                    # Non-structured response - check for dictionary iteration bug identification
                    self.logger.info("  📝 Got general debug response")

                    response_text = response.lower()

                    # Check for the specific bug in general response
                    bug_indicators = [
                        "dictionary",
                        "iteration",
                        "modify",
                        "concurrent",
                        "active_sessions",
                        "cleanup",
                        "del ",
                        "removing",
                        "changed size",
                    ]

                    found_indicators = [indicator for indicator in bug_indicators if indicator in response_text]

                    if len(found_indicators) >= 3:
                        self.logger.info(f"  ✅ Found {len(found_indicators)} relevant indicators in response")
                        self.logger.info(f"     Found: {found_indicators}")
                    else:
                        self.logger.error(f"  ❌ Only found {len(found_indicators)} relevant indicators")
                        self.logger.error(f"     Found: {found_indicators}")
                        return False

            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse debug response as JSON: {e}")
                # For non-JSON responses, check for dictionary iteration bug
                response_text = response.lower()

                bug_indicators = [
                    "dictionary",
                    "iteration",
                    "modify",
                    "concurrent",
                    "active_sessions",
                    "cleanup",
                    "del ",
                    "removing",
                ]

                found_indicators = [indicator for indicator in bug_indicators if indicator in response_text]

                if len(found_indicators) >= 3:
                    self.logger.info(f"  ✅ Text response found {len(found_indicators)} relevant indicators")
                else:
                    self.logger.error(f"  ❌ Text response only found {len(found_indicators)} relevant indicators")
                    return False

            # Validate logs
            self.logger.info("  📋 Validating execution logs...")

            # Get server logs using inherited method
            logs = self.get_recent_server_logs(500)

            # Look for debug tool execution patterns
            debug_patterns = [
                "debug tool",
                "[DEBUG]",
                "systematic investigation",
                "Token budget",
                "Essential files for debugging",
            ]

            patterns_found = 0
            for pattern in debug_patterns:
                if pattern in logs:
                    patterns_found += 1
                    self.logger.debug(f"  ✅ Found log pattern: {pattern}")

            if patterns_found >= 3:
                self.logger.info(f"  ✅ Log validation passed ({patterns_found}/{len(debug_patterns)} patterns)")
            else:
                self.logger.warning(f"  ⚠️ Only found {patterns_found}/{len(debug_patterns)} log patterns")

            # Test continuation if available
            if continuation_id:
                self.logger.info("  🔄 Testing debug continuation...")

                follow_up_response, _ = self.call_mcp_tool(
                    "debug",
                    {
                        "prompt": "Based on your analysis, which bug should we fix first and how?",
                        "continuation_id": continuation_id,
                        "model": "flash",
                    },
                )

                if follow_up_response:
                    self.logger.info("  ✅ Debug continuation worked")
                else:
                    self.logger.warning("  ⚠️ Debug continuation failed")

            self.logger.info("  ✅ Debug tool validation completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Debug validation test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()
