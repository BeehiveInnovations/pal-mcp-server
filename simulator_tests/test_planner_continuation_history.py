#!/usr/bin/env python3
"""
Planner Continuation History Test

Tests the planner tool's continuation history building across multiple completed planning sessions:
- Multiple completed planning sessions in sequence
- History context loading for new planning sessions
- Proper context building with multiple completed plans
- Context accumulation and retrieval
"""

import json
from typing import Optional

from .base_test import BaseSimulatorTest


class PlannerContinuationHistoryTest(BaseSimulatorTest):
    """Test planner tool's continuation history building across multiple completed sessions"""

    @property
    def test_name(self) -> str:
        return "planner_continuation_history"

    @property
    def test_description(self) -> str:
        return "Planner tool continuation history building across multiple completed planning sessions"

    def run_test(self) -> bool:
        """Test planner continuation history building across multiple completed sessions"""
        try:
            self.logger.info("Test: Planner continuation history validation")

            # Test 1: Complete first planning session (microservices migration)
            if not self._test_first_planning_session():
                return False

            # Test 2: Complete second planning session with context from first
            if not self._test_second_planning_session():
                return False

            # Test 3: Complete third planning session with context from both previous
            if not self._test_third_planning_session():
                return False

            # Test 4: Validate context accumulation across all sessions
            if not self._test_context_accumulation():
                return False

            self.logger.info("  ✅ All planner continuation history tests passed")
            return True

        except Exception as e:
            self.logger.error(f"Planner continuation history test failed: {e}")
            return False

    def _test_first_planning_session(self) -> bool:
        """Complete first planning session - microservices migration"""
        try:
            self.logger.info("  2.1: First planning session - Microservices Migration")

            # Step 1: Start migration planning
            self.logger.info("    2.1.1: Start migration planning")
            response1, continuation_id = self.call_mcp_tool(
                "planner",
                {
                    "step": "I need to plan a microservices migration for our monolithic e-commerce platform. Let me analyze the current monolith structure.",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start first planning session")
                return False

            # Step 2: Domain identification
            self.logger.info("    2.1.2: Domain identification")
            response2, _ = self.call_mcp_tool(
                "planner",
                {
                    "step": "I've identified key domains: User Management, Product Catalog, Order Processing, Payment, and Inventory. Each will become a separate microservice.",
                    "step_number": 2,
                    "total_steps": 3,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed step 2 of first planning session")
                return False

            # Step 3: Complete migration plan
            self.logger.info("    2.1.3: Complete migration plan")
            response3, _ = self.call_mcp_tool(
                "planner",
                {
                    "step": "Migration strategy: Phase 1 - Extract User Management service, Phase 2 - Product Catalog and Inventory services, Phase 3 - Order Processing and Payment services. Use API Gateway for service coordination.",
                    "step_number": 3,
                    "total_steps": 3,
                    "next_step_required": False,  # Complete the session
                    "continuation_id": continuation_id,
                },
            )

            if not response3:
                self.logger.error("Failed to complete first planning session")
                return False

            # Validate completion
            response3_data = self._parse_planner_response(response3)
            if not response3_data.get("planning_complete"):
                self.logger.error("First planning session not marked as complete")
                return False

            if not response3_data.get("plan_summary"):
                self.logger.error("First planning session missing plan summary")
                return False

            self.logger.info("    ✅ First planning session completed successfully")

            # Store for next test
            self.first_continuation_id = continuation_id
            return True

        except Exception as e:
            self.logger.error(f"First planning session test failed: {e}")
            return False

    def _test_second_planning_session(self) -> bool:
        """Complete second planning session with context from first"""
        try:
            self.logger.info("  2.2: Second planning session - Database Strategy")

            # Step 1: Start database planning with previous context
            self.logger.info("    2.2.1: Start database strategy with microservices context")
            response1, new_continuation_id = self.call_mcp_tool(
                "planner",
                {
                    "step": "Now I need to plan the database strategy for the microservices architecture. I'll design how each service will manage its data.",
                    "step_number": 1,
                    "total_steps": 2,
                    "next_step_required": True,
                    "continuation_id": self.first_continuation_id,  # Use first session's continuation_id
                },
            )

            if not response1 or not new_continuation_id:
                self.logger.error("Failed to start second planning session")
                return False

            # Validate context loading
            response1_data = self._parse_planner_response(response1)
            if "previous_plan_context" not in response1_data:
                self.logger.error("Second session should load context from first completed session")
                return False

            # Check context contains migration content
            context = response1_data["previous_plan_context"].lower()
            if "migration" not in context and "microservices" not in context:
                self.logger.error("Context should contain migration/microservices content from first session")
                return False

            self.logger.info("    ✅ Second session loaded context from first completed session")

            # Step 2: Complete database plan
            self.logger.info("    2.2.2: Complete database strategy")
            response2, _ = self.call_mcp_tool(
                "planner",
                {
                    "step": "Database strategy: Each microservice gets its own database (database-per-service pattern). Use event sourcing for cross-service communication and eventual consistency. Implement CQRS for read/write separation.",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Complete the session
                    "continuation_id": new_continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to complete second planning session")
                return False

            # Validate completion
            response2_data = self._parse_planner_response(response2)
            if not response2_data.get("planning_complete"):
                self.logger.error("Second planning session not marked as complete")
                return False

            self.logger.info("    ✅ Second planning session completed successfully")

            # Store for next test
            self.second_continuation_id = new_continuation_id
            return True

        except Exception as e:
            self.logger.error(f"Second planning session test failed: {e}")
            return False

    def _test_third_planning_session(self) -> bool:
        """Complete third planning session with context from both previous"""
        try:
            self.logger.info("  2.3: Third planning session - Deployment Strategy")

            # Step 1: Start deployment planning with accumulated context
            self.logger.info("    2.3.1: Start deployment strategy with accumulated context")
            response1, new_continuation_id = self.call_mcp_tool(
                "planner",
                {
                    "step": "Now I need to plan the deployment strategy that supports both the microservices architecture and the database strategy. I'll design the infrastructure and deployment pipeline.",
                    "step_number": 1,
                    "total_steps": 2,
                    "next_step_required": True,
                    "continuation_id": self.second_continuation_id,  # Use second session's continuation_id
                },
            )

            if not response1 or not new_continuation_id:
                self.logger.error("Failed to start third planning session")
                return False

            # Validate context loading
            response1_data = self._parse_planner_response(response1)
            if "previous_plan_context" not in response1_data:
                self.logger.error("Third session should load context from previous completed sessions")
                return False

            # Check context contains content from most recent completed session
            context = response1_data["previous_plan_context"].lower()
            expected_terms = ["database", "event sourcing", "cqrs"]
            found_terms = [term for term in expected_terms if term in context]

            if len(found_terms) == 0:
                self.logger.error(
                    f"Context should contain database strategy content from second session. Context: {context[:200]}..."
                )
                return False

            self.logger.info("    ✅ Third session loaded context from most recent completed session")

            # Step 2: Complete deployment plan
            self.logger.info("    2.3.2: Complete deployment strategy")
            response2, _ = self.call_mcp_tool(
                "planner",
                {
                    "step": "Deployment strategy: Use Kubernetes for container orchestration with Helm charts. Implement CI/CD pipeline with GitOps. Use service mesh (Istio) for traffic management, monitoring, and security. Deploy databases in separate namespaces with backup automation.",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Complete the session
                    "continuation_id": new_continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to complete third planning session")
                return False

            # Validate completion
            response2_data = self._parse_planner_response(response2)
            if not response2_data.get("planning_complete"):
                self.logger.error("Third planning session not marked as complete")
                return False

            self.logger.info("    ✅ Third planning session completed successfully")

            # Store for final test
            self.third_continuation_id = new_continuation_id
            return True

        except Exception as e:
            self.logger.error(f"Third planning session test failed: {e}")
            return False

    def _test_context_accumulation(self) -> bool:
        """Test that context properly accumulates across multiple completed sessions"""
        try:
            self.logger.info("  2.4: Testing context accumulation across all sessions")

            # Start a new planning session that should load context from the most recent completed session
            self.logger.info("    2.4.1: Start monitoring planning with full context history")
            response1, _ = self.call_mcp_tool(
                "planner",
                {
                    "step": "Finally, I need to plan the monitoring and observability strategy that works with the microservices, database, and deployment architecture.",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "continuation_id": self.third_continuation_id,  # Use third session's continuation_id
                },
            )

            if not response1:
                self.logger.error("Failed to start monitoring planning session")
                return False

            # Validate context loading
            response1_data = self._parse_planner_response(response1)
            if "previous_plan_context" not in response1_data:
                self.logger.error("Final session should load context from previous completed sessions")
                return False

            # Validate context contains most recent completed session content
            context = response1_data["previous_plan_context"].lower()

            # Should contain deployment strategy content (most recent)
            deployment_terms = ["kubernetes", "deployment", "istio", "gitops"]
            found_deployment_terms = [term for term in deployment_terms if term in context]

            if len(found_deployment_terms) == 0:
                self.logger.error(f"Context should contain deployment strategy content. Context: {context[:300]}...")
                return False

            self.logger.info("    ✅ Context accumulation working correctly")

            # Validate this creates a complete planning session
            if not response1_data.get("planning_complete"):
                self.logger.error("Final planning session should be marked as complete")
                return False

            self.logger.info("    ✅ Context accumulation test completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Context accumulation test failed: {e}")
            return False

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool via Claude CLI (docker exec) - override for planner-specific response handling"""
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
