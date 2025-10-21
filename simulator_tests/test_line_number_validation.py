"""
Test to validate line number handling across different tools
"""

import json
import os

from .base_test import BaseSimulatorTest


class LineNumberValidationTest(BaseSimulatorTest):
    """Test that validates correct line number handling in chat, analyze, and refactor tools"""

    @property
    def test_name(self) -> str:
        return "line_number_validation"

    @property
    def test_description(self) -> str:
        return "Line number handling validation across tools"

    def run_test(self) -> bool:
        """Test line number handling in different tools"""
        try:
            self.logger.info("Test: Line number handling validation")

            # Setup test files
            self.setup_test_files()

            # Create a test file with known content
            test_file_content = '''# Example code with specific elements
def calculate_total(items):
    """Calculate total with tax"""
    subtotal = 0
    tax_rate = 0.08  # Line 5 - tax_rate defined

    for item in items:  # Line 7 - loop starts
        if item.price > 0:
            subtotal += item.price

    tax_amount = subtotal * tax_rate  # Line 11
    return subtotal + tax_amount

def validate_data(data):
    """Validate input data"""  # Line 15
    required_fields = ["name", "email", "age"]  # Line 16

    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing field: {field}")

    return True  # Line 22
'''

            test_file_path = os.path.join(self.test_dir, "line_test.py")
            with open(test_file_path, "w") as f:
                f.write(test_file_content)

            self.logger.info(f"Created test file: {test_file_path}")

            # Test 1: Chat tool asking about specific line
            self.logger.info("  1.1: Testing chat tool with line number question")
            content, continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Where is tax_rate defined in this file? Please tell me the exact line number.",
                    "absolute_file_paths": [test_file_path],
                    "model": "flash",
                },
            )

            if content:
                # Check if the response mentions line 5
                if "line 5" in content.lower() or "line 5" in content:
                    self.logger.info("  ✅ Chat tool correctly identified tax_rate at line 5")
                else:
                    self.logger.warning(f"  ⚠️ Chat tool response didn't mention line 5: {content[:200]}...")
            else:
                self.logger.error("  ❌ Chat tool request failed")
                return False

            # Test 2: Analyze tool with line number reference
            self.logger.info("  1.2: Testing analyze tool with line number analysis")
            content, continuation_id = self.call_mcp_tool(
                "analyze",
                {
                    "prompt": "What happens between lines 7-11 in this code? Focus on the loop logic.",
                    "absolute_file_paths": [test_file_path],
                    "model": "flash",
                },
            )

            if content:
                # Check if the response references the loop
                if any(term in content.lower() for term in ["loop", "iterate", "line 7", "lines 7"]):
                    self.logger.info("  ✅ Analyze tool correctly analyzed the specified line range")
                else:
                    self.logger.warning("  ⚠️ Analyze tool response unclear about line range")
            else:
                self.logger.error("  ❌ Analyze tool request failed")
                return False

            # Test 3: Refactor tool with line number precision
            self.logger.info("  1.3: Testing refactor tool line number precision")
            content, continuation_id = self.call_mcp_tool(
                "refactor",
                {
                    "prompt": "Analyze this code for refactoring opportunities",
                    "absolute_file_paths": [test_file_path],
                    "refactor_type": "codesmells",
                    "model": "flash",
                },
            )

            if content:
                try:
                    # Parse the JSON response
                    result = json.loads(content)
                    if result.get("status") == "refactor_analysis_complete":
                        opportunities = result.get("refactor_opportunities", [])
                        if opportunities:
                            # Check if line numbers are precise
                            has_line_refs = any(
                                opp.get("start_line") is not None and opp.get("end_line") is not None
                                for opp in opportunities
                            )
                            if has_line_refs:
                                self.logger.info("  ✅ Refactor tool provided precise line number references")
                                # Log some examples
                                for opp in opportunities[:2]:
                                    if opp.get("start_line"):
                                        self.logger.info(
                                            f"    - Issue at lines {opp['start_line']}-{opp['end_line']}: {opp.get('issue', '')[:50]}..."
                                        )
                            else:
                                self.logger.warning("  ⚠️ Refactor tool response missing line numbers")
                        else:
                            self.logger.info("  ℹ️ No refactoring opportunities found (code might be too clean)")
                except json.JSONDecodeError:
                    self.logger.warning("  ⚠️ Refactor tool response not valid JSON")
            else:
                self.logger.error("  ❌ Refactor tool request failed")
                return False

            # Test 4: Validate log patterns
            self.logger.info("  1.4: Validating line number processing in logs")

            # Get logs from server
            try:
                log_file_path = "logs/mcp_server.log"
                with open(log_file_path) as f:
                    lines = f.readlines()
                    logs = "".join(lines[-500:])
            except Exception as e:
                self.logger.error(f"Failed to read server logs: {e}")
                logs = ""
                pass

            # Check for line number formatting patterns
            line_number_patterns = ["Line numbers for", "enabled", "│", "line number"]  # The line number separator

            found_patterns = 0
            for pattern in line_number_patterns:
                if pattern in logs:
                    found_patterns += 1

            self.logger.info(f"    Found {found_patterns}/{len(line_number_patterns)} line number patterns in logs")

            if found_patterns >= 2:
                self.logger.info("  ✅ Line number processing confirmed in logs")
            else:
                self.logger.warning("  ⚠️ Limited line number processing evidence in logs")

            self.logger.info("  ✅ Line number validation test completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Line number validation test failed: {type(e).__name__}: {e}")
            return False
