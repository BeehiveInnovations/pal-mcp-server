#!/usr/bin/env python3
"""
CodeReview Tool Validation Test

Tests the codereview tool's capabilities using the new workflow architecture.
This validates that the workflow-based code review provides step-by-step
analysis with proper investigation guidance and expert analysis integration.
"""

import json
from typing import Optional

from .conversation_base_test import ConversationBaseTest


class CodeReviewValidationTest(ConversationBaseTest):
    """Test codereview tool with new workflow architecture"""

    @property
    def test_name(self) -> str:
        return "codereview_validation"

    @property
    def test_description(self) -> str:
        return "CodeReview tool validation with new workflow architecture"

    def run_test(self) -> bool:
        """Test codereview tool capabilities"""
        # Set up the test environment
        self.setUp()

        try:
            self.logger.info("Test: CodeReviewWorkflow tool validation (new architecture)")

            # Create test code with various issues for review
            self._create_test_code_for_review()

            # Test 1: Single review session with multiple steps
            if not self._test_single_review_session():
                return False

            # Test 2: Review flow that requires refocusing
            if not self._test_review_refocus_flow():
                return False

            # Test 3: Complete review with expert analysis
            if not self._test_complete_review_with_analysis():
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

            self.logger.info("  ✅ All codereview validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"CodeReviewWorkflow validation test failed: {e}")
            return False

    def _create_test_code_for_review(self):
        """Create test files with various code quality issues for review"""
        # Create a payment processing module with multiple issues
        payment_code = """#!/usr/bin/env python3
import hashlib
import requests
import json
from datetime import datetime

class PaymentProcessor:
    def __init__(self, api_key):
        self.api_key = api_key  # Security issue: API key stored in plain text
        self.base_url = "https://payment-gateway.example.com"
        self.session = requests.Session()
        self.failed_payments = []  # Performance issue: unbounded list

    def process_payment(self, amount, card_number, cvv, user_id):
        \"\"\"Process a payment transaction\"\"\"
        # Security issue: No input validation
        # Performance issue: Inefficient nested loops
        for attempt in range(3):
            for retry in range(5):
                try:
                    # Security issue: Logging sensitive data
                    print(f"Processing payment: {card_number}, CVV: {cvv}")

                    # Over-engineering: Complex hashing that's not needed
                    payment_hash = self._generate_complex_hash(amount, card_number, cvv, user_id, datetime.now())

                    # Security issue: Insecure HTTP request construction
                    url = f"{self.base_url}/charge?amount={amount}&card={card_number}&api_key={self.api_key}"

                    response = self.session.get(url)  # Security issue: using GET for sensitive data

                    if response.status_code == 200:
                        return {"status": "success", "hash": payment_hash}
                    else:
                        # Code smell: Generic exception handling without specific error types
                        self.failed_payments.append({"amount": amount, "timestamp": datetime.now()})

                except Exception as e:
                    # Code smell: Bare except clause and poor error handling
                    print(f"Payment failed: {e}")
                    continue

        return {"status": "failed"}

    def _generate_complex_hash(self, amount, card_number, cvv, user_id, timestamp):
        \"\"\"Over-engineered hash generation with unnecessary complexity\"\"\"
        # Over-engineering: Overly complex for no clear benefit
        combined = f"{amount}-{card_number}-{cvv}-{user_id}-{timestamp}"

        # Security issue: Weak hashing algorithm
        hash1 = hashlib.md5(combined.encode()).hexdigest()
        hash2 = hashlib.sha1(hash1.encode()).hexdigest()
        hash3 = hashlib.md5(hash2.encode()).hexdigest()

        # Performance issue: Unnecessary string operations in loop
        result = ""
        for i in range(len(hash3)):
            for j in range(3):  # Arbitrary nested loop
                result += hash3[i] if i % 2 == 0 else hash3[i].upper()

        return result[:32]  # Arbitrary truncation

    def get_payment_history(self, user_id):
        \"\"\"Get payment history - has scalability issues\"\"\"
        # Performance issue: No pagination, could return massive datasets
        # Performance issue: Inefficient algorithm O(n²)
        all_payments = self._fetch_all_payments()  # Could be millions of records
        user_payments = []

        for payment in all_payments:
            for field in payment:  # Unnecessary nested iteration
                if field == "user_id" and payment[field] == user_id:
                    user_payments.append(payment)
                    break

        return user_payments

    def _fetch_all_payments(self):
        \"\"\"Simulated method that would fetch all payments\"\"\"
        # Maintainability issue: Hard-coded test data
        return [
            {"user_id": 1, "amount": 100, "status": "success"},
            {"user_id": 2, "amount": 200, "status": "failed"},
            {"user_id": 1, "amount": 150, "status": "success"},
        ]
"""

        # Create test file with multiple issues
        self.payment_file = self.create_additional_test_file("payment_processor.py", payment_code)
        self.logger.info(f"  ✅ Created test file with code issues: {self.payment_file}")

        # Create configuration file with additional issues
        config_code = """#!/usr/bin/env python3
import os

# Security issue: Hardcoded secrets
DATABASE_PASSWORD = "admin123"
SECRET_KEY = "my-secret-key-12345"

# Over-engineering: Unnecessarily complex configuration class
class ConfigurationManager:
    def __init__(self):
        self.config_cache = {}
        self.config_hierarchy = {}
        self.config_validators = {}
        self.config_transformers = {}
        self.config_listeners = []

    def get_config(self, key, default=None):
        # Over-engineering: Complex caching for simple config lookup
        if key in self.config_cache:
            cached_value = self.config_cache[key]
            if self._validate_cached_value(cached_value):
                return self._transform_value(key, cached_value)

        # Code smell: Complex nested conditionals
        if key in self.config_hierarchy:
            hierarchy = self.config_hierarchy[key]
            for level in hierarchy:
                if level == "env":
                    value = os.getenv(key.upper(), default)
                elif level == "file":
                    value = self._read_from_file(key, default)
                elif level == "database":
                    value = self._read_from_database(key, default)
                else:
                    value = default

                if value is not None:
                    self.config_cache[key] = value
                    return self._transform_value(key, value)

        return default

    def _validate_cached_value(self, value):
        # Maintainability issue: Unclear validation logic
        if isinstance(value, str) and len(value) > 1000:
            return False
        return True

    def _transform_value(self, key, value):
        # Code smell: Unnecessary abstraction
        if key in self.config_transformers:
            transformer = self.config_transformers[key]
            return transformer(value)
        return value

    def _read_from_file(self, key, default):
        # Maintainability issue: No error handling for file operations
        with open(f"/etc/app/{key}.conf") as f:
            return f.read().strip()

    def _read_from_database(self, key, default):
        # Performance issue: Database query for every config read
        # No connection pooling or caching
        import sqlite3
        conn = sqlite3.connect("config.db")
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else default
"""

        self.config_file = self.create_additional_test_file("config.py", config_code)
        self.logger.info(f"  ✅ Created configuration file with issues: {self.config_file}")

    def _test_single_review_session(self) -> bool:
        """Test a complete code review session with multiple steps"""
        try:
            self.logger.info("  1.1: Testing single code review session")

            # Step 1: Start review
            self.logger.info("    1.1.1: Step 1 - Initial review")
            response1, continuation_id = self.call_mcp_tool(
                "codereview",
                {
                    "step": "I need to perform a comprehensive code review of the payment processing module. Let me start by examining the code structure and identifying potential issues.",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial examination reveals a payment processing class with potential security and performance concerns.",
                    "files_checked": [self.payment_file],
                    "relevant_files": [self.payment_file],
                    "absolute_file_paths": [self.payment_file],  # Required for step 1
                    "review_type": "full",
                    "severity_filter": "all",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to get initial review response")
                return False

            # Parse and validate JSON response
            response1_data = self._parse_review_response(response1)
            if not response1_data:
                return False

            # Validate step 1 response structure - expect pause_for_code_review for next_step_required=True
            if not self._validate_step_response(response1_data, 1, 4, True, "pause_for_code_review"):
                return False

            self.logger.info(f"    ✅ Step 1 successful, continuation_id: {continuation_id}")

            # Step 2: Detailed analysis
            self.logger.info("    1.1.2: Step 2 - Detailed security analysis")
            response2, _ = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Now performing detailed security analysis of the payment processor code to identify vulnerabilities and code quality issues.",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Found multiple security issues: API key stored in plain text, sensitive data logging, insecure HTTP methods, and weak hashing algorithms.",
                    "files_checked": [self.payment_file],
                    "relevant_files": [self.payment_file],
                    "relevant_context": ["PaymentProcessor.__init__", "PaymentProcessor.process_payment"],
                    "issues_found": [
                        {"severity": "critical", "description": "API key stored in plain text in memory"},
                        {"severity": "critical", "description": "Credit card and CVV logged in plain text"},
                        {"severity": "high", "description": "Using GET method for sensitive payment data"},
                        {"severity": "medium", "description": "Weak MD5 hashing algorithm used"},
                    ],
                    "confidence": "high",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue review to step 2")
                return False

            response2_data = self._parse_review_response(response2)
            if not self._validate_step_response(response2_data, 2, 4, True, "pause_for_code_review"):
                return False

            # Check review status tracking
            review_status = response2_data.get("code_review_status", {})
            if review_status.get("files_checked", 0) < 1:
                self.logger.error("Files checked count not properly tracked")
                return False

            if review_status.get("relevant_context", 0) != 2:
                self.logger.error("Relevant context not properly tracked")
                return False

            # Check issues by severity
            issues_by_severity = review_status.get("issues_by_severity", {})
            if issues_by_severity.get("critical", 0) != 2:
                self.logger.error("Critical issues not properly tracked")
                return False

            if issues_by_severity.get("high", 0) != 1:
                self.logger.error("High severity issues not properly tracked")
                return False

            self.logger.info("    ✅ Step 2 successful with proper issue tracking")

            # Store continuation_id for next test
            self.review_continuation_id = continuation_id
            return True

        except Exception as e:
            self.logger.error(f"Single review session test failed: {e}")
            return False

    def _test_review_refocus_flow(self) -> bool:
        """Test code review flow that revises findings by refocusing"""
        try:
            self.logger.info("  1.2: Testing code review refocus workflow")

            # Start a new review for testing refocus behaviour
            self.logger.info("    1.2.1: Start review for refocus test")
            response1, continuation_id = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Reviewing configuration management code for best practices",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial analysis shows complex configuration class",
                    "files_checked": [self.config_file],
                    "relevant_files": [self.config_file],
                    "absolute_file_paths": [self.config_file],
                    "review_type": "full",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start refocus test review")
                return False

            # Step 2: Initial direction
            self.logger.info("    1.2.2: Step 2 - Initial analysis direction")
            response2, _ = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Focusing on configuration architecture patterns",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Architecture seems overly complex, but need to look more carefully at security issues",
                    "files_checked": [self.config_file],
                    "relevant_files": [self.config_file],
                    "issues_found": [
                        {"severity": "medium", "description": "Complex configuration hierarchy"},
                    ],
                    "confidence": "low",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            # Step 3: Shift focus based on new evidence
            self.logger.info("    1.2.3: Step 3 - Refocus on security issues")
            response3, _ = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Refocusing - need to concentrate on the critical security issues I initially missed. Found hardcoded secrets and credentials in plain text.",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Found critical security vulnerabilities: hardcoded DATABASE_PASSWORD and SECRET_KEY in plain text",
                    "files_checked": [self.config_file],
                    "relevant_files": [self.config_file],
                    "relevant_context": ["ConfigurationManager.__init__"],
                    "issues_found": [
                        {"severity": "critical", "description": "Hardcoded database password in source code"},
                        {"severity": "critical", "description": "Hardcoded secret key in source code"},
                        {"severity": "high", "description": "Over-engineered configuration system"},
                    ],
                    "confidence": "high",
                    "continuation_id": continuation_id,
                },
            )

            if not response3:
                self.logger.error("Failed to refocus")
                return False

            response3_data = self._parse_review_response(response3)
            if not self._validate_step_response(response3_data, 3, 4, True, "pause_for_code_review"):
                return False

            self.logger.info("    ✅ Refocus flow working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Refocus test failed: {e}")
            return False

    def _test_complete_review_with_analysis(self) -> bool:
        """Test complete code review ending with expert analysis"""
        try:
            self.logger.info("  1.3: Testing complete review with expert analysis")

            # Use the continuation from first test
            continuation_id = getattr(self, "review_continuation_id", None)
            if not continuation_id:
                # Start fresh if no continuation available
                self.logger.info("    1.3.0: Starting fresh review")
                response0, continuation_id = self.call_mcp_tool(
                    "codereview",
                    {
                        "step": "Reviewing payment processor for security and quality issues",
                        "step_number": 1,
                        "total_steps": 2,
                        "next_step_required": True,
                        "findings": "Found multiple security and performance issues",
                        "files_checked": [self.payment_file],
                        "relevant_files": [self.payment_file],
                        "absolute_file_paths": [self.payment_file],
                        "relevant_context": ["PaymentProcessor.process_payment"],
                    },
                )
                if not response0 or not continuation_id:
                    self.logger.error("Failed to start fresh review")
                    return False

            # Final step - trigger expert analysis
            self.logger.info("    1.3.1: Final step - complete review")
            response_final, _ = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Code review complete. Identified comprehensive security, performance, and maintainability issues throughout the payment processing module.",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step - triggers expert analysis
                    "findings": "Complete analysis reveals critical security vulnerabilities, performance bottlenecks, over-engineering patterns, and maintainability concerns. All issues documented with severity levels.",
                    "files_checked": [self.payment_file],
                    "relevant_files": [self.payment_file],
                    "relevant_context": [
                        "PaymentProcessor.process_payment",
                        "PaymentProcessor._generate_complex_hash",
                        "PaymentProcessor.get_payment_history",
                    ],
                    "issues_found": [
                        {"severity": "critical", "description": "API key stored in plain text"},
                        {"severity": "critical", "description": "Sensitive payment data logged"},
                        {"severity": "high", "description": "SQL injection vulnerability potential"},
                        {"severity": "medium", "description": "Over-engineered hash generation"},
                        {"severity": "low", "description": "Poor error handling patterns"},
                    ],
                    "confidence": "high",
                    "continuation_id": continuation_id,
                    "model": "flash",  # Use flash for expert analysis
                },
            )

            if not response_final:
                self.logger.error("Failed to complete review")
                return False

            response_final_data = self._parse_review_response(response_final)
            if not response_final_data:
                return False

            # Validate final response structure - expect calling_expert_analysis for next_step_required=False
            if response_final_data.get("status") != "calling_expert_analysis":
                self.logger.error(
                    f"Expected status 'calling_expert_analysis', got '{response_final_data.get('status')}'"
                )
                return False

            if not response_final_data.get("code_review_complete"):
                self.logger.error("Expected code_review_complete=true for final step")
                return False

            # Check for expert analysis
            if "expert_analysis" not in response_final_data:
                self.logger.error("Missing expert_analysis in final response")
                return False

            expert_analysis = response_final_data.get("expert_analysis", {})

            # Check for expected analysis content (checking common patterns)
            analysis_text = json.dumps(expert_analysis, ensure_ascii=False).lower()

            # Look for code review identification
            review_indicators = ["security", "vulnerability", "performance", "critical", "api", "key"]
            found_indicators = sum(1 for indicator in review_indicators if indicator in analysis_text)

            if found_indicators >= 3:
                self.logger.info("    ✅ Expert analysis identified the issues correctly")
            else:
                self.logger.warning(
                    f"    ⚠️ Expert analysis may not have fully identified the issues (found {found_indicators}/6 indicators)"
                )

            # Check complete review summary
            if "complete_code_review" not in response_final_data:
                self.logger.error("Missing complete_code_review in final response")
                return False

            complete_review = response_final_data["complete_code_review"]
            if not complete_review.get("relevant_context"):
                self.logger.error("Missing relevant context in complete review")
                return False

            if "PaymentProcessor.process_payment" not in complete_review["relevant_context"]:
                self.logger.error("Expected method not found in review summary")
                return False

            self.logger.info("    ✅ Complete review with expert analysis successful")
            return True

        except Exception as e:
            self.logger.error(f"Complete review test failed: {e}")
            return False

    def _test_certain_confidence(self) -> bool:
        """Test certain confidence behavior - should skip expert analysis"""
        try:
            self.logger.info("  1.4: Testing certain confidence behavior")

            # Test certain confidence - should skip expert analysis
            self.logger.info("    1.4.1: Certain confidence review")
            response_certain, _ = self.call_mcp_tool(
                "codereview",
                {
                    "step": "I have completed a thorough code review with 100% certainty of all issues identified.",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,  # Final step
                    "findings": "Complete review identified all critical security issues, performance problems, and code quality concerns. All issues are documented with clear severity levels and specific recommendations.",
                    "files_checked": [self.payment_file],
                    "relevant_files": [self.payment_file],
                    "absolute_file_paths": [self.payment_file],
                    "relevant_context": ["PaymentProcessor.process_payment"],
                    "issues_found": [
                        {"severity": "critical", "description": "Hardcoded API key security vulnerability"},
                        {"severity": "high", "description": "Performance bottleneck in payment history"},
                    ],
                    "review_validation_type": "internal",  # This should skip expert analysis
                    "model": "flash",
                },
            )

            if not response_certain:
                self.logger.error("Failed to test certain confidence")
                return False

            response_certain_data = self._parse_review_response(response_certain)
            if not response_certain_data:
                return False

            # Validate certain confidence response - should skip expert analysis
            if response_certain_data.get("status") != "code_review_complete_ready_for_implementation":
                self.logger.error(
                    f"Expected status 'code_review_complete_ready_for_implementation', got '{response_certain_data.get('status')}'"
                )
                return False

            if not response_certain_data.get("skip_expert_analysis"):
                self.logger.error("Expected skip_expert_analysis=true for certain confidence")
                return False

            expert_analysis = response_certain_data.get("expert_analysis", {})
            if expert_analysis.get("status") not in [
                "skipped_due_to_certain_review_confidence",
                "skipped_due_to_internal_analysis_type",
            ]:
                self.logger.error("Expert analysis should be skipped for certain confidence")
                return False

            self.logger.info("    ✅ Certain confidence behavior working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Certain confidence test failed: {e}")
            return False

    def _test_context_aware_file_embedding(self) -> bool:
        """Test context-aware file embedding optimization"""
        try:
            self.logger.info("  1.5: Testing context-aware file embedding")

            # Create multiple test files for context testing
            utils_content = """#!/usr/bin/env python3
def calculate_discount(price, discount_percent):
    \"\"\"Calculate discount amount\"\"\"
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Invalid discount percentage")

    return price * (discount_percent / 100)

def format_currency(amount):
    \"\"\"Format amount as currency\"\"\"
    return f"${amount:.2f}"
"""

            validator_content = """#!/usr/bin/env python3
import re

def validate_email(email):
    \"\"\"Validate email format\"\"\"
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_credit_card(card_number):
    \"\"\"Basic credit card validation\"\"\"
    # Remove spaces and dashes
    card_number = re.sub(r'[\\s-]', '', card_number)

    # Check if all digits
    if not card_number.isdigit():
        return False

    # Basic length check
    return len(card_number) in [13, 14, 15, 16]
"""

            # Create test files
            utils_file = self.create_additional_test_file("utils.py", utils_content)
            validator_file = self.create_additional_test_file("validator.py", validator_content)

            # Test 1: New conversation, intermediate step - should only reference files
            self.logger.info("    1.5.1: New conversation intermediate step (should reference only)")
            response1, continuation_id = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Starting comprehensive code review of utility modules",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,  # Intermediate step
                    "findings": "Initial analysis of utility and validation functions",
                    "files_checked": [utils_file, validator_file],
                    "relevant_files": [utils_file],  # This should be referenced, not embedded
                    "absolute_file_paths": [utils_file, validator_file],  # Required for step 1
                    "relevant_context": ["calculate_discount"],
                    "confidence": "low",
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start context-aware file embedding test")
                return False

            response1_data = self._parse_review_response(response1)
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

            # Test 2: Final step - should embed files for expert analysis
            self.logger.info("    1.5.2: Final step (should embed files)")
            response3, _ = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Code review complete - identified all issues and recommendations",
                    "step_number": 3,
                    "total_steps": 3,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Complete review: utility functions have proper error handling, validation functions are robust",
                    "files_checked": [utils_file, validator_file],
                    "relevant_files": [utils_file, validator_file],  # Should be fully embedded
                    "relevant_context": ["calculate_discount", "validate_email", "validate_credit_card"],
                    "issues_found": [
                        {"severity": "low", "description": "Could add more comprehensive email validation"},
                        {"severity": "medium", "description": "Credit card validation logic could be more robust"},
                    ],
                    "confidence": "medium",
                    "model": "flash",
                },
            )

            if not response3:
                self.logger.error("Failed to complete to final step")
                return False

            response3_data = self._parse_review_response(response3)
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

            # Use existing payment and config files for multi-step test
            files_to_review = [self.payment_file, self.config_file]

            # Step 1: Start review (new conversation)
            self.logger.info("    1.6.1: Step 1 - Start comprehensive review")
            response1, continuation_id = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Starting comprehensive security and quality review of payment system components",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial review of payment processor and configuration management modules",
                    "files_checked": files_to_review,
                    "relevant_files": [self.payment_file],
                    "absolute_file_paths": files_to_review,
                    "relevant_context": [],
                    "confidence": "low",
                    "review_type": "security",
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start multi-step file context test")
                return False

            response1_data = self._parse_review_response(response1)

            # Validate step 1 - should use reference_only
            file_context1 = response1_data.get("file_context", {})
            if file_context1.get("type") != "reference_only":
                self.logger.error("Step 1 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 1: reference_only file context")

            # Step 2: Security analysis
            self.logger.info("    1.6.2: Step 2 - Security analysis")
            response2, _ = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Focusing on critical security vulnerabilities across both modules",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                    "findings": "Found critical security issues: hardcoded secrets in config, API key exposure in payment processor",
                    "files_checked": files_to_review,
                    "relevant_files": files_to_review,
                    "relevant_context": ["PaymentProcessor.__init__", "ConfigurationManager"],
                    "issues_found": [
                        {"severity": "critical", "description": "Hardcoded database password"},
                        {"severity": "critical", "description": "API key stored in plain text"},
                    ],
                    "confidence": "medium",
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            response2_data = self._parse_review_response(response2)

            # Validate step 2 - should still use reference_only
            file_context2 = response2_data.get("file_context", {})
            if file_context2.get("type") != "reference_only":
                self.logger.error("Step 2 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 2: reference_only file context")

            # Step 3: Performance and architecture analysis
            self.logger.info("    1.6.3: Step 3 - Performance and architecture analysis")
            response3, _ = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Analyzing performance bottlenecks and architectural concerns",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                    "findings": "Performance issues: unbounded lists, inefficient algorithms, over-engineered patterns",
                    "files_checked": files_to_review,
                    "relevant_files": files_to_review,
                    "relevant_context": [
                        "PaymentProcessor.get_payment_history",
                        "PaymentProcessor._generate_complex_hash",
                    ],
                    "issues_found": [
                        {"severity": "high", "description": "O(n²) algorithm in payment history"},
                        {"severity": "medium", "description": "Over-engineered hash generation"},
                        {"severity": "medium", "description": "Unbounded failed_payments list"},
                    ],
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response3:
                self.logger.error("Failed to continue to step 3")
                return False

            response3_data = self._parse_review_response(response3)

            # Validate step 3 - should still use reference_only
            file_context3 = response3_data.get("file_context", {})
            if file_context3.get("type") != "reference_only":
                self.logger.error("Step 3 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 3: reference_only file context")

            # Step 4: Final comprehensive analysis
            self.logger.info("    1.6.4: Step 4 - Final comprehensive analysis")
            response4, _ = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Code review complete - comprehensive analysis of all security, performance, and quality issues",
                    "step_number": 4,
                    "total_steps": 4,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Complete review: identified critical security vulnerabilities, performance bottlenecks, over-engineering patterns, and maintainability concerns across payment and configuration modules.",
                    "files_checked": files_to_review,
                    "relevant_files": files_to_review,
                    "relevant_context": ["PaymentProcessor.process_payment", "ConfigurationManager.get_config"],
                    "issues_found": [
                        {"severity": "critical", "description": "Multiple hardcoded secrets"},
                        {"severity": "high", "description": "Performance and security issues in payment processing"},
                        {"severity": "medium", "description": "Over-engineered architecture patterns"},
                    ],
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response4:
                self.logger.error("Failed to complete to final step")
                return False

            response4_data = self._parse_review_response(response4)

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

            # Check that expert analysis has content
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

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool in-process - override for codereview-specific response handling"""
        # Use in-process implementation to maintain conversation memory
        response_text, _ = self.call_mcp_tool_direct(tool_name, params)

        if not response_text:
            return None, None

        # Extract continuation_id from codereview response specifically
        continuation_id = self._extract_review_continuation_id(response_text)

        return response_text, continuation_id

    def _extract_review_continuation_id(self, response_text: str) -> Optional[str]:
        """Extract continuation_id from codereview response"""
        try:
            # Parse the response
            response_data = json.loads(response_text)
            return response_data.get("continuation_id")

        except json.JSONDecodeError as e:
            self.logger.debug(f"Failed to parse response for review continuation_id: {e}")
            return None

    def _parse_review_response(self, response_text: str) -> dict:
        """Parse codereview tool JSON response"""
        try:
            # Parse the response - it should be direct JSON
            return json.loads(response_text)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse review response as JSON: {e}")
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
        """Validate a codereview step response structure"""
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

            # Check code_review_status exists
            if "code_review_status" not in response_data:
                self.logger.error("Missing code_review_status in response")
                return False

            # Check next_steps guidance
            if not response_data.get("next_steps"):
                self.logger.error("Missing next_steps guidance in response")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating step response: {e}")
            return False
