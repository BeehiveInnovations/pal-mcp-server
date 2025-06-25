#!/usr/bin/env python3
"""
ThinkDeep Tool Validation Test

Tests the thinkdeep tool's capabilities using the new workflow architecture.
This validates that the workflow-based deep thinking implementation provides
step-by-step thinking with expert analysis integration.
"""

import json
from typing import Optional

from .conversation_base_test import ConversationBaseTest


class ThinkDeepWorkflowValidationTest(ConversationBaseTest):
    """Test thinkdeep tool with new workflow architecture"""

    @property
    def test_name(self) -> str:
        return "thinkdeep_validation"

    @property
    def test_description(self) -> str:
        return "ThinkDeep workflow tool validation with new workflow architecture"

    def run_test(self) -> bool:
        """Test thinkdeep tool capabilities"""
        # Set up the test environment
        self.setUp()

        try:
            self.logger.info("Test: ThinkDeepWorkflow tool validation (new architecture)")

            # Create test files for thinking context
            self._create_thinking_context()

            # Test 1: Single thinking session with multiple steps
            if not self._test_single_thinking_session():
                return False

            # Test 2: Thinking with backtracking
            if not self._test_thinking_with_backtracking():
                return False

            # Test 3: Complete thinking with expert analysis
            if not self._test_complete_thinking_with_analysis():
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

            self.logger.info("  ✅ All thinkdeep validation tests passed")
            return True

        except Exception as e:
            self.logger.error(f"ThinkDeep validation test failed: {e}")
            return False

    def _create_thinking_context(self):
        """Create test files for deep thinking context"""
        # Create architecture document
        architecture_doc = """# Microservices Architecture Design

## Current System
- Monolithic application with 500k LOC
- Single PostgreSQL database
- Peak load: 10k requests/minute
- Team size: 25 developers
- Deployment: Manual, 2-week cycles

## Proposed Migration to Microservices

### Benefits
- Independent deployments
- Technology diversity
- Team autonomy
- Scalability improvements

### Challenges
- Data consistency
- Network latency
- Operational complexity
- Transaction management

### Key Considerations
- Service boundaries
- Data migration strategy
- Communication patterns
- Monitoring and observability
"""

        # Create requirements document
        requirements_doc = """# Migration Requirements

## Business Goals
- Reduce deployment cycle from 2 weeks to daily
- Support 50k requests/minute by Q4
- Enable A/B testing capabilities
- Improve system resilience

## Technical Constraints
- Zero downtime migration
- Maintain data consistency
- Budget: $200k for infrastructure
- Timeline: 6 months
- Existing team skills: Java, Spring Boot

## Success Metrics
- Deployment frequency: 10x improvement
- System availability: 99.9%
- Response time: <200ms p95
- Developer productivity: 30% improvement
"""

        # Create performance analysis
        performance_analysis = """# Current Performance Analysis

## Database Bottlenecks
- Connection pool exhaustion during peak hours
- Complex joins affecting query performance
- Lock contention on user_sessions table
- Read replica lag causing data inconsistency

## Application Issues
- Memory leaks in background processing
- Thread pool starvation
- Cache invalidation storms
- Session clustering problems

## Infrastructure Limits
- Single server deployment
- Manual scaling processes
- Limited monitoring capabilities
- No circuit breaker patterns
"""

        # Create test files
        self.architecture_file = self.create_additional_test_file("architecture_design.md", architecture_doc)
        self.requirements_file = self.create_additional_test_file("migration_requirements.md", requirements_doc)
        self.performance_file = self.create_additional_test_file("performance_analysis.md", performance_analysis)

        self.logger.info("  ✅ Created thinking context files:")
        self.logger.info(f"      - {self.architecture_file}")
        self.logger.info(f"      - {self.requirements_file}")
        self.logger.info(f"      - {self.performance_file}")

    def _test_single_thinking_session(self) -> bool:
        """Test a complete thinking session with multiple steps"""
        try:
            self.logger.info("  1.1: Testing single thinking session")

            # Step 1: Start thinking analysis
            self.logger.info("    1.1.1: Step 1 - Initial thinking analysis")
            response1, continuation_id = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "I need to think deeply about the microservices migration strategy. Let me analyze the trade-offs, risks, and implementation approach systematically.",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial analysis shows significant architectural complexity but potential for major scalability and development velocity improvements. Need to carefully consider migration strategy and service boundaries.",
                    "files_checked": [self.architecture_file, self.requirements_file],
                    "relevant_files": [self.architecture_file, self.requirements_file],
                    "relevant_context": ["microservices_migration", "service_boundaries", "data_consistency"],
                    "confidence": "low",
                    "problem_context": "Enterprise application migration from monolith to microservices",
                    "focus_areas": ["architecture", "scalability", "risk_assessment"],
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to get initial thinking response")
                return False

            # Parse and validate JSON response
            response1_data = self._parse_thinkdeep_response(response1)
            if not response1_data:
                return False

            # Validate step 1 response structure - expect pause_for_thinkdeep for next_step_required=True
            if not self._validate_step_response(response1_data, 1, 4, True, "pause_for_thinkdeep"):
                return False

            self.logger.info(f"    ✅ Step 1 successful, continuation_id: {continuation_id}")

            # Step 2: Deep analysis
            self.logger.info("    1.1.2: Step 2 - Deep analysis of alternatives")
            response2, _ = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "Analyzing different migration approaches: strangler fig pattern vs big bang vs gradual extraction. Each has different risk profiles and timelines.",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Strangler fig pattern emerges as best approach: lower risk, incremental value delivery, team learning curve management. Key insight: start with read-only services to minimize data consistency issues.",
                    "files_checked": [self.architecture_file, self.requirements_file, self.performance_file],
                    "relevant_files": [self.architecture_file, self.performance_file],
                    "relevant_context": ["strangler_fig_pattern", "service_extraction", "risk_mitigation"],
                    "issues_found": [
                        {"severity": "high", "description": "Data consistency challenges during migration"},
                        {"severity": "medium", "description": "Team skill gap in distributed systems"},
                    ],
                    "confidence": "medium",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue thinking to step 2")
                return False

            response2_data = self._parse_thinkdeep_response(response2)
            if not self._validate_step_response(response2_data, 2, 4, True, "pause_for_thinkdeep"):
                return False

            # Check thinking status tracking
            thinking_status = response2_data.get("thinking_status", {})
            if thinking_status.get("files_checked", 0) < 3:
                self.logger.error("Files checked count not properly tracked")
                return False

            if thinking_status.get("thinking_confidence") != "medium":
                self.logger.error("Confidence level not properly tracked")
                return False

            self.logger.info("    ✅ Step 2 successful with proper tracking")

            # Store continuation_id for next test
            self.thinking_continuation_id = continuation_id
            return True

        except Exception as e:
            self.logger.error(f"Single thinking session test failed: {e}")
            return False

    def _test_thinking_with_backtracking(self) -> bool:
        """Test thinking with backtracking to revise analysis"""
        try:
            self.logger.info("  1.2: Testing thinking with backtracking")

            # Start a new thinking session for testing backtracking
            self.logger.info("    1.2.1: Start thinking for backtracking test")
            response1, continuation_id = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "Thinking about optimal database architecture for the new microservices",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial thought: each service should have its own database for independence",
                    "files_checked": [self.architecture_file],
                    "relevant_files": [self.architecture_file],
                    "relevant_context": ["database_per_service", "data_independence"],
                    "confidence": "low",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start backtracking test thinking")
                return False

            # Step 2: Initial direction
            self.logger.info("    1.2.2: Step 2 - Initial analysis direction")
            response2, _ = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "Exploring database-per-service pattern implementation",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Database-per-service creates significant complexity for transactions and reporting",
                    "files_checked": [self.architecture_file, self.performance_file],
                    "relevant_files": [self.performance_file],
                    "relevant_context": ["database_per_service", "transaction_management"],
                    "issues_found": [
                        {"severity": "high", "description": "Cross-service transactions become complex"},
                        {"severity": "medium", "description": "Reporting queries span multiple databases"},
                    ],
                    "confidence": "low",
                    "continuation_id": continuation_id,
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            # Step 3: Backtrack and revise approach
            self.logger.info("    1.2.3: Step 3 - Backtrack and revise thinking")
            response3, _ = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "Backtracking - maybe shared database with service-specific schemas is better initially. Then gradually extract databases as services mature.",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Hybrid approach: shared database with bounded contexts, then gradual extraction. This reduces initial complexity while preserving migration path to full service independence.",
                    "files_checked": [self.architecture_file, self.requirements_file],
                    "relevant_files": [self.architecture_file, self.requirements_file],
                    "relevant_context": ["shared_database", "bounded_contexts", "gradual_extraction"],
                    "confidence": "medium",
                    "backtrack_from_step": 2,  # Backtrack from step 2
                    "continuation_id": continuation_id,
                },
            )

            if not response3:
                self.logger.error("Failed to backtrack")
                return False

            response3_data = self._parse_thinkdeep_response(response3)
            if not self._validate_step_response(response3_data, 3, 4, True, "pause_for_thinkdeep"):
                return False

            self.logger.info("    ✅ Backtracking working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Backtracking test failed: {e}")
            return False

    def _test_complete_thinking_with_analysis(self) -> bool:
        """Test complete thinking ending with expert analysis"""
        try:
            self.logger.info("  1.3: Testing complete thinking with expert analysis")

            # Use the continuation from first test
            continuation_id = getattr(self, "thinking_continuation_id", None)
            if not continuation_id:
                # Start fresh if no continuation available
                self.logger.info("    1.3.0: Starting fresh thinking session")
                response0, continuation_id = self.call_mcp_tool(
                    "thinkdeep",
                    {
                        "step": "Thinking about the complete microservices migration strategy",
                        "step_number": 1,
                        "total_steps": 2,
                        "next_step_required": True,
                        "findings": "Comprehensive analysis of migration approaches and risks",
                        "files_checked": [self.architecture_file, self.requirements_file],
                        "relevant_files": [self.architecture_file, self.requirements_file],
                        "relevant_context": ["migration_strategy", "risk_assessment"],
                    },
                )
                if not response0 or not continuation_id:
                    self.logger.error("Failed to start fresh thinking session")
                    return False

            # Final step - trigger expert analysis
            self.logger.info("    1.3.1: Final step - complete thinking analysis")
            response_final, _ = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "Thinking analysis complete. I've thoroughly considered the migration strategy, risks, and implementation approach.",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step - triggers expert analysis
                    "findings": "Comprehensive migration strategy: strangler fig pattern with shared database initially, gradual service extraction based on business value and technical feasibility. Key success factors: team training, monitoring infrastructure, and incremental rollout.",
                    "files_checked": [self.architecture_file, self.requirements_file, self.performance_file],
                    "relevant_files": [self.architecture_file, self.requirements_file, self.performance_file],
                    "relevant_context": ["strangler_fig", "migration_strategy", "risk_mitigation", "team_readiness"],
                    "issues_found": [
                        {"severity": "medium", "description": "Team needs distributed systems training"},
                        {"severity": "low", "description": "Monitoring tools need upgrade"},
                    ],
                    "confidence": "high",
                    "continuation_id": continuation_id,
                    "model": "flash",  # Use flash for expert analysis
                },
            )

            if not response_final:
                self.logger.error("Failed to complete thinking")
                return False

            response_final_data = self._parse_thinkdeep_response(response_final)
            if not response_final_data:
                return False

            # Validate final response structure - accept both expert analysis and special statuses
            valid_final_statuses = ["calling_expert_analysis", "files_required_to_continue"]
            if response_final_data.get("status") not in valid_final_statuses:
                self.logger.error(
                    f"Expected status in {valid_final_statuses}, got '{response_final_data.get('status')}'"
                )
                return False

            if not response_final_data.get("thinking_complete"):
                self.logger.error("Expected thinking_complete=true for final step")
                return False

            # Check for expert analysis or special status content
            if response_final_data.get("status") == "calling_expert_analysis":
                if "expert_analysis" not in response_final_data:
                    self.logger.error("Missing expert_analysis in final response")
                    return False
                expert_analysis = response_final_data.get("expert_analysis", {})
            else:
                # For special statuses like files_required_to_continue, analysis may be in content
                expert_analysis = response_final_data.get("content", "{}")
                if isinstance(expert_analysis, str):
                    try:
                        expert_analysis = json.loads(expert_analysis)
                    except (json.JSONDecodeError, TypeError):
                        expert_analysis = {"analysis": expert_analysis}

            # Check for expected analysis content (checking common patterns)
            analysis_text = json.dumps(expert_analysis, ensure_ascii=False).lower()

            # Look for thinking analysis validation
            thinking_indicators = ["migration", "strategy", "microservices", "risk", "approach", "implementation"]
            found_indicators = sum(1 for indicator in thinking_indicators if indicator in analysis_text)

            if found_indicators >= 3:
                self.logger.info("    ✅ Expert analysis validated the thinking correctly")
            else:
                self.logger.warning(
                    f"    ⚠️ Expert analysis may not have fully validated the thinking (found {found_indicators}/6 indicators)"
                )

            # Check complete thinking summary
            if "complete_thinking" not in response_final_data:
                self.logger.error("Missing complete_thinking in final response")
                return False

            complete_thinking = response_final_data["complete_thinking"]
            if not complete_thinking.get("relevant_context"):
                self.logger.error("Missing relevant context in complete thinking")
                return False

            if "migration_strategy" not in complete_thinking["relevant_context"]:
                self.logger.error("Expected context not found in thinking summary")
                return False

            self.logger.info("    ✅ Complete thinking with expert analysis successful")
            return True

        except Exception as e:
            self.logger.error(f"Complete thinking test failed: {e}")
            return False

    def _test_certain_confidence(self) -> bool:
        """Test certain confidence behavior - should skip expert analysis"""
        try:
            self.logger.info("  1.4: Testing certain confidence behavior")

            # Test certain confidence - should skip expert analysis
            self.logger.info("    1.4.1: Certain confidence thinking")
            response_certain, _ = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "I have thoroughly analyzed all aspects of the migration strategy with complete certainty.",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,  # Final step
                    "findings": "Definitive conclusion: strangler fig pattern with phased database extraction is the optimal approach. Risk mitigation through team training and robust monitoring. Timeline: 6 months with monthly service extractions.",
                    "files_checked": [self.architecture_file, self.requirements_file, self.performance_file],
                    "relevant_files": [self.architecture_file, self.requirements_file],
                    "relevant_context": ["migration_complete_strategy", "implementation_plan"],
                    "confidence": "certain",  # This should skip expert analysis
                    "model": "flash",
                },
            )

            if not response_certain:
                self.logger.error("Failed to test certain confidence")
                return False

            response_certain_data = self._parse_thinkdeep_response(response_certain)
            if not response_certain_data:
                return False

            # Validate certain confidence response - should skip expert analysis
            if response_certain_data.get("status") != "deep_thinking_complete_ready_for_implementation":
                self.logger.error(
                    f"Expected status 'deep_thinking_complete_ready_for_implementation', got '{response_certain_data.get('status')}'"
                )
                return False

            if not response_certain_data.get("skip_expert_analysis"):
                self.logger.error("Expected skip_expert_analysis=true for certain confidence")
                return False

            expert_analysis = response_certain_data.get("expert_analysis", {})
            if expert_analysis.get("status") != "skipped_due_to_certain_thinking_confidence":
                self.logger.error("Expert analysis should be skipped for certain confidence")
                return False

            self.logger.info("    ✅ Certain confidence behavior working correctly")
            return True

        except Exception as e:
            self.logger.error(f"Certain confidence test failed: {e}")
            return False

    def call_mcp_tool(self, tool_name: str, params: dict) -> tuple[Optional[str], Optional[str]]:
        """Call an MCP tool in-process - override for thinkdeep-specific response handling"""
        # Use in-process implementation to maintain conversation memory
        response_text, _ = self.call_mcp_tool_direct(tool_name, params)

        if not response_text:
            return None, None

        # Extract continuation_id from thinkdeep response specifically
        continuation_id = self._extract_thinkdeep_continuation_id(response_text)

        return response_text, continuation_id

    def _extract_thinkdeep_continuation_id(self, response_text: str) -> Optional[str]:
        """Extract continuation_id from thinkdeep response"""
        try:
            # Parse the response
            response_data = json.loads(response_text)
            return response_data.get("continuation_id")

        except json.JSONDecodeError as e:
            self.logger.debug(f"Failed to parse response for thinkdeep continuation_id: {e}")
            return None

    def _parse_thinkdeep_response(self, response_text: str) -> dict:
        """Parse thinkdeep tool JSON response"""
        try:
            # Parse the response - it should be direct JSON
            return json.loads(response_text)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse thinkdeep response as JSON: {e}")
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
        """Validate a thinkdeep thinking step response structure"""
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

            # Check thinking_status exists
            if "thinking_status" not in response_data:
                self.logger.error("Missing thinking_status in response")
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

            # Create additional test files for context testing
            strategy_doc = """# Implementation Strategy

## Phase 1: Foundation (Month 1-2)
- Set up monitoring and logging infrastructure
- Establish CI/CD pipelines for microservices
- Team training on distributed systems concepts

## Phase 2: Initial Services (Month 3-4)
- Extract read-only services (user profiles, product catalog)
- Implement API gateway
- Set up service discovery

## Phase 3: Core Services (Month 5-6)
- Extract transaction services
- Implement saga patterns for distributed transactions
- Performance optimization and monitoring
"""

            tech_stack_doc = """# Technology Stack Decisions

## Service Framework
- Spring Boot 2.7 (team familiarity)
- Docker containers
- Kubernetes orchestration

## Communication
- REST APIs for synchronous communication
- Apache Kafka for asynchronous messaging
- gRPC for high-performance internal communication

## Data Layer
- PostgreSQL (existing expertise)
- Redis for caching
- Elasticsearch for search and analytics

## Monitoring
- Prometheus + Grafana
- Distributed tracing with Jaeger
- Centralized logging with ELK stack
"""

            # Create test files
            strategy_file = self.create_additional_test_file("implementation_strategy.md", strategy_doc)
            tech_stack_file = self.create_additional_test_file("tech_stack.md", tech_stack_doc)

            # Test 1: New conversation, intermediate step - should only reference files
            self.logger.info("    1.5.1: New conversation intermediate step (should reference only)")
            response1, continuation_id = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "Starting deep thinking about implementation timeline and technology choices",
                    "step_number": 1,
                    "total_steps": 3,
                    "next_step_required": True,  # Intermediate step
                    "findings": "Initial analysis of implementation strategy and technology stack decisions",
                    "files_checked": [strategy_file, tech_stack_file],
                    "relevant_files": [strategy_file],  # This should be referenced, not embedded
                    "relevant_context": ["implementation_timeline", "technology_selection"],
                    "confidence": "low",
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start context-aware file embedding test")
                return False

            response1_data = self._parse_thinkdeep_response(response1)
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
                "thinkdeep",
                {
                    "step": "Thinking analysis complete - comprehensive evaluation of implementation approach",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Complete analysis: phased implementation with proven technology stack minimizes risk while maximizing team effectiveness. Timeline is realistic with proper training and infrastructure setup.",
                    "files_checked": [strategy_file, tech_stack_file],
                    "relevant_files": [strategy_file, tech_stack_file],  # Should be fully embedded
                    "relevant_context": ["implementation_plan", "technology_decisions", "risk_management"],
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to complete to final step")
                return False

            response2_data = self._parse_thinkdeep_response(response2)
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

            # Verify expert analysis was called for final step
            if response2_data.get("status") != "calling_expert_analysis":
                self.logger.error("Final step should trigger expert analysis")
                return False

            if "expert_analysis" not in response2_data:
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

            # Create a complex scenario with multiple thinking documents
            risk_analysis = """# Risk Analysis

## Technical Risks
- Service mesh complexity
- Data consistency challenges
- Performance degradation during migration
- Operational overhead increase

## Business Risks
- Extended development timelines
- Potential system instability
- Team productivity impact
- Customer experience disruption

## Mitigation Strategies
- Gradual rollout with feature flags
- Comprehensive monitoring and alerting
- Rollback procedures for each phase
- Customer communication plan
"""

            success_metrics = """# Success Metrics and KPIs

## Development Velocity
- Deployment frequency: Target 10x improvement
- Lead time for changes: <2 hours
- Mean time to recovery: <30 minutes
- Change failure rate: <5%

## System Performance
- Response time: <200ms p95
- System availability: 99.9%
- Throughput: 50k requests/minute
- Resource utilization: 70% optimal

## Business Impact
- Developer satisfaction: >8/10
- Time to market: 50% reduction
- Operational costs: 20% reduction
- System reliability: 99.9% uptime
"""

            # Create test files
            risk_file = self.create_additional_test_file("risk_analysis.md", risk_analysis)
            metrics_file = self.create_additional_test_file("success_metrics.md", success_metrics)

            # Step 1: Start thinking analysis (new conversation)
            self.logger.info("    1.6.1: Step 1 - Start thinking analysis")
            response1, continuation_id = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "Beginning comprehensive analysis of migration risks and success criteria",
                    "step_number": 1,
                    "total_steps": 4,
                    "next_step_required": True,
                    "findings": "Initial assessment of risk factors and success metrics for microservices migration",
                    "files_checked": [risk_file],
                    "relevant_files": [risk_file],
                    "relevant_context": ["risk_assessment", "migration_planning"],
                    "confidence": "low",
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("Failed to start multi-step file context test")
                return False

            response1_data = self._parse_thinkdeep_response(response1)

            # Validate step 1 - should use reference_only
            file_context1 = response1_data.get("file_context", {})
            if file_context1.get("type") != "reference_only":
                self.logger.error("Step 1 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 1: reference_only file context")

            # Step 2: Expand thinking analysis
            self.logger.info("    1.6.2: Step 2 - Expand thinking analysis")
            response2, _ = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "Deepening analysis by correlating risks with success metrics",
                    "step_number": 2,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                    "findings": "Key insight: technical risks directly impact business metrics. Need balanced approach prioritizing high-impact, low-risk improvements first.",
                    "files_checked": [risk_file, metrics_file],
                    "relevant_files": [risk_file, metrics_file],
                    "relevant_context": ["risk_metric_correlation", "priority_matrix"],
                    "confidence": "medium",
                    "model": "flash",
                },
            )

            if not response2:
                self.logger.error("Failed to continue to step 2")
                return False

            response2_data = self._parse_thinkdeep_response(response2)

            # Validate step 2 - should still use reference_only
            file_context2 = response2_data.get("file_context", {})
            if file_context2.get("type") != "reference_only":
                self.logger.error("Step 2 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 2: reference_only file context with multiple files")

            # Step 3: Deep analysis
            self.logger.info("    1.6.3: Step 3 - Deep strategic analysis")
            response3, _ = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "Synthesizing risk mitigation strategies with measurable success criteria",
                    "step_number": 3,
                    "total_steps": 4,
                    "next_step_required": True,
                    "continuation_id": continuation_id,
                    "findings": "Strategic framework emerging: phase-gate approach with clear go/no-go criteria at each milestone. Emphasis on early wins to build confidence and momentum.",
                    "files_checked": [risk_file, metrics_file, self.requirements_file],
                    "relevant_files": [risk_file, metrics_file, self.requirements_file],
                    "relevant_context": ["phase_gate_approach", "milestone_criteria", "early_wins"],
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response3:
                self.logger.error("Failed to continue to step 3")
                return False

            response3_data = self._parse_thinkdeep_response(response3)

            # Validate step 3 - should still use reference_only
            file_context3 = response3_data.get("file_context", {})
            if file_context3.get("type") != "reference_only":
                self.logger.error("Step 3 should use reference_only file context")
                return False

            self.logger.info("    ✅ Step 3: reference_only file context")

            # Step 4: Final analysis with expert consultation
            self.logger.info("    1.6.4: Step 4 - Final step with expert analysis")
            response4, _ = self.call_mcp_tool(
                "thinkdeep",
                {
                    "step": "Thinking analysis complete - comprehensive strategic framework developed",
                    "step_number": 4,
                    "total_steps": 4,
                    "next_step_required": False,  # Final step - should embed files
                    "continuation_id": continuation_id,
                    "findings": "Complete strategic framework: risk-balanced migration with measurable success criteria, phase-gate governance, and clear rollback procedures. Framework aligns technical execution with business objectives.",
                    "files_checked": [risk_file, metrics_file, self.requirements_file, self.architecture_file],
                    "relevant_files": [risk_file, metrics_file, self.requirements_file, self.architecture_file],
                    "relevant_context": ["strategic_framework", "governance_model", "success_measurement"],
                    "confidence": "high",
                    "model": "flash",
                },
            )

            if not response4:
                self.logger.error("Failed to complete to final step")
                return False

            response4_data = self._parse_thinkdeep_response(response4)

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

            # Check that expert analysis has file context
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
