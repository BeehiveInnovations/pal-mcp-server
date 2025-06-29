"""
TestGen Workflow tool - Step-by-step test generation with expert validation

This tool provides a structured workflow for comprehensive test generation.
It guides the CLI agent through systematic investigation steps with forced pauses between each step
to ensure thorough code examination, test planning, and pattern identification before proceeding.
The tool supports backtracking, finding updates, and expert analysis integration for
comprehensive test suite generation.

Key features:
- Step-by-step test generation workflow with progress tracking
- Context-aware file embedding (references during investigation, full content for analysis)
- Automatic test pattern detection and framework identification
- Expert analysis integration with external models for additional test suggestions
- Support for edge case identification and comprehensive coverage
- Confidence-based workflow optimization
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field, model_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import TESTGEN_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions for test generation workflow
TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS = {
    "step": (
        "What to analyze or look for in this step. In step 1, describe what you want to test and begin forming an "
        "analytical approach after thinking carefully about what needs to be examined. Consider code structure, "
        "business logic, critical paths, edge cases, and potential failure modes. Map out the codebase structure, "
        "understand the functionality, and identify areas requiring test coverage. In later steps, continue exploring "
        "with precision and adapt your understanding as you uncover more insights about testable behaviors."
    ),
    "step_number": (
        "The index of the current step in the test generation sequence, beginning at 1. Each step should build upon or "
        "revise the previous one."
    ),
    "total_steps": (
        "Your current estimate for how many steps will be needed to complete the test generation analysis. "
        "Adjust as new findings emerge."
    ),
    "next_step_required": (
        "Set to true if you plan to continue the investigation with another step. False means you believe the "
        "test generation analysis is complete and ready for expert validation."
    ),
    "findings": (
        "Summarize everything discovered in this step about the code being tested. Include analysis of functionality, "
        "critical paths, edge cases, boundary conditions, error handling, async behavior, state management, and "
        "integration points. Be specific and avoid vague language—document what you now know about the code and "
        "what test scenarios are needed. IMPORTANT: Document both the happy paths and potential failure modes. "
        "Identify existing test patterns if examples were provided. In later steps, confirm or update past findings "
        "with additional evidence."
    ),
    "files_checked": (
        "List all files (as absolute paths, do not clip or shrink file names) examined during the test generation "
        "investigation so far. Include even files ruled out or found to be unrelated, as this tracks your "
        "exploration path."
    ),
    "relevant_files": (
        "Subset of files_checked (as full absolute paths) that contain code directly needing tests or are essential "
        "for understanding test requirements. Only list those that are directly tied to the functionality being tested. "
        "This could include implementation files, interfaces, dependencies, or existing test examples."
    ),
    "relevant_context": (
        "List methods, functions, classes, or modules that need test coverage, in the format "
        "'ClassName.methodName', 'functionName', or 'module.ClassName'. Prioritize critical business logic, "
        "public APIs, complex algorithms, and error-prone code paths."
    ),
    "confidence": (
        "Indicate your current confidence in the test generation assessment. Use: 'exploring' (starting analysis), "
        "'low' (early investigation), 'medium' (some patterns identified), 'high' (strong understanding), "
        "'very_high' (very strong understanding), 'almost_certain' (nearly complete test plan), 'certain' "
        "(100% confidence - test plan is thoroughly complete and all test scenarios are identified with no need for external model validation). "
        "Do NOT use 'certain' unless the test generation analysis is comprehensively complete, use 'very_high' or 'almost_certain' instead if not 100% sure. "
        "Using 'certain' means you have complete confidence locally and prevents external model validation."
    ),
    "backtrack_from_step": (
        "If an earlier finding or assessment needs to be revised or discarded, specify the step number from which to "
        "start over. Use this to acknowledge investigative dead ends and correct the course."
    ),
    "images": (
        "Optional list of absolute paths to architecture diagrams, flow charts, or visual documentation that help "
        "understand the code structure and test requirements. Only include if they materially assist test planning."
    ),
}


class TestGenRequest(WorkflowRequest):
    """Request model for test generation workflow investigation steps"""

    # Required fields for each investigation step
    step: str = Field(..., description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"])

    # Investigation tracking fields
    findings: str = Field(..., description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["findings"])
    files_checked: list[str] = Field(
        default_factory=list, description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["files_checked"]
    )
    relevant_files: list[str] = Field(
        default_factory=list, description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"]
    )
    relevant_context: list[str] = Field(
        default_factory=list, description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["relevant_context"]
    )
    confidence: Optional[str] = Field("low", description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["confidence"])

    # Optional backtracking field
    backtrack_from_step: Optional[int] = Field(
        None, description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["backtrack_from_step"]
    )

    # Optional images for visual context
    images: Optional[list[str]] = Field(default=None, description=TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["images"])

    # Override inherited fields to exclude them from schema (except model which needs to be available)
    temperature: Optional[float] = Field(default=None, exclude=True)
    thinking_mode: Optional[str] = Field(default=None, exclude=True)
    use_websearch: Optional[bool] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_step_one_requirements(self):
        """Ensure step 1 has required relevant_files field."""
        if self.step_number == 1 and not self.relevant_files:
            raise ValueError("Step 1 requires 'relevant_files' field to specify code files to generate tests for")
        return self


class TestGenTool(WorkflowTool):
    """
    Test Generation workflow tool for step-by-step test planning and expert validation.

    This tool implements a structured test generation workflow that guides users through
    methodical investigation steps, ensuring thorough code examination, pattern identification,
    and test scenario planning before reaching conclusions. It supports complex testing scenarios
    including edge case identification, framework detection, and comprehensive coverage planning.
    """

    __test__ = False  # Prevent pytest from collecting this class as a test

    def __init__(self):
        super().__init__()
        self.initial_request = None

    def get_name(self) -> str:
        return "testgen"

    def get_description(self) -> str:
        return (
            "COMPREHENSIVE TEST GENERATION - Creates thorough test suites with edge case coverage. "
            "Use this when you need to generate tests for code, create test scaffolding, or improve test coverage. "
            "BE SPECIFIC about scope: target specific functions/classes/modules rather than testing everything. "
            "Examples: 'Generate tests for User.login() method', 'Test payment processing validation', "
            "'Create tests for authentication error handling'. If user request is vague, either ask for "
            "clarification about specific components to test, or make focused scope decisions and explain them. "
            "Analyzes code paths, identifies realistic failure modes, and generates framework-specific tests. "
            "Supports test pattern following when examples are provided. Choose thinking_mode based on "
            "code complexity: 'low' for simple functions, 'medium' for standard modules (default), "
            "'high' for complex systems with many interactions, 'max' for critical systems requiring "
            "exhaustive test coverage. Note: If you're not currently using a top-tier model such as "
            "Opus 4 or above, these tools can provide enhanced capabilities."
        )

    def get_system_prompt(self) -> str:
        return TESTGEN_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Test generation requires thorough analysis and reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_workflow_request_model(self):
        """Return the test generation workflow-specific request model."""
        return TestGenRequest

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema using WorkflowSchemaBuilder with test generation-specific overrides."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Test generation workflow-specific field overrides
        testgen_field_overrides = {
            "step": {
                "type": "string",
                "description": TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["step"],
            },
            "step_number": {
                "type": "integer",
                "minimum": 1,
                "description": TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["step_number"],
            },
            "total_steps": {
                "type": "integer",
                "minimum": 1,
                "description": TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"],
            },
            "next_step_required": {
                "type": "boolean",
                "description": TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"],
            },
            "findings": {
                "type": "string",
                "description": TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["findings"],
            },
            "files_checked": {
                "type": "array",
                "items": {"type": "string"},
                "description": TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["files_checked"],
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"],
            },
            "confidence": {
                "type": "string",
                "enum": ["exploring", "low", "medium", "high", "very_high", "almost_certain", "certain"],
                "description": TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["confidence"],
            },
            "backtrack_from_step": {
                "type": "integer",
                "minimum": 1,
                "description": TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["backtrack_from_step"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": TESTGEN_WORKFLOW_FIELD_DESCRIPTIONS["images"],
            },
        }

        # Use WorkflowSchemaBuilder with test generation-specific tool fields
        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=testgen_field_overrides,
            model_field_schema=self.get_model_field_schema(),
            auto_mode=self.is_effective_auto_mode(),
            tool_name=self.get_name(),
        )

    def get_required_actions(self, step_number: int, confidence: str, findings: str, total_steps: int) -> list[str]:
        """Define required actions for each investigation phase."""
        if step_number == 1:
            # Initial test generation investigation tasks
            return [
                "Read and understand the code files specified for test generation",
                "Analyze the overall structure, public APIs, and main functionality",
                "Identify critical business logic and complex algorithms that need testing",
                "Look for existing test patterns or examples if provided",
                "Understand dependencies, external interactions, and integration points",
                "Note any potential testability issues or areas that might be hard to test",
            ]
        elif confidence in ["exploring", "low"]:
            # Need deeper investigation
            return [
                "Examine specific functions and methods to understand their behavior",
                "Trace through code paths to identify all possible execution flows",
                "Identify edge cases, boundary conditions, and error scenarios",
                "Check for async operations, state management, and side effects",
                "Look for non-deterministic behavior or external dependencies",
                "Analyze error handling and exception cases that need testing",
            ]
        elif confidence in ["medium", "high"]:
            # Close to completion - need final verification
            return [
                "Verify all critical paths have been identified for testing",
                "Confirm edge cases and boundary conditions are comprehensive",
                "Check that test scenarios cover both success and failure cases",
                "Ensure async behavior and concurrency issues are addressed",
                "Validate that the testing strategy aligns with code complexity",
                "Double-check that findings include actionable test scenarios",
            ]
        else:
            # General investigation needed
            return [
                "Continue examining the codebase for additional test scenarios",
                "Gather more evidence about code behavior and dependencies",
                "Test your assumptions about how the code should be tested",
                "Look for patterns that confirm your testing strategy",
                "Focus on areas that haven't been thoroughly examined yet",
            ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """
        Decide when to call external model based on investigation completeness.

        Always call expert analysis for test generation to get additional test ideas.
        """
        # Check if user requested to skip assistant model
        if request and not self.get_request_use_assistant_model(request):
            return False

        # Always benefit from expert analysis for comprehensive test coverage
        return len(consolidated_findings.relevant_files) > 0 or len(consolidated_findings.findings) >= 1

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Prepare context for external model call for test generation validation."""
        context_parts = [
            f"=== TEST GENERATION REQUEST ===\n{self.initial_request or 'Test generation workflow initiated'}\n=== END REQUEST ==="
        ]

        # Add investigation summary
        investigation_summary = self._build_test_generation_summary(consolidated_findings)
        context_parts.append(
            f"\n=== AGENT'S TEST PLANNING INVESTIGATION ===\n{investigation_summary}\n=== END INVESTIGATION ==="
        )

        # Add relevant code elements if available
        if consolidated_findings.relevant_context:
            methods_text = "\n".join(f"- {method}" for method in consolidated_findings.relevant_context)
            context_parts.append(f"\n=== CODE ELEMENTS TO TEST ===\n{methods_text}\n=== END CODE ELEMENTS ===")

        # Add images if available
        if consolidated_findings.images:
            images_text = "\n".join(f"- {img}" for img in consolidated_findings.images)
            context_parts.append(f"\n=== VISUAL DOCUMENTATION ===\n{images_text}\n=== END VISUAL DOCUMENTATION ===")

        return "\n".join(context_parts)

    def _build_test_generation_summary(self, consolidated_findings) -> str:
        """Prepare a comprehensive summary of the test generation investigation."""
        summary_parts = [
            "=== SYSTEMATIC TEST GENERATION INVESTIGATION SUMMARY ===",
            f"Total steps: {len(consolidated_findings.findings)}",
            f"Files examined: {len(consolidated_findings.files_checked)}",
            f"Relevant files identified: {len(consolidated_findings.relevant_files)}",
            f"Code elements to test: {len(consolidated_findings.relevant_context)}",
            "",
            "=== INVESTIGATION PROGRESSION ===",
        ]

        for finding in consolidated_findings.findings:
            summary_parts.append(finding)

        return "\\n".join(summary_parts)

    def should_include_files_in_expert_prompt(self) -> bool:
        """Include files in expert analysis for comprehensive test generation."""
        return True

    def should_embed_system_prompt(self) -> bool:
        """Embed system prompt in expert analysis for proper context."""
        return True

    def get_expert_thinking_mode(self) -> str:
        """Use high thinking mode for thorough test generation analysis."""
        return "high"

    def get_expert_analysis_instruction(self) -> str:
        """Get specific instruction for test generation expert analysis."""
        return (
            "Please provide comprehensive test generation guidance based on the investigation findings. "
            "Focus on identifying additional test scenarios, edge cases not yet covered, framework-specific "
            "best practices, and providing concrete test implementation examples following the multi-agent "
            "workflow specified in the system prompt."
        )

    # Hook method overrides for test generation-specific behavior

    def prepare_step_data(self, request) -> dict:
        """
        Map test generation-specific fields for internal processing.
        """
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": request.findings,
            "files_checked": request.files_checked,
            "relevant_files": request.relevant_files,
            "relevant_context": request.relevant_context,
            "confidence": request.confidence,
            "images": request.images or [],
        }
        return step_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """
        Test generation workflow skips expert analysis when the CLI agent has "certain" confidence.
        """
        return request.confidence == "certain" and not request.next_step_required

    def store_initial_issue(self, step_description: str):
        """Store initial request for expert analysis."""
        self.initial_request = step_description

    # Override inheritance hooks for test generation-specific behavior

    def get_completion_status(self) -> str:
        """Test generation tools use test-specific status."""
        return "test_generation_complete_ready_for_implementation"

    def get_completion_data_key(self) -> str:
        """Test generation uses 'complete_test_generation' key."""
        return "complete_test_generation"

    def get_final_analysis_from_request(self, request):
        """Test generation tools use findings for final analysis."""
        return request.findings

    def get_confidence_level(self, request) -> str:
        """Test generation tools use 'certain' for high confidence."""
        return "certain"

    def get_completion_message(self) -> str:
        """Test generation-specific completion message."""
        return (
            "Test generation analysis complete with CERTAIN confidence. You have identified all test scenarios "
            "and provided comprehensive coverage strategy. MANDATORY: Present the user with the complete test plan "
            "and IMMEDIATELY proceed with creating the test files following the identified patterns and framework. "
            "Focus on implementing concrete, runnable tests with proper assertions."
        )

    def get_skip_reason(self) -> str:
        """Test generation-specific skip reason."""
        return "Completed comprehensive test planning with full confidence locally"

    def get_skip_expert_analysis_status(self) -> str:
        """Test generation-specific expert analysis skip status."""
        return "skipped_due_to_certain_test_confidence"

    def prepare_work_summary(self) -> str:
        """Test generation-specific work summary."""
        return self._build_test_generation_summary(self.consolidated_findings)

    def get_completion_next_steps_message(self, expert_analysis_used: bool = False) -> str:
        """
        Test generation-specific completion message.
        """
        base_message = (
            "TEST GENERATION ANALYSIS IS COMPLETE. You MUST now implement ALL identified test scenarios, "
            "creating comprehensive test files that cover happy paths, edge cases, error conditions, and "
            "boundary scenarios. Organize tests by functionality, use appropriate assertions, and follow "
            "the identified framework patterns. Provide concrete, executable test code—make it easy for "
            "a developer to run the tests and understand what each test validates."
        )

        # Add expert analysis guidance only when expert analysis was actually used
        if expert_analysis_used:
            expert_guidance = self.get_expert_analysis_guidance()
            if expert_guidance:
                return f"{base_message}\\n\\n{expert_guidance}"

        return base_message

    def get_expert_analysis_guidance(self) -> str:
        """
        Provide specific guidance for handling expert analysis in test generation.
        """
        return (
            "IMPORTANT: Additional test scenarios and edge cases have been provided by the expert analysis above. "
            "You MUST incorporate these suggestions into your test implementation, ensuring comprehensive coverage. "
            "Validate that the expert's test ideas are practical and align with the codebase structure. Combine "
            "your systematic investigation findings with the expert's additional scenarios to create a thorough "
            "test suite that catches real-world bugs before they reach production."
        )

    def get_step_guidance_message(self, request) -> str:
        """
        Test generation-specific step guidance with detailed investigation instructions.
        """
        step_guidance = self.get_test_generation_step_guidance(request.step_number, request.confidence, request)
        return step_guidance["next_steps"]

    def get_test_generation_step_guidance(self, step_number: int, confidence: str, request) -> dict[str, Any]:
        """
        Provide step-specific guidance for test generation workflow.
        """
        # Generate the next steps instruction based on required actions
        required_actions = self.get_required_actions(step_number, confidence, request.findings, request.total_steps)

        if step_number == 1:
            next_steps = (
                f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. You MUST first analyze "
                f"the code thoroughly using appropriate tools. CRITICAL AWARENESS: You need to understand "
                f"the code structure, identify testable behaviors, find edge cases and boundary conditions, "
                f"and determine the appropriate testing strategy. Use file reading tools, code analysis, and "
                f"systematic examination to gather comprehensive information about what needs to be tested. "
                f"Only call {self.get_name()} again AFTER completing your investigation. When you call "
                f"{self.get_name()} next time, use step_number: {step_number + 1} and report specific "
                f"code paths examined, test scenarios identified, and testing patterns discovered."
            )
        elif confidence in ["exploring", "low"]:
            next_steps = (
                f"STOP! Do NOT call {self.get_name()} again yet. Based on your findings, you've identified areas that need "
                f"deeper analysis for test generation. MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\\n"
                + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\\n\\nOnly call {self.get_name()} again with step_number: {step_number + 1} AFTER "
                + "completing these test planning tasks."
            )
        elif confidence in ["medium", "high"]:
            next_steps = (
                f"WAIT! Your test generation analysis needs final verification. DO NOT call {self.get_name()} immediately. REQUIRED ACTIONS:\\n"
                + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\\n\\nREMEMBER: Ensure you have identified all test scenarios including edge cases and error conditions. "
                f"Document findings with specific test cases to implement, then call {self.get_name()} "
                f"with step_number: {step_number + 1}."
            )
        else:
            next_steps = (
                f"PAUSE ANALYSIS. Before calling {self.get_name()} step {step_number + 1}, you MUST examine more code thoroughly. "
                + "Required: "
                + ", ".join(required_actions[:2])
                + ". "
                + f"Your next {self.get_name()} call (step_number: {step_number + 1}) must include "
                f"NEW test scenarios from actual code analysis, not just theories. NO recursive {self.get_name()} calls "
                f"without investigation work!"
            )

        return {"next_steps": next_steps}

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """
        Customize response to match test generation workflow format.
        """
        # Store initial request on first step
        if request.step_number == 1:
            self.initial_request = request.step

        # Convert generic status names to test generation-specific ones
        tool_name = self.get_name()
        status_mapping = {
            f"{tool_name}_in_progress": "test_generation_in_progress",
            f"pause_for_{tool_name}": "pause_for_test_analysis",
            f"{tool_name}_required": "test_analysis_required",
            f"{tool_name}_complete": "test_generation_complete",
        }

        if response_data["status"] in status_mapping:
            response_data["status"] = status_mapping[response_data["status"]]

        # Rename status field to match test generation workflow
        if f"{tool_name}_status" in response_data:
            response_data["test_generation_status"] = response_data.pop(f"{tool_name}_status")
            # Add test generation-specific status fields
            response_data["test_generation_status"]["test_scenarios_identified"] = len(
                self.consolidated_findings.relevant_context
            )
            response_data["test_generation_status"]["analysis_confidence"] = self.get_request_confidence(request)

        # Map complete_testgen to complete_test_generation
        if f"complete_{tool_name}" in response_data:
            response_data["complete_test_generation"] = response_data.pop(f"complete_{tool_name}")

        # Map the completion flag to match test generation workflow
        if f"{tool_name}_complete" in response_data:
            response_data["test_generation_complete"] = response_data.pop(f"{tool_name}_complete")

        return response_data

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the test generation workflow-specific request model."""
        return TestGenRequest

    async def prepare_prompt(self, request) -> str:
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
