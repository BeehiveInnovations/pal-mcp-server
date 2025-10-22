#!/usr/bin/env python3
"""
Refactor Tool Validation Test

Tests the refactor tool's capabilities using the new workflow architecture.
This validates the step-by-step refactoring analysis pattern with expert validation.
"""

import json
from typing import Optional

from .conversation_base_test import ConversationBaseTest


class RefactorValidationTest(ConversationBaseTest):
    """Test refactor tool with new workflow architecture"""

    @property
    def test_name(self) -> str:
        return "refactor_validation"

    @property
    def test_description(self) -> str:
        return "Refactor tool validation with new workflow architecture"

    def run_test(self) -> bool:
        """Test refactor tool capabilities"""
        # Set up the test environment
        self.setUp()

        try:
            self.logger.info("Test: Refactor tool validation (new architecture)")

            # Create test files with refactoring opportunities
            self._create_refactoring_test_code()

            # Test 1: Single refactoring analysis session with multiple steps
            if not self._test_single_refactoring_session():
                return False

            # Test 2: Refactoring analysis requiring refocus
            if not self._test_refactoring_refocus_flow():
                return False

            # Test 3: Complete refactoring analysis with expert analysis
            if not self._test_complete_refactoring_with_analysis():
                return False

            # Test 4: Certain confidence with complete refactor_result_confidence
            if not self._test_certain_confidence_complete_refactoring():
                return False

            # Test 5: Context-aware file embedding for refactoring
            if not self._test_context_aware_refactoring_file_embedding():
                return False

            # Test 6: Different refactor types
            if not self._test_different_refactor_types():
                return False

            self.logger.info("  ✅ All refactor validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"Refactor validation test failed: {e}")
            return False

    def _create_refactoring_test_code(self):
        """Create test files with various refactoring opportunities"""
        # Create a Python file with obvious code smells and decomposition opportunities
        refactor_code = """#!/usr/bin/env python3
import json
import os
from datetime import datetime

# Code smell: Large class with multiple responsibilities
class DataProcessorManager:
    def __init__(self, config_file):
        self.config = self._load_config(config_file)
        self.processed_count = 0
        self.error_count = 0
        self.log_file = "processing.log"

    def _load_config(self, config_file):
        \"\"\"Load configuration from file\"\"\"
        with open(config_file, 'r') as f:
            return json.load(f)

    # Code smell: Long method doing too many things (decompose opportunity)
    def process_user_data(self, user_data, validation_rules, output_format):
        \"\"\"Process user data with validation and formatting\"\"\"
        # Validation logic
        if not user_data:
            print("Error: No user data")  # Code smell: print instead of logging
            return None

        if not isinstance(user_data, dict):
            print("Error: Invalid data format")
            return None

        # Check required fields
        required_fields = ['name', 'email', 'age']
        for field in required_fields:
            if field not in user_data:
                print(f"Error: Missing field {field}")
                return None

        # Apply validation rules
        for rule in validation_rules:
            if rule['field'] == 'email':
                if '@' not in user_data['email']:  # Code smell: simple validation
                    print("Error: Invalid email")
                    return None
            elif rule['field'] == 'age':
                if user_data['age'] < 18:  # Code smell: magic number
                    print("Error: Age too young")
                    return None

        # Data processing
        processed_data = {}
        processed_data['full_name'] = user_data['name'].title()
        processed_data['email_domain'] = user_data['email'].split('@')[1]
        processed_data['age_category'] = 'adult' if user_data['age'] >= 18 else 'minor'

        # Code smell: Duplicate date formatting logic
        if output_format == 'json':
            processed_data['processed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            result = json.dumps(processed_data, ensure_ascii=False)
        elif output_format == 'csv':
            processed_data['processed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            result = f"{processed_data['full_name']},{processed_data['email_domain']},{processed_data['age_category']}"
        else:
            processed_data['processed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            result = str(processed_data)

        # Logging and statistics
        self.processed_count += 1
        with open(self.log_file, 'a') as f:  # Code smell: file handling without context
            f.write(f"Processed: {user_data['name']} at {datetime.now()}\\n")

        return result

    # Code smell: Another long method (decompose opportunity)
    def batch_process_files(self, file_list, output_dir):
        \"\"\"Process multiple files in batch\"\"\"
        results = []

        for file_path in file_list:
            # File validation
            if not os.path.exists(file_path):
                print(f"Error: File {file_path} not found")
                continue

            if not file_path.endswith('.json'):
                print(f"Error: File {file_path} is not JSON")
                continue

            # Read and process file
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)

                # Code smell: Nested loops and complex logic
                for user_id, user_data in data.items():
                    if isinstance(user_data, dict):
                        # Duplicate validation logic from process_user_data
                        if 'name' in user_data and 'email' in user_data:
                            if '@' in user_data['email']:
                                # More processing...
                                processed = {
                                    'id': user_id,
                                    'name': user_data['name'].title(),
                                    'email': user_data['email'].lower()
                                }
                                results.append(processed)

                # Write output file
                output_file = os.path.join(output_dir, f"processed_{os.path.basename(file_path)}")
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2)

            except Exception as e:
                print(f"Error processing file {file_path}: {e}")
                self.error_count += 1

        return results

    # Code smell: Method doing file I/O and business logic
    def generate_report(self):
        \"\"\"Generate processing report\"\"\"
        report_data = {
            'total_processed': self.processed_count,
            'total_errors': self.error_count,
            'success_rate': (self.processed_count / (self.processed_count + self.error_count)) * 100 if (self.processed_count + self.error_count) > 0 else 0,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Write to multiple formats (code smell: duplicate logic)
        with open('report.json', 'w') as f:
            json.dump(report_data, f, indent=2)

        with open('report.txt', 'w') as f:
            f.write(f"Processing Report\\n")
            f.write(f"================\\n")
            f.write(f"Total Processed: {report_data['total_processed']}\\n")
            f.write(f"Total Errors: {report_data['total_errors']}\\n")
            f.write(f"Success Rate: {report_data['success_rate']:.2f}%\\n")
            f.write(f"Generated: {report_data['generated_at']}\\n")

        return report_data

# Code smell: Utility functions that could be in a separate module
def validate_email(email):
    \"\"\"Simple email validation\"\"\"
    return '@' in email and '.' in email

def format_name(name):
    \"\"\"Format name to title case\"\"\"
    return name.title() if name else ""

def calculate_age_category(age):
    \"\"\"Calculate age category\"\"\"
    if age < 18:
        return 'minor'
    elif age < 65:
        return 'adult'
    else:
        return 'senior'
"""

        # Create test file with refactoring opportunities
        self.refactor_file = self.create_additional_test_file("data_processor_manager.py", refactor_code)
        self.logger.info(f"  ✅ Created test file with refactoring opportunities: {self.refactor_file}")

        # Create a smaller file for focused testing
        small_refactor_code = """#!/usr/bin/env python3

# Code smell: God function
def process_everything(data, config, logger):
    \"\"\"Function that does too many things\"\"\"
    # Validation
    if not data:
        print("No data")  # Should use logger
        return None

    # Processing
    result = []
    for item in data:
        if item > 5:  # Magic number
            result.append(item * 2)  # Magic number

    # Logging
    print(f"Processed {len(result)} items")

    # File I/O
    with open("output.txt", "w") as f:
        f.write(str(result))

    return result

# Modernization opportunity: Could use dataclass
class UserData:
    def __init__(self, name, email, age):
        self.name = name
        self.email = email
        self.age = age

    def to_dict(self):
        return {
            'name': self.name,
            'email': self.email,
            'age': self.age
        }
"""

        self.small_refactor_file = self.create_additional_test_file("simple_processor.py", small_refactor_code)
        self.logger.info(f"  ✅ Created small test file: {self.small_refactor_file}")

    def _test_single_refactoring_session(self) -> bool:
        """Test a complete refactoring analysis session with multiple steps"""
        try:
            self.logger.info("  1.1: Testing single refactoring analysis session")

            # Step 1: Start refactoring analysis
            self.logger.info("    1.1.1: Step 1 - Initial refactoring investigation")
            response1, continuation_id = self.call_mcp_tool(
                "refactor",
                {
                    "step": "Starting refactoring analysis of the data processor code. Let me examine the code structure and identify opportunities for decomposition, code smell fixes, and modernization.",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial scan shows a large DataProcessorManager class with multiple responsibilities. The class handles configuration, data processing, file I/O, and logging - violating single responsibility principle.",
                    "files_checked": [self.refactor_file],
                    "relevant_files": [self.refactor_file],
                    "confidence": "incomplete",
                    "refactor_type": "codesmells",
                    "focus_areas": ["maintainability", "readability"],
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to get initial refactoring response")
                return False

            # Parse and validate JSON response
            response1_data = self._parse_refactor_response(response1)
            if not response1_data:
                return False

            # Validate step 1 response structure - expect pause_for_refactoring_analysis for next_step_required=True
            if not self._validate_refactoring_step_response(
                response1_data, 1, 4, True, "pause_for_refactoring_analysis"
            ):
                return False

            self.logger.info(f"    ✅ Step 1 successful, continuation_id: {continuation_id}")

            # Step 2: Deeper analysis
            self.logger.info("    1.1.2: Step 2 - Detailed code analysis")
            response2, _ = self.call_mcp_tool(
                "refactor",
                {
                    "step": "Now examining the specific methods and identifying concrete refactoring opportunities. Found multiple code smells and decomposition needs.",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Identified several major issues: 1) process_user_data method is 50+ lines doing validation, processing, and I/O. 2) Duplicate validation logic. 3) Magic numbers (18 for age). 4) print statements instead of proper logging. 5) File handling without proper context management.",
                    "files_checked": [self.refactor_file],
                    "relevant_files": [self.refactor_file],
                    "relevant_context": [
                        "DataProcessorManager.process_user_data",
                        "DataProcessorManager.batch_process_files",
                    ],
                    "issues_found": [
                        {
                            "type": "codesmells",
                            "severity": "high",
                            "description": "Long method: process_user_data does too many things",
                        },
                        {
                            "type": "codesmells",
                            "severity": "medium",
                            "description": "Magic numbers: age validation uses hardcoded 18",
                        },
                        {
                            "type": "codesmells",
                            "severity": "medium",
                            "description": "Duplicate validation logic in multiple places",
                        },
                    ],
                    "confidence": "partial",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue refactoring analysis to step 2")
                return False

            response2_data = self._parse_refactor_response(response2)
            if not self._validate_refactoring_step_response(
                response2_data, 2, 4, True, "pause_for_refactoring_analysis"
            ):
                return False

            # Check refactoring status tracking
            refactoring_status = response2_data.get("refactoring_status", {})
            if refactoring_status.get("files_checked", 0) < 1:
                self.logger.error("Files checked count not properly tracked")
                return False

            opportunities_by_type = refactoring_status.get("opportunities_by_type", {})
            if "codesmells" not in opportunities_by_type:
                self.logger.error("Code smells not properly tracked in opportunities")
                return False

            if refactoring_status.get("refactor_confidence") != "partial":
                self.logger.error("Refactor confidence not properly tracked")
                return False

            self.logger.info("    ✅ Step 2 successful with proper refactoring tracking")

            # Store continuation_id for next test
            self.refactoring_continuation_id = continuation_id
            return True

        except Exception as e:
            self.logger.error(f"Single refactoring session test failed: {e}")
            return False

    def _test_refactoring_refocus_flow(self) -> bool:
        """Test refactoring analysis that shifts focus mid-investigation"""
        try:
            self.logger.info("  1.2: Testing refactoring analysis refocus workflow")

            # Start a new refactoring analysis for testing refocus behaviour
            self.logger.info("    1.2.1: Start refactoring analysis for refocus test")
            response1, continuation_id = self.call_mcp_tool(
                "refactor",
                {
                    "step": "Analyzing code for decomposition opportunities",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial focus on class-level decomposition",
                    "files_checked": [self.small_refactor_file],
                    "relevant_files": [self.small_refactor_file],
                    "confidence": "incomplete",
                    "refactor_type": "decompose",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start refocus test refactoring analysis")
                return False

            # Step 2: Wrong direction
            self.logger.info("    1.2.2: Step 2 - Wrong refactoring focus")
            response2, _ = self.call_mcp_tool(
                "refactor",
                {
                    "step": "Focusing on class decomposition strategies",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Class structure seems reasonable, might be looking in wrong direction",
                    "files_checked": [self.small_refactor_file],
                    "relevant_files": [],
                    "confidence": "incomplete",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            # Step 3: Backtrack from step 2
            self.logger.info("    1.2.3: Step 3 - Refocus on function decomposition")
            response3, _ = self.call_mcp_tool(
                "refactor",
                {
                    "step": "Refocusing - the real decomposition opportunity is the god function process_everything. Let me analyze function-level refactoring instead.",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Found the main decomposition opportunity: process_everything function does validation, processing, logging, and file I/O. Should be split into separate functions with single responsibilities.",
                    "files_checked": [self.small_refactor_file],
                    "relevant_files": [self.small_refactor_file],
                    "relevant_context": ["process_everything"],
                    "issues_found": [
                        {
                            "type": "decompose",
                            "severity": "high",
                            "description": "God function: process_everything has multiple responsibilities",
                        },
                        {
                            "type": "codesmells",
                            "severity": "medium",
                            "description": "Magic numbers in processing logic",
                        },
                    ],
                    "confidence": "partial",
                    "continuation_id": continuation_id,
                },
            )

            if not response3:
                self.logger.error("Failed to refocus")
                return False

            response3_data = self._parse_refactor_response(response3)
            if not self._validate_refactoring_step_response(
                response3_data, 3, 4, True, "pause_for_refactoring_analysis"
            ):
                return False

            self.logger.info("    ✅ Refocus working correctly for refactoring analysis")
            return True

        except Exception as e:
            self.logger.error(f"Refocusing test failed: {e}")
            return False

    def _test_complete_refactoring_with_analysis(self) -> bool:
        """Test complete refactoring analysis ending with expert analysis"""
        try:
            self.logger.info("  1.3: Testing complete refactoring analysis with expert analysis")

            # Use the continuation from first test
            continuation_id = getattr(self, "refactoring_continuation_id", None)
            if not continuation_id:
                # Start fresh if no continuation available
                self.logger.info("    1.3.0: Starting fresh refactoring analysis")
                response0, continuation_id = self.call_mcp_tool(
                    "refactor",
                    {
                        "step": "Analyzing the data processor for comprehensive refactoring opportunities",
                        "step_number": 1,
                        "total_steps": 2,
                        "next_step_required": True,
                        "findings": "Found multiple refactoring opportunities in DataProcessorManager",
                        "files_checked": [self.refactor_file],
                        "relevant_files": [self.refactor_file],
                        "relevant_context": ["DataProcessorManager.process_user_data"],
                        "confidence": "partial",
                        "refactor_type": "codesmells",
                    },
                )
                if not response0 or not continuation_id:
                    self.logger.error("Failed to start fresh refactoring analysis")
                    return False

            # Final step - trigger expert analysis
            self.logger.info("    1.3.1: Final step - complete refactoring analysis")
            response_final, _ = self.call_mcp_tool(
                "refactor",
                {
                    "step": "Refactoring analysis complete. Identified comprehensive opportunities for code smell fixes, decomposition, and modernization across the DataProcessorManager class.",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step - triggers expert analysis
                    "findings": "Complete analysis shows: 1) Large class violating SRP, 2) Long methods needing decomposition, 3) Duplicate validation logic, 4) Magic numbers, 5) Poor error handling with print statements, 6) File I/O mixed with business logic. All major refactoring opportunities identified with specific line locations.",
                    "files_checked": [self.refactor_file],
                    "relevant_files": [self.refactor_file],
                    "relevant_context": [
                        "DataProcessorManager.process_user_data",
                        "DataProcessorManager.batch_process_files",
                        "DataProcessorManager.generate_report",
                    ],
                    "issues_found": [
                        {
                            "type": "decompose",
                            "severity": "critical",
                            "description": "Large class with multiple responsibilities",
                        },
                        {
                            "type": "codesmells",
                            "severity": "high",
                            "description": "Long method: process_user_data (50+ lines)",
                        },
                        {"type": "codesmells", "severity": "high", "description": "Duplicate validation logic"},
                        {"type": "codesmells", "severity": "medium", "description": "Magic numbers in age validation"},
                        {
                            "type": "modernize",
                            "severity": "medium",
                            "description": "Use proper logging instead of print statements",
                        },
                    ],
                    "confidence": "partial",  # Use partial to trigger expert analysis
                    "continuation_id": continuation_id,
                    "model": "flash",  # Use flash for expert analysis
                },
            )

            if not response_final:
                self.logger.error("Failed to complete refactoring analysis")
                return False

            response_final_data = self._parse_refactor_response(response_final)
            if not response_final_data:
                return False

            # Validate final response structure - expect calling_expert_analysis or files_required_to_continue
            expected_statuses = ["calling_expert_analysis", "files_required_to_continue"]
            actual_status = response_final_data.get("status")
            if actual_status not in expected_statuses:
                self.logger.error(f"Expected status to be one of {expected_statuses}, got '{actual_status}'")
                return False

            if not response_final_data.get("refactoring_complete"):
                self.logger.error("Expected refactoring_complete=true for final step")
                return False

            # Check for expert analysis or content (depending on status)
            if actual_status == "calling_expert_analysis":
                if "expert_analysis" not in response_final_data:
                    self.logger.error("Missing expert_analysis in final response")
                    return False
                expert_analysis = response_final_data.get("expert_analysis", {})
                analysis_content = json.dumps(expert_analysis, ensure_ascii=False).lower()
            elif actual_status == "files_required_to_continue":
                # For files_required_to_continue, analysis is in content field
                if "content" not in response_final_data:
                    self.logger.error("Missing content in files_required_to_continue response")
                    return False
                expert_analysis = {"content": response_final_data.get("content", "")}
                analysis_content = response_final_data.get("content", "").lower()
            else:
                self.logger.error(f"Unexpected status: {actual_status}")
                return False

            # Check for expected analysis content (checking common patterns)
            analysis_text = analysis_content

            # Look for refactoring identification
            refactor_indicators = ["refactor", "decompose", "code smell", "method", "class", "responsibility"]
            found_indicators = sum(1 for indicator in refactor_indicators if indicator in analysis_text)

            if found_indicators >= 3:
                self.logger.info("    ✅ Expert analysis identified refactoring opportunities correctly")
            else:
                self.logger.warning(
                    f"    ⚠️ Expert analysis may not have fully identified refactoring opportunities (found {found_indicators}/6 indicators)"
                )

            # Check complete refactoring summary
            if "complete_refactoring" not in response_final_data:
                self.logger.error("Missing complete_refactoring in final response")
                return False

            complete_refactoring = response_final_data["complete_refactoring"]
            if not complete_refactoring.get("relevant_context"):
                self.logger.error("Missing relevant context in complete refactoring")
                return False

            if "DataProcessorManager.process_user_data" not in complete_refactoring["relevant_context"]:
                self.logger.error("Expected method not found in refactoring summary")
                return False

            self.logger.info("    ✅ Complete refactoring analysis with expert analysis successful")
            return True

        except Exception as e:
            self.logger.error(f"Complete refactoring analysis test failed: {e}")
            return False

    def _test_certain_confidence_complete_refactoring(self) -> bool:
        """Test complete confidence - should skip expert analysis"""
        try:
            self.logger.info("  1.4: Testing complete confidence behavior")

            # Test complete confidence - should skip expert analysis
            self.logger.info("    1.4.1: Complete confidence refactoring")
            response_certain, _ = self.call_mcp_tool(
                "refactor",
                {
                    "step": "I have completed comprehensive refactoring analysis with 100% certainty: identified all major opportunities including decomposition, code smells, and modernization.",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,  # Final step
                    "findings": "Complete refactoring analysis: 1) DataProcessorManager class needs decomposition into separate responsibilities, 2) process_user_data method needs breaking into validation, processing, and formatting functions, 3) Replace print statements with proper logging, 4) Extract magic numbers to constants, 5) Use dataclasses for modern Python patterns.",
                    "files_checked": [self.small_refactor_file],
                    "relevant_files": [self.small_refactor_file],
                    "relevant_context": ["process_everything", "UserData"],
                    "issues_found": [
                        {"type": "decompose", "severity": "high", "description": "God function needs decomposition"},
                        {"type": "modernize", "severity": "medium", "description": "Use dataclass for UserData"},
                        {"type": "codesmells", "severity": "medium", "description": "Replace print with logging"},
                    ],
                    "confidence": "complete",  # Complete confidence should skip expert analysis
                    "refactor_type": "codesmells",
                    "model": "flash",
                },
            )

            if not response_certain:
                self.logger.error("Failed to test certain confidence with complete refactoring")
                return False

            response_certain_data = self._parse_refactor_response(response_certain)
            if not response_certain_data:
                return False

            # Validate certain confidence response - should skip expert analysis
            if response_certain_data.get("status") != "refactoring_analysis_complete_ready_for_implementation":
                self.logger.error(
                    f"Expected status 'refactoring_analysis_complete_ready_for_implementation', got '{response_certain_data.get('status')}'"
                )
                return False

            if not response_certain_data.get("skip_expert_analysis"):
                self.logger.error("Expected skip_expert_analysis=true for complete confidence")
                return False

            expert_analysis = response_certain_data.get("expert_analysis", {})
            if expert_analysis.get("status") != "skipped_due_to_complete_refactoring_confidence":
                self.logger.error("Expert analysis should be skipped for complete confidence")
                return False

            self.logger.info("    ✅ Complete confidence behavior working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Complete confidence test failed: {e}")
            return False

    def _test_context_aware_refactoring_file_embedding(self) -> bool:
        """Test context-aware file embedding optimization for refactoring workflow"""
        try:
            self.logger.info("  1.5: Testing context-aware file embedding for refactoring")

            # Create multiple test files for context testing
            utils_content = """#!/usr/bin/env python3
# Utility functions with refactoring opportunities

def calculate_total(items):
    \"\"\"Calculate total with magic numbers\"\"\"
    total = 0
    for item in items:
        if item > 10:  # Magic number
            total += item * 1.1  # Magic number for tax
    return total

def format_output(data, format_type):
    \"\"\"Format output - duplicate logic\"\"\"
    if format_type == 'json':
        import json
        return json.dumps(data, ensure_ascii=False)
    elif format_type == 'csv':
        return ','.join(str(v) for v in data.values())
    else:
        return str(data)
"""

            helpers_content = """#!/usr/bin/env python3
# Helper functions that could be modernized

class DataContainer:
    \"\"\"Simple data container - could use dataclass\"\"\"
    def __init__(self, name, value, category):
        self.name = name
        self.value = value
        self.category = category

    def to_dict(self):
        return {
            'name': self.name,
            'value': self.value,
            'category': self.category
        }
"""

            # Create test files
            utils_file = self.create_additional_test_file("utils.py", utils_content)
            helpers_file = self.create_additional_test_file("helpers.py", helpers_content)

            # Test 1: New conversation, intermediate step - should only reference files
            self.logger.info("    1.5.1: New conversation intermediate step (should reference only)")
            response1, continuation_id = self.call_mcp_tool(
                "refactor",
                {
                    "step": "Starting refactoring analysis of utility modules",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,  # Intermediate step
                    "findings": "Initial analysis of utility and helper modules for refactoring opportunities",
                    "files_checked": [utils_file, helpers_file],
                    "relevant_files": [utils_file],  # This should be referenced, not embedded
                    "relevant_context": ["calculate_total"],
                    "confidence": "incomplete",
                    "refactor_type": "codesmells",
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start context-aware file embedding test")
                return False

            response1_data = self._parse_refactor_response(response1)
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
            response2, _ = self.call_mcp_tool(
                "refactor",
                {
                    "step": "Refactoring analysis complete - identified all opportunities",
                    "step_number": 3,
                    "total_steps": 3,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Complete analysis: Found magic numbers in calculate_total, duplicate formatting logic, and modernization opportunity with DataContainer class that could use dataclass.",
                    "files_checked": [utils_file, helpers_file],
                    "relevant_files": [utils_file, helpers_file],  # Should be fully embedded
                    "relevant_context": ["calculate_total", "format_output", "DataContainer"],
                    "issues_found": [
                        {"type": "codesmells", "severity": "medium", "description": "Magic numbers in calculate_total"},
                        {"type": "modernize", "severity": "low", "description": "DataContainer could use dataclass"},
                        {"type": "codesmells", "severity": "low", "description": "Duplicate formatting logic"},
                    ],
                    "confidence": "partial",  # Use partial to trigger expert analysis
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to complete to final step")
                return False

            response2_data = self._parse_refactor_response(response2)
            if not response2_data:
                return False

            # Check file context - should be fully_embedded for final step
            file_context2 = response2_data.get("file_context", {})
            if file_context2.get("type") != "fully_embedded":
                self.logger.error(
                    f"Expected fully_embedded file context for final step, got: {file_context2.get('type')}"
                )
                return False

            if "Full file content embedded for expert analysis" not in file_context2.get("context_optimization", ""):
                self.logger.error("Expected expert analysis optimization message for fully_embedded")
                return False

            self.logger.info("    ✅ Final step correctly uses fully_embedded file context")

            # Verify expert analysis was called for final step (or files_required_to_continue)
            expected_statuses = ["calling_expert_analysis", "files_required_to_continue"]
            actual_status = response2_data.get("status")
            if actual_status not in expected_statuses:
                self.logger.error(f"Expected one of {expected_statuses}, got: {actual_status}")
                return False

            # Handle expert analysis based on status
            if actual_status == "calling_expert_analysis" and "expert_analysis" not in response2_data:
                self.logger.error("Expert analysis should be present in final step with calling_expert_analysis")
                return False

            self.logger.info("    ✅ Context-aware file embedding test for refactoring completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Context-aware refactoring file embedding test failed: {e}")
            return False

    def _test_different_refactor_types(self) -> bool:
        """Test different refactor types (decompose, modernize, organization)"""
        try:
            self.logger.info("  1.6: Testing different refactor types")

            # Test decompose type
            self.logger.info("    1.6.1: Testing decompose refactor type")
            response_decompose, _ = self.call_mcp_tool(
                "refactor",
                {
                    "step": "Analyzing code for decomposition opportunities in large functions and classes",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Found large DataProcessorManager class that violates single responsibility principle and long process_user_data method that needs decomposition.",
                    "files_checked": [self.refactor_file],
                    "relevant_files": [self.refactor_file],
                    "relevant_context": ["DataProcessorManager", "DataProcessorManager.process_user_data"],
                    "issues_found": [
                        {
                            "type": "decompose",
                            "severity": "critical",
                            "description": "Large class with multiple responsibilities",
                        },
                        {
                            "type": "decompose",
                            "severity": "high",
                            "description": "Long method doing validation, processing, and I/O",
                        },
                    ],
                    "confidence": "complete",
                    "refactor_type": "decompose",
                    "model": "flash",
                },
            )

            if not response_decompose:
                self.logger.error("Failed to test decompose refactor type")
                return False

            response_decompose_data = self._parse_refactor_response(response_decompose)

            # Check that decompose type is properly tracked
            refactoring_status = response_decompose_data.get("refactoring_status", {})
            opportunities_by_type = refactoring_status.get("opportunities_by_type", {})
            if "decompose" not in opportunities_by_type:
                self.logger.error("Decompose opportunities not properly tracked")
                return False

            self.logger.info("    ✅ Decompose refactor type working correctly")

            # Test modernize type
            self.logger.info("    1.6.2: Testing modernize refactor type")
            response_modernize, _ = self.call_mcp_tool(
                "refactor",
                {
                    "step": "Analyzing code for modernization opportunities using newer Python features",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Found opportunities to use dataclasses, f-strings, pathlib, and proper logging instead of print statements.",
                    "files_checked": [self.small_refactor_file],
                    "relevant_files": [self.small_refactor_file],
                    "relevant_context": ["UserData", "process_everything"],
                    "issues_found": [
                        {
                            "type": "modernize",
                            "severity": "medium",
                            "description": "UserData class could use @dataclass decorator",
                        },
                        {
                            "type": "modernize",
                            "severity": "medium",
                            "description": "Replace print statements with proper logging",
                        },
                        {"type": "modernize", "severity": "low", "description": "Use pathlib for file operations"},
                    ],
                    "confidence": "complete",
                    "refactor_type": "modernize",
                    "model": "flash",
                },
            )

            if not response_modernize:
                self.logger.error("Failed to test modernize refactor type")
                return False

            response_modernize_data = self._parse_refactor_response(response_modernize)

            # Check that modernize type is properly tracked
            refactoring_status = response_modernize_data.get("refactoring_status", {})
            opportunities_by_type = refactoring_status.get("opportunities_by_type", {})
            if "modernize" not in opportunities_by_type:
                self.logger.error("Modernize opportunities not properly tracked")
                return False

            self.logger.info("    ✅ Modernize refactor type working correctly")

            self.logger.info("    ✅ Different refactor types test completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Different refactor types test failed: {e}")
            return False

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool in-process - override for -specific response handling"""
        # Use in-process implementation to maintain conversation memory
        response_text, _ = self.call_mcp_tool_direct(tool_name, params)

        if not response_text:
            return None, None

        # Extract continuation_id from refactor response specifically
        continuation_id = self._extract_refactor_continuation_id(response_text)

        return response_text, continuation_id

    def _extract_refactor_continuation_id(self, response_text: str) -> Optional[str]:
        """Extract continuation_id from refactor response"""
        try:
            # Parse the response
            response_data = json.loads(response_text)
            return response_data.get("continuation_id")

        except json.JSONDecodeError as e:
            self.logger.debug(f"Failed to parse response for refactor continuation_id: {e}")
            return None

    def _parse_refactor_response(self, response_text: str) -> dict:
        """Parse refactor tool JSON response"""
        try:
            # Parse the response - it should be direct JSON
            return json.loads(response_text)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse refactor response as JSON: {e}")
            self.logger.error(f"Response text: {response_text[:500]}...")
            return {}

    def _validate_refactoring_step_response(
        self,
        response_data: dict,
        expected_step: int,
        expected_total: int,
        expected_next_required: bool,
        expected_status: str,
    ) -> bool:
        """Validate a refactor investigation step response structure"""
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

            # Check refactoring_status exists
            if "refactoring_status" not in response_data:
                self.logger.error("Missing refactoring_status in response")
                return False

            # Check next_steps guidance
            if not response_data.get("next_steps"):
                self.logger.error("Missing next_steps guidance in response")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating refactoring step response: {e}")
            return False
