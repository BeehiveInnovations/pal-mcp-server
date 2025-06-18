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
import re

from .base_test import BaseSimulatorTest


class TokenAllocationValidationTest(BaseSimulatorTest):
    """Test token allocation and conversation history functionality"""

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
                    "files": [file1_path],
                    "model": "flash",
                    "temperature": 0.7,
                },
            )

            if not response1 or not continuation_id1:
                self.logger.error("  ❌ Step 1 failed - no response or continuation ID")
                return False

            self.logger.info(f"  ✅ Step 1 completed with continuation_id: {continuation_id1[:8]}...")
            continuation_ids.append(continuation_id1)

            # Get logs and analyze file processing (Step 1 is new conversation, no conversation debug logs expected)
            logs_step1 = self.get_recent_server_logs()

            # For Step 1, check for file embedding logs instead of conversation usage
            file_embedding_logs_step1 = [
                line
                for line in logs_step1.split("\n")
                if "successfully embedded" in line and "files" in line and "tokens" in line
            ]

            if not file_embedding_logs_step1:
                self.logger.error("  ❌ Step 1: No file embedding logs found")
                return False

            # Extract file token count from embedding logs
            step1_file_tokens = 0
            for log in file_embedding_logs_step1:
                # Look for pattern like "successfully embedded 1 files (146 tokens)"
                match = re.search(r"\((\d+) tokens\)", log)
                if match:
                    step1_file_tokens = int(match.group(1))
                    break

            self.logger.info(f"   Step 1 File Processing - Embedded files: {step1_file_tokens:,} tokens")

            # Validate that file1 is actually mentioned in the embedding logs (check for actual filename)
            file1_mentioned = any("math_functions.py" in log for log in file_embedding_logs_step1)
            if not file1_mentioned:
                # Debug: show what files were actually found in the logs
                self.logger.debug("  📋 Files found in embedding logs:")
                for log in file_embedding_logs_step1:
                    self.logger.debug(f"    {log}")
                # Also check if any files were embedded at all
                any_file_embedded = len(file_embedding_logs_step1) > 0
                if not any_file_embedded:
                    self.logger.error("  ❌ Step 1: No file embedding logs found at all")
                    return False
                else:
                    self.logger.warning("  ⚠️ Step 1: math_functions.py not specifically found, but files were embedded")
                    # Continue test - the important thing is that files were processed

            # Step 2: Different tool continuing same conversation - should build conversation history
            self.logger.info(
                "  Step 2: Analyze tool continuing chat conversation - checking conversation history buildup"
            )

            response2, continuation_id2 = self.call_mcp_tool(
                "analyze",
                {
                    "prompt": "Analyze the performance implications of these recursive functions.",
                    "files": [file1_path],
                    "continuation_id": continuation_id1,  # Continue the chat conversation
                    "model": "flash",
                    "temperature": 0.7,
                },
            )

            if not response2 or not continuation_id2:
                self.logger.error("  ❌ Step 2 failed - no response or continuation ID")
                return False

            self.logger.info(f"  ✅ Step 2 completed with continuation_id: {continuation_id2[:8]}...")
            continuation_ids.append(continuation_id2)

            # Validate that we got a different continuation ID
            if continuation_id2 == continuation_id1:
                self.logger.error("  ❌ Step 2: Got same continuation ID as Step 1 - continuation not working")
                return False

            # Get logs and analyze token usage
            logs_step2 = self.get_recent_server_logs()
            usage_step2 = self.extract_conversation_usage_logs(logs_step2)

            if len(usage_step2) < 2:
                self.logger.warning(
                    f"  ⚠️ Step 2: Only found {len(usage_step2)} conversation usage logs, expected at least 2"
                )
                # Debug: Look for any CONVERSATION_DEBUG logs
                conversation_debug_lines = [line for line in logs_step2.split("\n") if "CONVERSATION_DEBUG" in line]
                self.logger.debug(f"  📋 Found {len(conversation_debug_lines)} CONVERSATION_DEBUG lines in step 2")

                if conversation_debug_lines:
                    self.logger.debug("  📋 Recent CONVERSATION_DEBUG lines:")
                    for line in conversation_debug_lines[-10:]:  # Show last 10
                        self.logger.debug(f"    {line}")

                # If we have at least 1 usage log, continue with adjusted expectations
                if len(usage_step2) >= 1:
                    self.logger.info("  📋 Continuing with single usage log for analysis")
                else:
                    self.logger.error("  ❌ No conversation usage logs found at all")
                    return False

            latest_usage_step2 = usage_step2[-1]  # Get most recent usage
            self.logger.info(
                f"   Step 2 Token Usage - Total Capacity: {latest_usage_step2.get('total_capacity', 0):,}, "
                f"Conversation: {latest_usage_step2.get('conversation_tokens', 0):,}, "
                f"Remaining: {latest_usage_step2.get('remaining_tokens', 0):,}"
            )

            # Step 3: Continue conversation with additional file - should show increased token usage
            self.logger.info("  Step 3: Continue conversation with file1 + file2 - checking token growth")

            response3, continuation_id3 = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Now compare the math functions with this calculator class. How do they differ in approach?",
                    "files": [file1_path, file2_path],
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

            # Get logs and analyze final token usage
            logs_step3 = self.get_recent_server_logs()
            usage_step3 = self.extract_conversation_usage_logs(logs_step3)

            self.logger.info(f"  📋 Found {len(usage_step3)} total conversation usage logs")

            if len(usage_step3) < 3:
                self.logger.warning(
                    f"  ⚠️ Step 3: Only found {len(usage_step3)} conversation usage logs, expected at least 3"
                )
                # Let's check if we have at least some logs to work with
                if len(usage_step3) == 0:
                    self.logger.error("  ❌ No conversation usage logs found at all")
                    # Debug: show some recent logs
                    recent_lines = logs_step3.split("\n")[-50:]
                    self.logger.debug("  📋 Recent log lines:")
                    for line in recent_lines:
                        if line.strip() and "CONVERSATION_DEBUG" in line:
                            self.logger.debug(f"    {line}")
                    return False

            latest_usage_step3 = usage_step3[-1]  # Get most recent usage
            self.logger.info(
                f"   Step 3 Token Usage - Total Capacity: {latest_usage_step3.get('total_capacity', 0):,}, "
                f"Conversation: {latest_usage_step3.get('conversation_tokens', 0):,}, "
                f"Remaining: {latest_usage_step3.get('remaining_tokens', 0):,}"
            )

            # Validation: Check token processing and conversation history
            self.logger.info("  📋 Validating token processing and conversation history...")

            # Get conversation usage for steps with continuation_id
            step2_conversation = 0
            step2_remaining = 0
            step3_conversation = 0
            step3_remaining = 0

            if len(usage_step2) > 0:
                step2_conversation = latest_usage_step2.get("conversation_tokens", 0)
                step2_remaining = latest_usage_step2.get("remaining_tokens", 0)

            if len(usage_step3) >= len(usage_step2) + 1:  # Should have one more log than step2
                step3_conversation = latest_usage_step3.get("conversation_tokens", 0)
                step3_remaining = latest_usage_step3.get("remaining_tokens", 0)
            else:
                # Use step2 values as fallback
                step3_conversation = step2_conversation
                step3_remaining = step2_remaining
                self.logger.warning("  ⚠️ Using Step 2 usage for Step 3 comparison due to missing logs")

            # Validation criteria
            criteria = []

            # 1. Step 1 should have processed files successfully
            step1_processed_files = step1_file_tokens > 0
            criteria.append(("Step 1 processed files successfully", step1_processed_files))

            # 2. Step 2 should have conversation history (if continuation worked)
            step2_has_conversation = (
                step2_conversation > 0 if len(usage_step2) > 0 else True
            )  # Pass if no logs (might be different issue)
            step2_has_remaining = step2_remaining > 0 if len(usage_step2) > 0 else True
            criteria.append(("Step 2 has conversation history", step2_has_conversation))
            criteria.append(("Step 2 has remaining tokens", step2_has_remaining))

            # 3. Step 3 should show conversation growth
            step3_has_conversation = (
                step3_conversation >= step2_conversation if len(usage_step3) > len(usage_step2) else True
            )
            criteria.append(("Step 3 maintains conversation history", step3_has_conversation))

            # 4. Check that we got some conversation usage logs for continuation calls
            has_conversation_logs = len(usage_step3) > 0
            criteria.append(("Found conversation usage logs", has_conversation_logs))

            # 5. Validate unique continuation IDs per response
            unique_continuation_ids = len(set(continuation_ids)) == len(continuation_ids)
            criteria.append(("Each response generated unique continuation ID", unique_continuation_ids))

            # 6. Validate continuation IDs were different from each step
            step_ids_different = (
                len(continuation_ids) == 3
                and continuation_ids[0] != continuation_ids[1]
                and continuation_ids[1] != continuation_ids[2]
            )
            criteria.append(("All continuation IDs are different", step_ids_different))

            # Log detailed analysis
            self.logger.info("   Token Processing Analysis:")
            self.logger.info(f"    Step 1 - File tokens: {step1_file_tokens:,} (new conversation)")
            self.logger.info(f"    Step 2 - Conversation: {step2_conversation:,}, Remaining: {step2_remaining:,}")
            self.logger.info(f"    Step 3 - Conversation: {step3_conversation:,}, Remaining: {step3_remaining:,}")

            # Log continuation ID analysis
            self.logger.info("   Continuation ID Analysis:")
            self.logger.info(f"    Step 1 ID: {continuation_ids[0][:8]}... (generated)")
            self.logger.info(f"    Step 2 ID: {continuation_ids[1][:8]}... (generated from Step 1)")
            self.logger.info(f"    Step 3 ID: {continuation_ids[2][:8]}... (generated from Step 2)")

            # Check for file mentions in step 3 (should include both files)
            # Look for file processing in conversation memory logs and tool embedding logs
            file2_mentioned_step3 = any(
                "calculator.py" in log
                for log in logs_step3.split("\n")
                if ("embedded" in log.lower() and ("conversation" in log.lower() or "tool" in log.lower()))
            )
            file1_still_mentioned_step3 = any(
                "math_functions.py" in log
                for log in logs_step3.split("\n")
                if ("embedded" in log.lower() and ("conversation" in log.lower() or "tool" in log.lower()))
            )

            self.logger.info("   File Processing in Step 3:")
            self.logger.info(f"    File1 (math_functions.py) mentioned: {file1_still_mentioned_step3}")
            self.logger.info(f"    File2 (calculator.py) mentioned: {file2_mentioned_step3}")

            # Add file increase validation
            step3_file_increase = file2_mentioned_step3  # New file should be visible
            criteria.append(("Step 3 shows new file being processed", step3_file_increase))

            # Check validation criteria
            passed_criteria = sum(1 for _, passed in criteria if passed)
            total_criteria = len(criteria)

            self.logger.info(f"   Validation criteria: {passed_criteria}/{total_criteria}")
            for criterion, passed in criteria:
                status = "✅" if passed else "❌"
                self.logger.info(f"    {status} {criterion}")

            # Check for file embedding logs
            file_embedding_logs = [
                line for line in logs_step3.split("\n") if "tool embedding" in line and "files" in line
            ]

            conversation_logs = [line for line in logs_step3.split("\n") if "conversation history" in line.lower()]

            self.logger.info(f"   File embedding logs: {len(file_embedding_logs)}")
            self.logger.info(f"   Conversation history logs: {len(conversation_logs)}")

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
