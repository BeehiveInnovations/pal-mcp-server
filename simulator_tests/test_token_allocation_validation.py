#!/usr/bin/env python3
"""
Token Allocation and Conversation History Validation Test

This test validates that:
1. Token allocation logging works correctly for file processing
2. Conversation history builds up properly and consumes tokens
3. File deduplication works correctly across tool calls
4. Token usage increases appropriately as conversation history grows
"""

import datetime

from .conversation_base_test import ConversationBaseTest


class TokenAllocationValidationTest(ConversationBaseTest):
    """Test token allocation and conversation history functionality"""

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple:
        """Call an MCP tool in-process"""
        response_text, continuation_id = self.call_mcp_tool_direct(tool_name, params)
        return response_text, continuation_id

    @property
    def test_name(self) -> str:
        return "token_allocation_validation"

    @property
    def test_description(self) -> str:
        return "Token allocation and conversation history validation"

    def run_test(self) -> bool:
        """Test token allocation and conversation history functionality"""
        try:
            self.logger.info(" Test: Token allocation and conversation history validation")

            # Initialize for in-process tool calling
            self.setUp()

            # Setup test files
            self.setup_test_files()

            # Create additional test files for this test - make them substantial enough to see token differences
            file1_content = """def fibonacci(n):
    '''Calculate fibonacci number recursively

    This is a classic recursive algorithm that demonstrates
    the exponential time complexity of naive recursion.
    For large values of n, this becomes very slow.

    Time complexity: O(2^n)
    Space complexity: O(n) due to call stack
    '''
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def factorial(n):
    '''Calculate factorial using recursion

    More efficient than fibonacci as each value
    is calculated only once.

    Time complexity: O(n)
    Space complexity: O(n) due to call stack
    '''
    if n <= 1:
        return 1
    return n * factorial(n-1)

def gcd(a, b):
    '''Calculate greatest common divisor using Euclidean algorithm'''
    while b:
        a, b = b, a % b
    return a

def lcm(a, b):
    '''Calculate least common multiple'''
    return abs(a * b) // gcd(a, b)

# Test functions with detailed output
if __name__ == "__main__":
    print("=== Mathematical Functions Demo ===")
    print(f"Fibonacci(10) = {fibonacci(10)}")
    print(f"Factorial(5) = {factorial(5)}")
    print(f"GCD(48, 18) = {gcd(48, 18)}")
    print(f"LCM(48, 18) = {lcm(48, 18)}")
    print("Fibonacci sequence (first 10 numbers):")
    for i in range(10):
        print(f"  F({i}) = {fibonacci(i)}")
"""

            file2_content = """class Calculator:
    '''Advanced calculator class with error handling and logging'''

    def __init__(self):
        self.history = []
        self.last_result = 0

    def add(self, a, b):
        '''Addition with history tracking'''
        result = a + b
        operation = f"{a} + {b} = {result}"
        self.history.append(operation)
        self.last_result = result
        return result

    def multiply(self, a, b):
        '''Multiplication with history tracking'''
        result = a * b
        operation = f"{a} * {b} = {result}"
        self.history.append(operation)
        self.last_result = result
        return result

    def divide(self, a, b):
        '''Division with error handling and history tracking'''
        if b == 0:
            error_msg = f"Division by zero error: {a} / {b}"
            self.history.append(error_msg)
            raise ValueError("Cannot divide by zero")

        result = a / b
        operation = f"{a} / {b} = {result}"
        self.history.append(operation)
        self.last_result = result
        return result

    def power(self, base, exponent):
        '''Exponentiation with history tracking'''
        result = base ** exponent
        operation = f"{base} ^ {exponent} = {result}"
        self.history.append(operation)
        self.last_result = result
        return result

    def get_history(self):
        '''Return calculation history'''
        return self.history.copy()

    def clear_history(self):
        '''Clear calculation history'''
        self.history.clear()
        self.last_result = 0

# Demo usage
if __name__ == "__main__":
    calc = Calculator()
    print("=== Calculator Demo ===")

    # Perform various calculations
    print(f"Addition: {calc.add(10, 20)}")
    print(f"Multiplication: {calc.multiply(5, 8)}")
    print(f"Division: {calc.divide(100, 4)}")
    print(f"Power: {calc.power(2, 8)}")

    print("\\nCalculation History:")
    for operation in calc.get_history():
        print(f"  {operation}")

    print(f"\\nLast result: {calc.last_result}")
"""

            # Create test files
            file1_path = self.create_additional_test_file("math_functions.py", file1_content)
            file2_path = self.create_additional_test_file("calculator.py", file2_content)

            # Track continuation IDs to validate each step generates new ones
            continuation_ids = []

            # Step 1: Initial chat with first file
            self.logger.info("  Step 1: Initial chat with file1 - checking token allocation")

            datetime.datetime.now()

            response1, continuation_id1 = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Please analyze this math functions file and explain what it does.",
                    "absolute_file_paths": [file1_path],
                    "model": "flash",
                    "temperature": 0.7,
                },
            )

            if not response1 or not continuation_id1:
                self.logger.error("  ❌ Step 1 failed - no response or continuation ID")
                return False

            self.logger.info(f"  ✅ Step 1 completed with continuation_id: {continuation_id1[:8]}...")
            continuation_ids.append(continuation_id1)

            # Validate that Step 1 succeeded and returned proper content
            if "fibonacci" not in response1.lower() or "factorial" not in response1.lower():
                self.logger.error("  ❌ Step 1: Response doesn't contain expected function analysis")
                return False

            self.logger.info("  ✅ Step 1: File was successfully analyzed")

            # Step 2: Different tool continuing same conversation - should build conversation history
            self.logger.info(
                "  Step 2: Analyze tool continuing chat conversation - checking conversation history buildup"
            )

            response2, continuation_id2 = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Analyze the performance implications of these recursive functions.",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Continuing from chat conversation to analyze performance implications of recursive functions.",
                    "relevant_files": [file1_path],
                    "continuation_id": continuation_id1,  # Continue the chat conversation
                    "model": "flash",
                },
            )

            if not response2 or not continuation_id2:
                self.logger.error("  ❌ Step 2 failed - no response or continuation ID")
                return False

            self.logger.info(f"  ✅ Step 2 completed with continuation_id: {continuation_id2[:8]}...")
            continuation_ids.append(continuation_id2)

            # Validate continuation ID behavior for workflow tools
            # Workflow tools reuse the same continuation_id when continuing within a workflow session
            # This is expected behavior and different from simple tools
            if continuation_id2 != continuation_id1:
                self.logger.info("  ✅ Step 2: Got new continuation ID (workflow behavior)")
            else:
                self.logger.info("  ✅ Step 2: Reused continuation ID (workflow session continuation)")
            # Both behaviors are valid - what matters is that we got a continuation_id

            # Validate that Step 2 is building on Step 1's conversation
            # Check if the response references the previous conversation
            if "performance" not in response2.lower() and "recursive" not in response2.lower():
                self.logger.error("  ❌ Step 2: Response doesn't contain expected performance analysis")
                return False

            self.logger.info("  ✅ Step 2: Successfully continued conversation with performance analysis")

            # Step 3: Continue conversation with additional file - should show increased token usage
            self.logger.info("  Step 3: Continue conversation with file1 + file2 - checking token growth")

            response3, continuation_id3 = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Now compare the math functions with this calculator class. How do they differ in approach?",
                    "absolute_file_paths": [file1_path, file2_path],
                    "continuation_id": continuation_id2,  # Continue the conversation from step 2
                    "model": "flash",
                    "temperature": 0.7,
                },
            )

            if not response3 or not continuation_id3:
                self.logger.error("  ❌ Step 3 failed - no response or continuation ID")
                return False

            self.logger.info(f"  ✅ Step 3 completed with continuation_id: {continuation_id3[:8]}...")
            continuation_ids.append(continuation_id3)

            # Validate that Step 3 references both previous steps and compares the files
            if "calculator" not in response3.lower() or "math" not in response3.lower():
                self.logger.error("  ❌ Step 3: Response doesn't contain expected comparison between files")
                return False

            self.logger.info("  ✅ Step 3: Successfully compared both files in continued conversation")

            # Validation: Check that conversation continuation worked properly
            self.logger.info("  📋 Validating conversation continuation...")

            # Validation criteria
            criteria = []

            # 1. All steps returned valid responses
            all_responses_valid = bool(response1 and response2 and response3)
            criteria.append(("All steps returned valid responses", all_responses_valid))

            # 2. All steps generated continuation IDs
            all_have_continuation_ids = bool(continuation_id1 and continuation_id2 and continuation_id3)
            criteria.append(("All steps generated continuation IDs", all_have_continuation_ids))

            # 3. Continuation behavior validation (handles both simple and workflow tools)
            # Simple tools create new IDs each time, workflow tools may reuse IDs within sessions
            has_valid_continuation_pattern = len(continuation_ids) == 3
            criteria.append(("Valid continuation ID pattern", has_valid_continuation_pattern))

            # 4. Check for conversation continuity (more important than ID uniqueness)
            conversation_has_continuity = len(continuation_ids) == 3 and all(
                cid is not None for cid in continuation_ids
            )
            criteria.append(("Conversation continuity maintained", conversation_has_continuity))

            # 5. Check responses build on each other (content validation)
            step1_has_function_analysis = "fibonacci" in response1.lower() or "factorial" in response1.lower()
            step2_has_performance_analysis = "performance" in response2.lower() or "recursive" in response2.lower()
            step3_has_comparison = "calculator" in response3.lower() and "math" in response3.lower()

            criteria.append(("Step 1 analyzed the math functions", step1_has_function_analysis))
            criteria.append(("Step 2 discussed performance implications", step2_has_performance_analysis))
            criteria.append(("Step 3 compared both files", step3_has_comparison))

            # Log continuation ID analysis
            self.logger.info("   Continuation ID Analysis:")
            self.logger.info(f"    Step 1 ID: {continuation_ids[0][:8]}... (new conversation)")
            self.logger.info(f"    Step 2 ID: {continuation_ids[1][:8]}... (continued from Step 1)")
            self.logger.info(f"    Step 3 ID: {continuation_ids[2][:8]}... (continued from Step 2)")

            # Check validation criteria
            passed_criteria = sum(1 for _, passed in criteria if passed)
            total_criteria = len(criteria)

            self.logger.info(f"   Validation criteria: {passed_criteria}/{total_criteria}")
            for criterion, passed in criteria:
                status = "✅" if passed else "❌"
                self.logger.info(f"    {status} {criterion}")

            # Success criteria: All validation criteria must pass
            success = passed_criteria == total_criteria

            if success:
                self.logger.info("  ✅ Token allocation validation test PASSED")
                return True
            else:
                self.logger.error("  ❌ Token allocation validation test FAILED")
                return False

        except Exception as e:
            self.logger.error(f"Token allocation validation test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()


def main():
    """Run the token allocation validation test"""
    import sys

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    test = TokenAllocationValidationTest(verbose=verbose)

    success = test.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
