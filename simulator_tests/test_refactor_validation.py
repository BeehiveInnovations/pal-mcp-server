#!/usr/bin/env python3
"""
Refactor Tool Validation Test

Tests the refactor tool with a simple code smell example to validate:
- Proper execution with flash model
- Correct line number references in response
- Log validation for tool execution
"""

import json

from .base_test import BaseSimulatorTest


class RefactorValidationTest(BaseSimulatorTest):
    """Test refactor tool with codesmells detection"""

    @property
    def test_name(self) -> str:
        return "refactor_validation"

    @property
    def test_description(self) -> str:
        return "Refactor tool validation with codesmells"

    def run_test(self) -> bool:
        """Test refactor tool with a simple code smell example"""
        try:
            self.logger.info("Test: Refactor tool validation")

            # Setup test files directory first
            self.setup_test_files()

            # Create a simple Python file with obvious code smells
            code_with_smells = """# Code with obvious smells for testing
def process_data(data):
    # Code smell: Magic number
    if len(data) > 42:
        result = []
        # Code smell: Nested loops with poor variable names
        for i in range(len(data)):
            for j in range(len(data[i])):
                x = data[i][j]
                # Code smell: Duplicate code
                if x > 0:
                    result.append(x * 2)
                elif x < 0:
                    result.append(x * 2)
        return result
    else:
        # Code smell: Return inconsistent type
        return None

# Code smell: God function doing too many things
def handle_everything(user_input, config, database):
    # Validation
    if not user_input:
        print("Error: No input")  # Code smell: print instead of logging
        return

    # Processing
    processed = user_input.strip().lower()

    # Database operation
    connection = database.connect()
    data = connection.query("SELECT * FROM users")  # Code smell: SQL in code

    # Business logic mixed with data access
    valid_users = []
    for row in data:
        if row[2] == processed:  # Code smell: Magic index
            valid_users.append(row)

    return valid_users
"""

            # Create test file
            test_file = self.create_additional_test_file("smelly_code.py", code_with_smells)
            self.logger.info(f"  ✅ Created test file with code smells: {test_file}")

            # Call refactor tool with codesmells type
            self.logger.info("  📝 Calling refactor tool with codesmells type...")
            response, _ = self.call_mcp_tool(
                "refactor",
                {
                    "files": [test_file],
                    "prompt": "Find and suggest fixes for code smells in this file",
                    "refactor_type": "codesmells",
                    "model": "flash",
                    "thinking_mode": "low",  # Keep it fast for testing
                },
            )

            if not response:
                self.logger.error("Failed to get refactor response")
                return False

            self.logger.info("  ✅ Got refactor response")

            # Parse response to check for line references
            try:
                response_data = json.loads(response)

                # Debug: log the response structure
                self.logger.debug(f"Response keys: {list(response_data.keys())}")

                # Extract the actual content if it's wrapped
                if "content" in response_data:
                    # The actual refactoring data is in the content field
                    content = response_data["content"]
                    # Remove markdown code block markers if present
                    if content.startswith("```json"):
                        content = content[7:]  # Remove ```json
                    if content.endswith("```"):
                        content = content[:-3]  # Remove ```
                    content = content.strip()

                    # Find the end of the JSON object - handle truncated responses
                    # Count braces to find where the JSON ends
                    brace_count = 0
                    json_end = -1
                    in_string = False
                    escape_next = False

                    for i, char in enumerate(content):
                        if escape_next:
                            escape_next = False
                            continue
                        if char == "\\":
                            escape_next = True
                            continue
                        if char == '"' and not escape_next:
                            in_string = not in_string
                        if not in_string:
                            if char == "{":
                                brace_count += 1
                            elif char == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    json_end = i + 1
                                    break

                    if json_end > 0:
                        content = content[:json_end]

                    # Parse the inner JSON
                    inner_data = json.loads(content)
                    self.logger.debug(f"Inner data keys: {list(inner_data.keys())}")
                else:
                    inner_data = response_data

                # Check that we got refactoring suggestions (might be called refactor_opportunities)
                refactorings_key = None
                for key in ["refactorings", "refactor_opportunities"]:
                    if key in inner_data:
                        refactorings_key = key
                        break

                if not refactorings_key:
                    self.logger.error("No refactorings found in response")
                    self.logger.error(f"Response structure: {json.dumps(inner_data, indent=2)[:500]}...")
                    return False

                refactorings = inner_data[refactorings_key]
                if not isinstance(refactorings, list) or len(refactorings) == 0:
                    self.logger.error("Empty refactorings list")
                    return False

                # Validate that we have line references for code smells
                # Flash model typically detects these issues:
                # - Lines 4-18: process_data function (magic number, nested loops, duplicate code)
                # - Lines 11-14: duplicate code blocks
                # - Lines 21-40: handle_everything god function

                self.logger.debug(f"Refactorings found: {len(refactorings)}")
                for i, ref in enumerate(refactorings[:3]):  # Log first 3
                    self.logger.debug(
                        f"Refactoring {i}: start_line={ref.get('start_line')}, end_line={ref.get('end_line')}, type={ref.get('type')}"
                    )

                found_references = []
                for refactoring in refactorings:
                    # Check for line numbers in various fields
                    start_line = refactoring.get("start_line")
                    end_line = refactoring.get("end_line")
                    location = refactoring.get("location", "")

                    # Add found line numbers
                    if start_line:
                        found_references.append(f"line {start_line}")
                    if end_line and end_line != start_line:
                        found_references.append(f"line {end_line}")

                    # Also extract from location string
                    import re

                    line_matches = re.findall(r"line[s]?\s+(\d+)", location.lower())
                    found_references.extend([f"line {num}" for num in line_matches])

                self.logger.info(f"  📍 Found line references: {found_references}")

                # Check that flash found the expected refactoring areas
                found_ranges = []
                for refactoring in refactorings:
                    start = refactoring.get("start_line")
                    end = refactoring.get("end_line")
                    if start and end:
                        found_ranges.append((start, end))

                self.logger.info(f"  📍 Found refactoring ranges: {found_ranges}")

                # Verify we found issues in the main problem areas
                # Check if we have issues detected in process_data function area (lines 2-18)
                process_data_issues = [r for r in found_ranges if r[0] >= 2 and r[1] <= 18]
                # Check if we have issues detected in handle_everything function area (lines 21-40)
                god_function_issues = [r for r in found_ranges if r[0] >= 21 and r[1] <= 40]

                self.logger.info(f"  📍 Issues in process_data area (lines 2-18): {len(process_data_issues)}")
                self.logger.info(f"  📍 Issues in handle_everything area (lines 21-40): {len(god_function_issues)}")

                if len(process_data_issues) >= 1 and len(god_function_issues) >= 1:
                    self.logger.info("  ✅ Flash correctly identified code smells in both major areas")
                    self.logger.info(f"  ✅ Found {len(refactorings)} total refactoring opportunities")

                    # Verify we have reasonable number of total issues
                    if len(refactorings) >= 3:
                        self.logger.info("  ✅ Refactoring analysis validation passed")
                    else:
                        self.logger.warning(f"  ⚠️ Only {len(refactorings)} refactorings found (expected >= 3)")
                else:
                    self.logger.error("  ❌ Flash didn't find enough issues in expected areas")
                    self.logger.error(f"     - process_data area: found {len(process_data_issues)}, expected >= 1")
                    self.logger.error(f"     - handle_everything area: found {len(god_function_issues)}, expected >= 1")
                    return False

            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse refactor response as JSON: {e}")
                return False

            # Validate logs
            self.logger.info("  📋 Validating execution logs...")

            # Get server logs using inherited method
            logs = self.get_recent_server_logs(500)

            # Look for refactor tool execution patterns
            refactor_patterns = [
                "[REFACTOR]",
                "refactor tool",
                "codesmells",
                "Token budget",
                "Code files embedded successfully",
            ]

            patterns_found = 0
            for pattern in refactor_patterns:
                if pattern in logs:
                    patterns_found += 1
                    self.logger.debug(f"  ✅ Found log pattern: {pattern}")

            if patterns_found >= 3:
                self.logger.info(f"  ✅ Log validation passed ({patterns_found}/{len(refactor_patterns)} patterns)")
            else:
                self.logger.warning(f"  ⚠️ Only found {patterns_found}/{len(refactor_patterns)} log patterns")

            self.logger.info("  ✅ Refactor tool validation completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Refactor validation test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()
