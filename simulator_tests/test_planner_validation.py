#!/usr/bin/env python3
"""
Planner Tool Validation Test

Tests the planner tool's sequential planning capabilities including:
- Step-by-step planning with proper JSON responses
- Continuation logic across planning sessions
- Branching and revision capabilities
- Previous plan context loading
- Plan completion and summary storage
"""

import json
from typing import Optional

from .base_test import BaseSimulatorTest


class PlannerValidationTest(BaseSimulatorTest):
    """Test planner tool's sequential planning and continuation features"""

    @property
    def test_name(self) -> str:
        return "planner_validation"

    @property
    def test_description(self) -> str:
        return "Planner tool sequential planning and continuation validation"

    def run_test(self) -> bool:
        """Test planner tool sequential planning capabilities"""
        try:
            self.logger.info("Test: Planner tool validation")

            # Test 1: Single planning session with multiple steps
            if not self._test_single_planning_session():
                return False

            # Test 2: Plan completion and continuation to new planning session
            if not self._test_plan_continuation():
                return False

            # Test 3: Branching and revision capabilities
            if not self._test_branching_and_revision():
                return False

            self.logger.info("  ✅ All planner validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"Planner validation test failed: {e}")
            return False

    def _test_single_planning_session(self) -> bool:
        """Test a complete planning session with multiple steps"""
        try:
            self.logger.info("  1.1: Testing single planning session")

            # Step 1: Start planning
            self.logger.info("    1.1.1: Step 1 - Initial planning step")
            response1, continuation_id = self.call_mcp_tool(
                "planner",
                {
                    "step": "I need to plan a microservices migration for our monolithic e-commerce platform. Let me start by understanding the current architecture and identifying the key business domains.",
                    "step_number": 1,
                    "total_steps": 5,
                    "next_step_required": True,
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to get initial planning response")
                return False

            # Parse and validate JSON response
            response1_data = self._parse_planner_response(response1)
            if not response1_data:
                return False

            # Validate step 1 response structure
            if not self._validate_step_response(response1_data, 1, 5, True, "planning_success"):
                return False

            self.logger.info(f"    ✅ Step 1 successful, continuation_id: {continuation_id}")

            # Step 2: Continue planning
            self.logger.info("    1.1.2: Step 2 - Domain identification")
            response2, _ = self.call_mcp_tool(
                "planner",
                {
                    "step": "Based on my analysis, I can identify the main business domains: User Management, Product Catalog, Order Processing, Payment, and Inventory. Let me plan how to extract these into separate services.",
                    "step_number": 2,
                    "total_steps": 5,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue planning to step 2")
                return False

            response2_data = self._parse_planner_response(response2)
            if not self._validate_step_response(response2_data, 2, 5, True, "planning_success"):
                return False

            self.logger.info("    ✅ Step 2 successful")

            # Step 3: Final step
            self.logger.info("    1.1.3: Step 3 - Final planning step")
            response3, _ = self.call_mcp_tool(
                "planner",
                {
                    "step": "Now I'll create a phased migration strategy: Phase 1 - Extract User Management, Phase 2 - Product Catalog and Inventory, Phase 3 - Order Processing and Payment services. This completes the initial migration plan.",
                    "step_number": 3,
                    "total_steps": 3,  # Adjusted total
                    "next_step_required": False,  # Final step
                    "continuation_id": continuation_id,
                },
            )

            if not response3:
                self.logger.error("Failed to complete planning session")
                return False

            response3_data = self._parse_planner_response(response3)
            if not self._validate_final_step_response(response3_data, 3, 3):
                return False

            self.logger.info("    ✅ Planning session completed successfully")

            # Store continuation_id for next test
            self.migration_continuation_id = continuation_id
            return True

        except Exception as e:
            self.logger.error(f"Single planning session test failed: {e}")
            return False

    def _test_plan_continuation(self) -> bool:
        """Test continuing from a previous completed plan"""
        try:
            self.logger.info("  1.2: Testing plan continuation with previous context")

            # Start a new planning session using the continuation_id from previous completed plan
            self.logger.info("    1.2.1: New planning session with previous plan context")
            response1, new_continuation_id = self.call_mcp_tool(
                "planner",
                {
                    "step": "Now that I have the microservices migration plan, let me plan the database strategy. I need to decide how to handle data consistency across the new services.",
                    "step_number": 1,  # New planning session starts at step 1
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": self.migration_continuation_id,  # Use previous plan's continuation_id
                },
            )

            if not response1 or not new_continuation_id:
                self.logger.error("Failed to start new planning session with context")
                return False

            response1_data = self._parse_planner_response(response1)
            if not response1_data:
                return False

            # Should have previous plan context
            if "previous_plan_context" not in response1_data:
                self.logger.error("Expected previous_plan_context in new planning session")
                return False

            # Check for key terms from the previous plan
            context = response1_data["previous_plan_context"].lower()
            if "migration" not in context and "plan" not in context:
                self.logger.error("Previous plan context doesn't contain expected content")
                return False

            self.logger.info("    ✅ New planning session loaded previous plan context")

            # Continue the new planning session (step 2+ should NOT load context)
            self.logger.info("    1.2.2: Continue new planning session (no context loading)")
            response2, _ = self.call_mcp_tool(
                "planner",
                {
                    "step": "I'll implement a database-per-service pattern with eventual consistency using event sourcing for cross-service communication.",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": new_continuation_id,  # Same continuation, step 2
                },
            )

            if not response2:
                self.logger.error("Failed to continue new planning session")
                return False

            response2_data = self._parse_planner_response(response2)
            if not response2_data:
                return False

            # Step 2+ should NOT have previous_plan_context (only step 1 with continuation_id gets context)
            if "previous_plan_context" in response2_data:
                self.logger.error("Step 2 should NOT have previous_plan_context")
                return False

            self.logger.info("    ✅ Step 2 correctly has no previous context (as expected)")
            return True

        except Exception as e:
            self.logger.error(f"Plan continuation test failed: {e}")
            return False

    def _test_branching_and_revision(self) -> bool:
        """Test branching and revision capabilities"""
        try:
            self.logger.info("  1.3: Testing branching and revision capabilities")

            # Start a new planning session for testing branching
            self.logger.info("    1.3.1: Start planning session for branching test")
            response1, continuation_id = self.call_mcp_tool(
                "planner",
                {
                    "step": "Let me plan the deployment strategy for the microservices. I'll consider different deployment options.",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start branching test planning session")
                return False

            # Test branching
            self.logger.info("    1.3.2: Create a branch from step 1")
            response2, _ = self.call_mcp_tool(
                "planner",
                {
                    "step": "Branch A: I'll explore Kubernetes deployment with service mesh (Istio) for advanced traffic management and observability.",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "is_branch_point": True,
                    "branch_from_step": 1,
                    "branch_id": "kubernetes-istio",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to create branch")
                return False

            response2_data = self._parse_planner_response(response2)
            if not response2_data:
                return False

            # Validate branching metadata
            metadata = response2_data.get("metadata", {})
            if not metadata.get("is_branch_point"):
                self.logger.error("Branch point not properly recorded in metadata")
                return False

            if metadata.get("branch_id") != "kubernetes-istio":
                self.logger.error("Branch ID not properly recorded")
                return False

            if "kubernetes-istio" not in metadata.get("branches", []):
                self.logger.error("Branch not recorded in branches list")
                return False

            self.logger.info("    ✅ Branching working correctly")

            # Test revision
            self.logger.info("    1.3.3: Revise step 2")
            response3, _ = self.call_mcp_tool(
                "planner",
                {
                    "step": "Revision: Actually, let me revise the Kubernetes approach. I'll use a simpler deployment initially, then migrate to Kubernetes later.",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "is_step_revision": True,
                    "revises_step_number": 2,
                    "continuation_id": continuation_id,
                },
            )

            if not response3:
                self.logger.error("Failed to create revision")
                return False

            response3_data = self._parse_planner_response(response3)
            if not response3_data:
                return False

            # Validate revision metadata
            metadata = response3_data.get("metadata", {})
            if not metadata.get("is_step_revision"):
                self.logger.error("Step revision not properly recorded in metadata")
                return False

            if metadata.get("revises_step_number") != 2:
                self.logger.error("Revised step number not properly recorded")
                return False

            self.logger.info("    ✅ Revision working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Branching and revision test failed: {e}")
            return False

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool via standalone server - override for planner-specific response handling"""
        # Use parent implementation to get the raw response
        response_text, _ = super().call_mcp_tool(tool_name, params)

        if not response_text:
            return None, None

        # Extract continuation_id from planner response specifically
        continuation_id = self._extract_planner_continuation_id(response_text)

        return response_text, continuation_id

    def _extract_planner_continuation_id(self, response_text: str) -> Optional[str]:
        """Extract continuation_id from planner response"""
        try:
            # Parse the response - it's now direct JSON, not wrapped
            response_data = json.loads(response_text)
            return response_data.get("continuation_id")

        except json.JSONDecodeError as e:
            self.logger.debug(f"Failed to parse response for planner continuation_id: {e}")
            return None

    def _parse_planner_response(self, response_text: str) -> dict:
        """Parse planner tool JSON response"""
        try:
            # Parse the response - it's now direct JSON, not wrapped
            return json.loads(response_text)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse planner response as JSON: {e}")
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
        """Validate a planning step response structure"""
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

            # Check that step_content exists
            if not response_data.get("step_content"):
                self.logger.error("Missing step_content in response")
                return False

            # Check metadata exists
            if "metadata" not in response_data:
                self.logger.error("Missing metadata in response")
                return False

            # Check next_steps guidance
            if not response_data.get("next_steps"):
                self.logger.error("Missing next_steps guidance in response")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating step response: {e}")
            return False

    def _validate_final_step_response(self, response_data: dict, expected_step: int, expected_total: int) -> bool:
        """Validate a final planning step response"""
        try:
            # Basic step validation
            if not self._validate_step_response(
                response_data, expected_step, expected_total, False, "planning_success"
            ):
                return False

            # Check planning_complete flag
            if not response_data.get("planning_complete"):
                self.logger.error("Expected planning_complete=true for final step")
                return False

            # Check plan_summary exists
            if not response_data.get("plan_summary"):
                self.logger.error("Missing plan_summary in final step")
                return False

            # Check plan_summary contains expected content
            plan_summary = response_data.get("plan_summary", "")
            if "COMPLETE PLAN:" not in plan_summary:
                self.logger.error("plan_summary doesn't contain 'COMPLETE PLAN:' marker")
                return False

            # Check next_steps mentions completion
            next_steps = response_data.get("next_steps", "")
            if "complete" not in next_steps.lower():
                self.logger.error("next_steps doesn't indicate planning completion")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating final step response: {e}")
            return False
