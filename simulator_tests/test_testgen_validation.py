#!/usr/bin/env python3
"""
TestGen Tool Validation Test

Tests the testgen tool's capabilities using the workflow architecture.
This validates that the workflow-based implementation guides Claude through
systematic test generation analysis before creating comprehensive test suites.
"""

import json
from typing import Optional

from .conversation_base_test import ConversationBaseTest


class TestGenValidationTest(ConversationBaseTest):
    """Test testgen tool with workflow architecture"""

    @property
    def test_name(self) -> str:
        return "testgen_validation"

    @property
    def test_description(self) -> str:
        return "TestGen tool validation with step-by-step test planning"

    def run_test(self) -> bool:
        """Test testgen tool capabilities"""
        # Set up the test environment
        self.setUp()

        try:
            self.logger.info("Test: TestGen tool validation")

            # Create sample code files to test
            self._create_test_code_files()

            # Test 1: Single investigation session with multiple steps
            if not self._test_single_test_generation_session():
                return False

            # Test 2: Test generation with pattern following
            if not self._test_generation_with_pattern_following():
                return False

            # Test 3: Complete test generation with expert analysis
            if not self._test_complete_generation_with_analysis():
                return False

            # Test 4: Certain confidence behavior
            if not self._test_certain_confidence():
                return False

            # Test 5: Context-aware file embedding
            if not self._test_context_aware_file_embedding():
                return False

            # Test 6: Multi-step test planning
            if not self._test_multi_step_test_planning():
                return False

            self.logger.info("  ✅ All testgen validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"TestGen validation test failed: {e}")
            return False

    def _create_test_code_files(self):
        """Create sample code files for test generation"""
        # Create a calculator module with various functions
        calculator_code = """#!/usr/bin/env python3
\"\"\"
Simple calculator module for demonstration
\"\"\"

def add(a, b):
    \"\"\"Add two numbers\"\"\"
    return a + b

def subtract(a, b):
    \"\"\"Subtract b from a\"\"\"
    return a - b

def multiply(a, b):
    \"\"\"Multiply two numbers\"\"\"
    return a * b

def divide(a, b):
    \"\"\"Divide a by b\"\"\"
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def calculate_percentage(value, percentage):
    \"\"\"Calculate percentage of a value\"\"\"
    if percentage < 0:
        raise ValueError("Percentage cannot be negative")
    if percentage > 100:
        raise ValueError("Percentage cannot exceed 100")
    return (value * percentage) / 100

def power(base, exponent):
    \"\"\"Calculate base raised to exponent\"\"\"
    if base == 0 and exponent < 0:
        raise ValueError("Cannot raise 0 to negative power")
    return base ** exponent
"""

        # Create test file
        self.calculator_file = self.create_additional_test_file("calculator.py", calculator_code)
        self.logger.info(f"  ✅ Created calculator module: {self.calculator_file}")

        # Create a simple existing test file to use as pattern
        existing_test = """#!/usr/bin/env python3
import pytest
from calculator import add, subtract

class TestCalculatorBasic:
    \"\"\"Test basic calculator operations\"\"\"

    def test_add_positive_numbers(self):
        \"\"\"Test adding two positive numbers\"\"\"
        assert add(2, 3) == 5
        assert add(10, 20) == 30

    def test_add_negative_numbers(self):
        \"\"\"Test adding negative numbers\"\"\"
        assert add(-5, -3) == -8
        assert add(-10, 5) == -5

    def test_subtract_positive(self):
        \"\"\"Test subtracting positive numbers\"\"\"
        assert subtract(10, 3) == 7
        assert subtract(5, 5) == 0
"""

        self.existing_test_file = self.create_additional_test_file("test_calculator_basic.py", existing_test)
        self.logger.info(f"  ✅ Created existing test file: {self.existing_test_file}")

    def _test_single_test_generation_session(self) -> bool:
        """Test a complete test generation session with multiple steps"""
        try:
            self.logger.info("  1.1: Testing single test generation session")

            # Step 1: Start investigation
            self.logger.info("    1.1.1: Step 1 - Initial test planning")
            response1, continuation_id = self.call_mcp_tool(
                "testgen",
                {
                    "step": "I need to generate comprehensive tests for the calculator module. Let me start by analyzing the code structure and understanding the functionality.",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Calculator module contains 6 functions: add, subtract, multiply, divide, calculate_percentage, and power. Each has specific error conditions that need testing.",
                    "files_checked": [self.calculator_file],
                    "relevant_files": [self.calculator_file],
                    "relevant_context": ["add", "subtract", "multiply", "divide", "calculate_percentage", "power"],
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to get initial test planning response")
                return False

            # Parse and validate JSON response
            response1_data = self._parse_testgen_response(response1)
            if not response1_data:
                return False

            # Validate step 1 response structure
            if not self._validate_step_response(response1_data, 1, 4, True, "pause_for_test_analysis"):
                return False

            self.logger.info(f"    ✅ Step 1 successful, continuation_id: {continuation_id}")

            # Step 2: Analyze test requirements
            self.logger.info("    1.1.2: Step 2 - Test requirements analysis")
            response2, _ = self.call_mcp_tool(
                "testgen",
                {
                    "step": "Now analyzing the test requirements for each function, identifying edge cases and boundary conditions.",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Identified key test scenarios: (1) divide - zero division error, (2) calculate_percentage - negative/over 100 validation, (3) power - zero to negative power error. Need tests for normal cases and edge cases.",
                    "files_checked": [self.calculator_file],
                    "relevant_files": [self.calculator_file],
                    "relevant_context": ["divide", "calculate_percentage", "power"],
                    "confidence": "medium",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue test planning to step 2")
                return False

            response2_data = self._parse_testgen_response(response2)
            if not self._validate_step_response(response2_data, 2, 4, True, "pause_for_test_analysis"):
                return False

            # Check test generation status tracking
            test_status = response2_data.get("test_generation_status", {})
            if test_status.get("test_scenarios_identified", 0) < 3:
                self.logger.error("Test scenarios not properly tracked")
                return False

            if test_status.get("analysis_confidence") != "medium":
                self.logger.error("Confidence level not properly tracked")
                return False

            self.logger.info("    ✅ Step 2 successful with proper tracking")

            # Store continuation_id for next test
            self.test_continuation_id = continuation_id
            return True

        except Exception as e:
            self.logger.error(f"Single test generation session test failed: {e}")
            return False

    def _test_generation_with_pattern_following(self) -> bool:
        """Test test generation following existing patterns"""
        try:
            self.logger.info("  1.2: Testing test generation with pattern following")

            # Start a new investigation with existing test patterns
            self.logger.info("    1.2.1: Start test generation with pattern reference")
            response1, continuation_id = self.call_mcp_tool(
                "testgen",
                {
                    "step": "Generating tests for remaining calculator functions following existing test patterns",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,
                    "findings": "Found existing test pattern using pytest with class-based organization and descriptive test names",
                    "files_checked": [self.calculator_file, self.existing_test_file],
                    "relevant_files": [self.calculator_file, self.existing_test_file],
                    "relevant_context": ["TestCalculatorBasic", "multiply", "divide", "calculate_percentage", "power"],
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start pattern following test")
                return False

            # Step 2: Analyze patterns
            self.logger.info("    1.2.2: Step 2 - Pattern analysis")
            response2, _ = self.call_mcp_tool(
                "testgen",
                {
                    "step": "Analyzing the existing test patterns to maintain consistency",
                    "step_number": 2,
                    "total_steps": 3,
                    "next_step_required": True,
                    "findings": "Existing tests use: class-based organization (TestCalculatorBasic), descriptive method names (test_operation_scenario), multiple assertions per test, pytest framework",
                    "files_checked": [self.existing_test_file],
                    "relevant_files": [self.calculator_file, self.existing_test_file],
                    "confidence": "high",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            self.logger.info("    ✅ Pattern analysis successful")
            return True

        except Exception as e:
            self.logger.error(f"Pattern following test failed: {e}")
            return False

    def _test_complete_generation_with_analysis(self) -> bool:
        """Test complete test generation ending with expert analysis"""
        try:
            self.logger.info("  1.3: Testing complete test generation with expert analysis")

            # Use the continuation from first test or start fresh
            continuation_id = getattr(self, "test_continuation_id", None)
            if not continuation_id:
                # Start fresh if no continuation available
                self.logger.info("    1.3.0: Starting fresh test generation")
                response0, continuation_id = self.call_mcp_tool(
                    "testgen",
                    {
                        "step": "Analyzing calculator module for comprehensive test generation",
                        "step_number": 1,
                        "total_steps": 2,
                        "next_step_required": True,
                        "findings": "Identified 6 functions needing tests with various edge cases",
                        "files_checked": [self.calculator_file],
                        "relevant_files": [self.calculator_file],
                        "relevant_context": ["add", "subtract", "multiply", "divide", "calculate_percentage", "power"],
                    },
                )
                if not response0 or not continuation_id:
                    self.logger.error("Failed to start fresh test generation")
                    return False

            # Final step - trigger expert analysis
            self.logger.info("    1.3.1: Final step - complete test planning")
            response_final, _ = self.call_mcp_tool(
                "testgen",
                {
                    "step": "Test planning complete. Identified all test scenarios including edge cases, error conditions, and boundary values for comprehensive coverage.",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step - triggers expert analysis
                    "findings": "Complete test plan: normal operations, edge cases (zero, negative), error conditions (divide by zero, invalid percentage, zero to negative power), boundary values",
                    "files_checked": [self.calculator_file],
                    "relevant_files": [self.calculator_file],
                    "relevant_context": ["add", "subtract", "multiply", "divide", "calculate_percentage", "power"],
                    "confidence": "high",
                    "continuation_id": continuation_id,
                    "model": "flash",  # Use flash for expert analysis
                },
            )

            if not response_final:
                self.logger.error("Failed to complete test generation")
                return False

            response_final_data = self._parse_testgen_response(response_final)
            if not response_final_data:
                return False

            # Validate final response structure
            if response_final_data.get("status") != "calling_expert_analysis":
                self.logger.error(
                    f"Expected status 'calling_expert_analysis', got '{response_final_data.get('status')}'"
                )
                return False

            if not response_final_data.get("test_generation_complete"):
                self.logger.error("Expected test_generation_complete=true for final step")
                return False

            # Check for expert analysis
            if "expert_analysis" not in response_final_data:
                self.logger.error("Missing expert_analysis in final response")
                return False

            expert_analysis = response_final_data.get("expert_analysis", {})

            # Check for expected analysis content
            analysis_text = json.dumps(expert_analysis, ensure_ascii=False).lower()

            # Look for test generation indicators
            test_indicators = ["test", "edge", "boundary", "error", "coverage", "pytest"]
            found_indicators = sum(1 for indicator in test_indicators if indicator in analysis_text)

            if found_indicators >= 4:
                self.logger.info("    ✅ Expert analysis provided comprehensive test suggestions")
            else:
                self.logger.warning(
                    f"    ⚠️ Expert analysis may not have fully addressed test generation (found {found_indicators}/6 indicators)"
                )

            # Check complete test generation summary
            if "complete_test_generation" not in response_final_data:
                self.logger.error("Missing complete_test_generation in final response")
                return False

            complete_generation = response_final_data["complete_test_generation"]
            if not complete_generation.get("relevant_context"):
                self.logger.error("Missing relevant context in complete test generation")
                return False

            self.logger.info("    ✅ Complete test generation with expert analysis successful")
            return True

        except Exception as e:
            self.logger.error(f"Complete test generation test failed: {e}")
            return False

    def _test_certain_confidence(self) -> bool:
        """Test certain confidence behavior - should skip expert analysis"""
        try:
            self.logger.info("  1.4: Testing certain confidence behavior")

            # Test certain confidence - should skip expert analysis
            self.logger.info("    1.4.1: Certain confidence test generation")
            response_certain, _ = self.call_mcp_tool(
                "testgen",
                {
                    "step": "I have fully analyzed the code and identified all test scenarios with 100% certainty. Test plan is complete.",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,  # Final step
                    "findings": "Complete test coverage plan: all functions covered with normal cases, edge cases, and error conditions. Ready for implementation.",
                    "files_checked": [self.calculator_file],
                    "relevant_files": [self.calculator_file],
                    "relevant_context": ["add", "subtract", "multiply", "divide", "calculate_percentage", "power"],
                    "confidence": "certain",  # This should skip expert analysis
                    "model": "flash",
                },
            )

            if not response_certain:
                self.logger.error("Failed to test certain confidence")
                return False

            response_certain_data = self._parse_testgen_response(response_certain)
            if not response_certain_data:
                return False

            # Validate certain confidence response - should skip expert analysis
            if response_certain_data.get("status") != "test_generation_complete_ready_for_implementation":
                self.logger.error(
                    f"Expected status 'test_generation_complete_ready_for_implementation', got '{response_certain_data.get('status')}'"
                )
                return False

            if not response_certain_data.get("skip_expert_analysis"):
                self.logger.error("Expected skip_expert_analysis=true for certain confidence")
                return False

            expert_analysis = response_certain_data.get("expert_analysis", {})
            if expert_analysis.get("status") != "skipped_due_to_certain_test_confidence":
                self.logger.error("Expert analysis should be skipped for certain confidence")
                return False

            self.logger.info("    ✅ Certain confidence behavior working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Certain confidence test failed: {e}")
            return False

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool in-process - override for testgen-specific response handling"""
        # Use in-process implementation to maintain conversation memory
        response_text, _ = self.call_mcp_tool_direct(tool_name, params)

        if not response_text:
            return None, None

        # Extract continuation_id from testgen response specifically
        continuation_id = self._extract_testgen_continuation_id(response_text)

        return response_text, continuation_id

    def _extract_testgen_continuation_id(self, response_text: str) -> Optional[str]:
        """Extract continuation_id from testgen response"""
        try:
            # Parse the response
            response_data = json.loads(response_text)
            return response_data.get("continuation_id")

        except json.JSONDecodeError as e:
            self.logger.debug(f"Failed to parse response for testgen continuation_id: {e}")
            return None

    def _parse_testgen_response(self, response_text: str) -> dict:
        """Parse testgen tool JSON response"""
        try:
            # Parse the response - it should be direct JSON
            return json.loads(response_text)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse testgen response as JSON: {e}")
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
        """Validate a test generation step response structure"""
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

            # Check test_generation_status exists
            if "test_generation_status" not in response_data:
                self.logger.error("Missing test_generation_status in response")
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

            # Create additional test files
            utils_code = """#!/usr/bin/env python3
def validate_number(n):
    \"\"\"Validate if input is a number\"\"\"
    return isinstance(n, (int, float))

def format_result(result):
    \"\"\"Format calculation result\"\"\"
    if isinstance(result, float):
        return round(result, 2)
    return result
"""

            math_helpers_code = """#!/usr/bin/env python3
import math

def factorial(n):
    \"\"\"Calculate factorial of n\"\"\"
    if n < 0:
        raise ValueError("Factorial not defined for negative numbers")
    return math.factorial(n)

def is_prime(n):
    \"\"\"Check if number is prime\"\"\"
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True
"""

            # Create test files
            utils_file = self.create_additional_test_file("utils.py", utils_code)
            math_file = self.create_additional_test_file("math_helpers.py", math_helpers_code)

            # Test 1: New conversation, intermediate step - should only reference files
            self.logger.info("    1.5.1: New conversation intermediate step (should reference only)")
            response1, continuation_id = self.call_mcp_tool(
                "testgen",
                {
                    "step": "Starting test generation for utility modules",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,  # Intermediate step
                    "findings": "Initial analysis of utility functions",
                    "files_checked": [utils_file, math_file],
                    "relevant_files": [utils_file],  # This should be referenced, not embedded
                    "relevant_context": ["validate_number", "format_result"],
                    "confidence": "low",
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start context-aware file embedding test")
                return False

            response1_data = self._parse_testgen_response(response1)
            if not response1_data:
                return False

            # Check file context - should be reference_only for intermediate step
            file_context = response1_data.get("file_context", {})
            if file_context.get("type") != "reference_only":
                self.logger.error(f"Expected reference_only file context, got: {file_context.get('type')}")
                return False

            self.logger.info("    ✅ Intermediate step correctly uses reference_only file context")

            # Test 2: Final step - should embed files for expert analysis
            self.logger.info("    1.5.2: Final step (should embed files)")
            response2, _ = self.call_mcp_tool(
                "testgen",
                {
                    "step": "Test planning complete - all test scenarios identified",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Complete test plan for all utility functions with edge cases",
                    "files_checked": [utils_file, math_file],
                    "relevant_files": [utils_file, math_file],  # Should be fully embedded
                    "relevant_context": ["validate_number", "format_result", "factorial", "is_prime"],
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to complete to final step")
                return False

            response2_data = self._parse_testgen_response(response2)
            if not response2_data:
                return False

            # Check file context - should be fully_embedded for final step
            file_context2 = response2_data.get("file_context", {})
            if file_context2.get("type") != "fully_embedded":
                self.logger.error(
                    f"Expected fully_embedded file context for final step, got: {file_context2.get('type')}"
                )
                return False

            # Verify expert analysis was called for final step
            if response2_data.get("status") != "calling_expert_analysis":
                self.logger.error("Final step should trigger expert analysis")
                return False

            self.logger.info("    ✅ Context-aware file embedding test completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Context-aware file embedding test failed: {e}")
            return False

    def _test_multi_step_test_planning(self) -> bool:
        """Test multi-step test planning with complex code"""
        try:
            self.logger.info("  1.6: Testing multi-step test planning")

            # Create a complex class to test
            complex_code = """#!/usr/bin/env python3
import asyncio
from typing import List, Dict, Optional

class DataProcessor:
    \"\"\"Complex data processor with async operations\"\"\"

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.processed_count = 0
        self.error_count = 0
        self.cache: Dict[str, any] = {}

    async def process_batch(self, items: List[dict]) -> List[dict]:
        \"\"\"Process a batch of items asynchronously\"\"\"
        if not items:
            return []

        if len(items) > self.batch_size:
            raise ValueError(f"Batch size {len(items)} exceeds limit {self.batch_size}")

        results = []
        for item in items:
            try:
                result = await self._process_single_item(item)
                results.append(result)
                self.processed_count += 1
            except Exception as e:
                self.error_count += 1
                results.append({"error": str(e), "item": item})

        return results

    async def _process_single_item(self, item: dict) -> dict:
        \"\"\"Process a single item with caching\"\"\"
        item_id = item.get('id')
        if not item_id:
            raise ValueError("Item must have an ID")

        # Check cache
        if item_id in self.cache:
            return self.cache[item_id]

        # Simulate async processing
        await asyncio.sleep(0.01)

        processed = {
            'id': item_id,
            'processed': True,
            'value': item.get('value', 0) * 2
        }

        # Cache result
        self.cache[item_id] = processed
        return processed

    def get_stats(self) -> Dict[str, int]:
        \"\"\"Get processing statistics\"\"\"
        return {
            'processed': self.processed_count,
            'errors': self.error_count,
            'cache_size': len(self.cache),
            'success_rate': self.processed_count / (self.processed_count + self.error_count) if (self.processed_count + self.error_count) > 0 else 0
        }
"""

            # Create test file
            processor_file = self.create_additional_test_file("data_processor.py", complex_code)

            # Step 1: Start investigation
            self.logger.info("    1.6.1: Step 1 - Start complex test planning")
            response1, continuation_id = self.call_mcp_tool(
                "testgen",
                {
                    "step": "Analyzing complex DataProcessor class for comprehensive test generation",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "DataProcessor is an async class with caching, error handling, and statistics. Need async test patterns.",
                    "files_checked": [processor_file],
                    "relevant_files": [processor_file],
                    "relevant_context": ["DataProcessor", "process_batch", "_process_single_item", "get_stats"],
                    "confidence": "low",
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start multi-step test planning")
                return False

            response1_data = self._parse_testgen_response(response1)

            # Validate step 1
            file_context1 = response1_data.get("file_context", {})
            if file_context1.get("type") != "reference_only":
                self.logger.error("Step 1 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 1: Started complex test planning")

            # Step 2: Analyze async patterns
            self.logger.info("    1.6.2: Step 2 - Async pattern analysis")
            response2, _ = self.call_mcp_tool(
                "testgen",
                {
                    "step": "Analyzing async patterns and edge cases for testing",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                    "findings": "Key test areas: async batch processing, cache behavior, error handling, batch size limits, empty items, statistics calculation",
                    "files_checked": [processor_file],
                    "relevant_files": [processor_file],
                    "relevant_context": ["process_batch", "_process_single_item"],
                    "confidence": "medium",
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            self.logger.info("    ✅ Step 2: Async patterns analyzed")

            # Step 3: Edge case identification
            self.logger.info("    1.6.3: Step 3 - Edge case identification")
            response3, _ = self.call_mcp_tool(
                "testgen",
                {
                    "step": "Identifying all edge cases and boundary conditions",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                    "findings": "Edge cases: empty batch, oversized batch, items without ID, cache hits/misses, concurrent processing, error accumulation",
                    "files_checked": [processor_file],
                    "relevant_files": [processor_file],
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response3:
                self.logger.error("Failed to continue to step 3")
                return False

            self.logger.info("    ✅ Step 3: Edge cases identified")

            # Step 4: Final test plan with expert analysis
            self.logger.info("    1.6.4: Step 4 - Complete test plan")
            response4, _ = self.call_mcp_tool(
                "testgen",
                {
                    "step": "Test planning complete with comprehensive coverage strategy",
                    "step_number": 4,
                    "total_steps": 4,
                    "next_step_required": False,  # Final step
                    "continuation_id": continuation_id,
                    "findings": "Complete async test suite plan: unit tests for each method, integration tests for batch processing, edge case coverage, performance tests",
                    "files_checked": [processor_file],
                    "relevant_files": [processor_file],
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response4:
                self.logger.error("Failed to complete to final step")
                return False

            response4_data = self._parse_testgen_response(response4)

            # Validate final step
            if response4_data.get("status") != "calling_expert_analysis":
                self.logger.error("Final step should trigger expert analysis")
                return False

            file_context4 = response4_data.get("file_context", {})
            if file_context4.get("type") != "fully_embedded":
                self.logger.error("Final step should use fully_embedded file context")
                return False

            self.logger.info("    ✅ Multi-step test planning completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Multi-step test planning test failed: {e}")
            return False
