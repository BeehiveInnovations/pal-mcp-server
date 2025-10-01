"""
Refactor tool - Step-by-step refactoring analysis with expert validation

This tool provides a structured workflow for comprehensive code refactoring analysis.
It guides CLI agent through systematic investigation steps with forced pauses between each step
to ensure thorough code examination, refactoring opportunity identification, and quality
assessment before proceeding. The tool supports complex refactoring scenarios including
code smell detection, decomposition planning, modernization opportunities, and organization improvements.

Key features:
- Step-by-step refactoring investigation workflow with progress tracking
- Context-aware file embedding (references during investigation, full content for analysis)
- Automatic refactoring opportunity tracking with type and severity classification
- Expert analysis integration with external models
- Support for focused refactoring types (codesmells, decompose, modernize, organization)
- Confidence-based workflow optimization with refactor completion tracking
"""

import logging
from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic import Field, model_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import REFACTOR_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions for refactor tool
REFACTOR_FIELD_DESCRIPTIONS = {
    "step": (
        "The refactoring plan. Step 1: State strategy. Later steps: Report findings. "
        "CRITICAL: Examine code for smells, and opportunities for decomposition, modernization, and organization. "
        "Use 'relevant_files' for code. FORBIDDEN: Large code snippets."
    ),
    "step_number": (
        "The index of the current step in the refactoring investigation sequence, beginning at 1. Each step should "
        "build upon or revise the previous one."
    ),
    "total_steps": (
        "Your current estimate for how many steps will be needed to complete the refactoring investigation. "
        "Adjust as new opportunities emerge."
    ),
    "next_step_required": (
        "Set to true if you plan to continue the investigation with another step. False means you believe the "
        "refactoring analysis is complete and ready for expert validation."
    ),
    "findings": (
        "Summary of discoveries from this step, including code smells and opportunities for decomposition, modernization, or organization. "
        "Document both strengths and weaknesses. In later steps, confirm or update past findings."
    ),
    "files_checked": (
        "List all files examined (absolute paths). Include even ruled-out files to track exploration path."
    ),
    "relevant_files": (
        "Subset of files_checked with code requiring refactoring (absolute paths). Include files with "
        "code smells, decomposition needs, or improvement opportunities."
    ),
    "relevant_context": (
        "List methods/functions central to refactoring opportunities, in 'ClassName.methodName' or 'functionName' format. "
        "Prioritize those with code smells or needing improvement."
    ),
    "issues_found": (
        "Refactoring opportunities as dictionaries with 'severity' (critical/high/medium/low), "
        "'type' (codesmells/decompose/modernize/organization), and 'description'. "
        "Include all improvement opportunities found."
    ),
    "confidence": (
        "Your confidence in refactoring analysis: exploring (starting), incomplete (significant work remaining), "
        "partial (some opportunities found, more analysis needed), complete (comprehensive analysis finished, "
        "all major opportunities identified). "
        "WARNING: Use 'complete' ONLY when fully analyzed and can provide recommendations without expert help. "
        "'complete' PREVENTS expert validation. Use 'partial' for large files or uncertain analysis."
    ),
    "backtrack_from_step": ("If an earlier finding needs revision, specify the step number to backtrack from."),
    "images": (
        "Optional list of absolute paths to architecture diagrams, UI mockups, design documents, or visual references "
        "that help with refactoring context. Only include if they materially assist understanding or assessment."
    ),
    "refactor_type": "Type of refactoring analysis to perform (codesmells, decompose, modernize, organization)",
    "focus_areas": "Specific areas to focus on (e.g., 'performance', 'readability', 'maintainability', 'security')",
    "style_guide_examples": (
        "Optional existing code files to use as style/pattern reference (must be FULL absolute paths to real files / "
        "folders - DO NOT SHORTEN). These files represent the target coding style and patterns for the project."
    ),
}


class RefactorRequest(WorkflowRequest):
    """Request model for refactor workflow investigation steps"""

    # Required fields for each investigation step
    step: str = Field(..., description=REFACTOR_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=REFACTOR_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=REFACTOR_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=REFACTOR_FIELD_DESCRIPTIONS["next_step_required"])

    # Investigation tracking fields
    findings: str = Field(..., description=REFACTOR_FIELD_DESCRIPTIONS["findings"])
    files_checked: list[str] = Field(default_factory=list, description=REFACTOR_FIELD_DESCRIPTIONS["files_checked"])
    relevant_files: list[str] = Field(default_factory=list, description=REFACTOR_FIELD_DESCRIPTIONS["relevant_files"])
    relevant_context: list[str] = Field(
        default_factory=list, description=REFACTOR_FIELD_DESCRIPTIONS["relevant_context"]
    )
    issues_found: list[dict] = Field(default_factory=list, description=REFACTOR_FIELD_DESCRIPTIONS["issues_found"])
    confidence: Optional[Literal["exploring", "incomplete", "partial", "complete"]] = Field(
        "incomplete", description=REFACTOR_FIELD_DESCRIPTIONS["confidence"]
    )

    # Optional backtracking field
    backtrack_from_step: Optional[int] = Field(None, description=REFACTOR_FIELD_DESCRIPTIONS["backtrack_from_step"])

    # Optional images for visual context
    images: Optional[list[str]] = Field(default=None, description=REFACTOR_FIELD_DESCRIPTIONS["images"])

    # Refactor-specific fields (only used in step 1 to initialize)
    refactor_type: Optional[Literal["codesmells", "decompose", "modernize", "organization"]] = Field(
        "codesmells", description=REFACTOR_FIELD_DESCRIPTIONS["refactor_type"]
    )
    focus_areas: Optional[list[str]] = Field(None, description=REFACTOR_FIELD_DESCRIPTIONS["focus_areas"])
    style_guide_examples: Optional[list[str]] = Field(
        None, description=REFACTOR_FIELD_DESCRIPTIONS["style_guide_examples"]
    )

    # Override inherited fields to exclude them from schema (except model which needs to be available)
    temperature: Optional[float] = Field(default=None, exclude=True)
    thinking_mode: Optional[str] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_step_one_requirements(self):
        """Ensure step 1 has required relevant_files field."""
        if self.step_number == 1 and not self.relevant_files:
            raise ValueError(
                "Step 1 requires 'relevant_files' field to specify code files or directories to analyze for refactoring"
            )
        return self


class RefactorTool(WorkflowTool):
    """
    Refactor tool for step-by-step refactoring analysis and expert validation.

    This tool implements a structured refactoring workflow that guides users through
    methodical investigation steps, ensuring thorough code examination, refactoring opportunity
    identification, and improvement assessment before reaching conclusions. It supports complex
    refactoring scenarios including code smell detection, decomposition planning, modernization
    opportunities, and organization improvements.
    """

    def __init__(self):
        super().__init__()
        self.initial_request = None
        self.refactor_config = {}

    def get_name(self) -> str:
        return "refactor"

    def get_description(self) -> str:
        return (
            "Analyzes code for refactoring opportunities with systematic investigation. "
            "Use for code smell detection, decomposition planning, modernization, and maintainability improvements. "
            "Guides through structured analysis with expert validation."
        )

    def get_system_prompt(self) -> str:
        return REFACTOR_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Refactor workflow requires thorough analysis and reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_workflow_request_model(self):
        """Return the refactor workflow-specific request model."""
        return RefactorRequest

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema using WorkflowSchemaBuilder with refactor-specific overrides."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Refactor workflow-specific field overrides
        refactor_field_overrides = {
            "step": {
                "type": "string",
                "description": REFACTOR_FIELD_DESCRIPTIONS["step"],
            },
            "step_number": {
                "type": "integer",
                "minimum": 1,
                "description": REFACTOR_FIELD_DESCRIPTIONS["step_number"],
            },
            "total_steps": {
                "type": "integer",
                "minimum": 1,
                "description": REFACTOR_FIELD_DESCRIPTIONS["total_steps"],
            },
            "next_step_required": {
                "type": "boolean",
                "description": REFACTOR_FIELD_DESCRIPTIONS["next_step_required"],
            },
            "findings": {
                "type": "string",
                "description": REFACTOR_FIELD_DESCRIPTIONS["findings"],
            },
            "files_checked": {
                "type": "array",
                "items": {"type": "string"},
                "description": REFACTOR_FIELD_DESCRIPTIONS["files_checked"],
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": REFACTOR_FIELD_DESCRIPTIONS["relevant_files"],
            },
            "confidence": {
                "type": "string",
                "enum": ["exploring", "incomplete", "partial", "complete"],
                "default": "incomplete",
                "description": REFACTOR_FIELD_DESCRIPTIONS["confidence"],
            },
            "backtrack_from_step": {
                "type": "integer",
                "minimum": 1,
                "description": REFACTOR_FIELD_DESCRIPTIONS["backtrack_from_step"],
            },
            "issues_found": {
                "type": "array",
                "items": {"type": "object"},
                "description": REFACTOR_FIELD_DESCRIPTIONS["issues_found"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": REFACTOR_FIELD_DESCRIPTIONS["images"],
            },
            # Refactor-specific fields (for step 1)
            # Note: Use relevant_files field instead of files for consistency
            "refactor_type": {
                "type": "string",
                "enum": ["codesmells", "decompose", "modernize", "organization"],
                "default": "codesmells",
                "description": REFACTOR_FIELD_DESCRIPTIONS["refactor_type"],
            },
            "focus_areas": {
                "type": "array",
                "items": {"type": "string"},
                "description": REFACTOR_FIELD_DESCRIPTIONS["focus_areas"],
            },
            "style_guide_examples": {
                "type": "array",
                "items": {"type": "string"},
                "description": REFACTOR_FIELD_DESCRIPTIONS["style_guide_examples"],
            },
        }

        # Use WorkflowSchemaBuilder with refactor-specific tool fields
        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=refactor_field_overrides,
            model_field_schema=self.get_model_field_schema(),
            auto_mode=self.is_effective_auto_mode(),
            tool_name=self.get_name(),
        )

    def get_required_actions(
        self, step_number: int, confidence: str, findings: str, total_steps: int, request=None
    ) -> list[str]:
        """Define required actions for each investigation phase."""
        if step_number == 1:
            # Initial refactoring investigation tasks
            return [
                "Read and understand the code files specified for refactoring analysis",
                "Examine the overall structure, architecture, and design patterns used",
                "Identify potential code smells: long methods, large classes, duplicate code, complex conditionals",
                "Look for decomposition opportunities: oversized components that could be broken down",
                "Check for modernization opportunities: outdated patterns, deprecated features, newer language constructs",
                "Assess organization: logical grouping, file structure, naming conventions, module boundaries",
                "Document specific refactoring opportunities with file locations and line numbers",
            ]
        elif confidence in ["exploring", "incomplete"]:
            # Need deeper investigation
            return [
                "Examine specific code sections you've identified as needing refactoring",
                "Analyze code smells in detail: complexity, coupling, cohesion issues",
                "Investigate decomposition opportunities: identify natural breaking points for large components",
                "Look for modernization possibilities: language features, patterns, libraries that could improve the code",
                "Check organization issues: related functionality that could be better grouped or structured",
                "Trace dependencies and relationships between components to understand refactoring impact",
                "Prioritize refactoring opportunities by impact and effort required",
            ]
        elif confidence == "partial":
            # Close to completion - need final verification
            return [
                "Verify all identified refactoring opportunities have been properly documented with locations",
                "Check for any missed opportunities in areas not yet thoroughly examined",
                "Confirm that refactoring suggestions align with the specified refactor_type and focus_areas",
                "Ensure refactoring opportunities are prioritized by severity and impact",
                "Validate that proposed changes would genuinely improve code quality without breaking functionality",
                "Double-check that all relevant files and code elements are captured in your analysis",
            ]
        else:
            # General investigation needed
            return [
                "Continue examining the codebase for additional refactoring opportunities",
                "Gather more evidence using appropriate code analysis techniques",
                "Test your assumptions about code quality and improvement possibilities",
                "Look for patterns that confirm or refute your current refactoring assessment",
                "Focus on areas that haven't been thoroughly examined for refactoring potential",
            ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """
        Decide when to call external model based on investigation completeness.

        Don't call expert analysis if the CLI agent has certain confidence and complete refactoring - trust their judgment.
        """
        # Check if user requested to skip assistant model
        if request and not self.get_request_use_assistant_model(request):
            return False

        # Check if refactoring work is complete
        if request and request.confidence == "complete":
            return False

        # Check if we have meaningful investigation data
        return (
            len(consolidated_findings.relevant_files) > 0
            or len(consolidated_findings.findings) >= 2
            or len(consolidated_findings.issues_found) > 0
        )

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Prepare context for external model call for final refactoring validation."""
        context_parts = [
            f"=== REFACTORING ANALYSIS REQUEST ===\\n{self.initial_request or 'Refactoring workflow initiated'}\\n=== END REQUEST ==="
        ]

        # Add investigation summary
        investigation_summary = self._build_refactoring_summary(consolidated_findings)
        context_parts.append(
            f"\\n=== AGENT'S REFACTORING INVESTIGATION ===\\n{investigation_summary}\\n=== END INVESTIGATION ==="
        )

        # Add refactor configuration context if available
        if self.refactor_config:
            config_text = "\\n".join(f"- {key}: {value}" for key, value in self.refactor_config.items() if value)
            context_parts.append(f"\\n=== REFACTOR CONFIGURATION ===\\n{config_text}\\n=== END CONFIGURATION ===")

        # Add relevant code elements if available
        if consolidated_findings.relevant_context:
            methods_text = "\\n".join(f"- {method}" for method in consolidated_findings.relevant_context)
            context_parts.append(f"\\n=== RELEVANT CODE ELEMENTS ===\\n{methods_text}\\n=== END CODE ELEMENTS ===")

        # Add refactoring opportunities found if available
        if consolidated_findings.issues_found:
            opportunities_text = "\\n".join(
                f"[{issue.get('severity', 'unknown').upper()}] {issue.get('type', 'unknown').upper()}: {issue.get('description', 'No description')}"
                for issue in consolidated_findings.issues_found
            )
            context_parts.append(
                f"\\n=== REFACTORING OPPORTUNITIES ===\\n{opportunities_text}\\n=== END OPPORTUNITIES ==="
            )

        # Add assessment evolution if available
        if consolidated_findings.hypotheses:
            assessments_text = "\\n".join(
                f"Step {h['step']} ({h['confidence']} confidence): {h['hypothesis']}"
                for h in consolidated_findings.hypotheses
            )
            context_parts.append(f"\\n=== ASSESSMENT EVOLUTION ===\\n{assessments_text}\\n=== END ASSESSMENTS ===")

        # Add images if available
        if consolidated_findings.images:
            images_text = "\\n".join(f"- {img}" for img in consolidated_findings.images)
            context_parts.append(
                f"\\n=== VISUAL REFACTORING INFORMATION ===\\n{images_text}\\n=== END VISUAL INFORMATION ==="
            )

        return "\\n".join(context_parts)

    def _build_refactoring_summary(self, consolidated_findings) -> str:
        """Prepare a comprehensive summary of the refactoring investigation."""
        summary_parts = [
            "=== SYSTEMATIC REFACTORING INVESTIGATION SUMMARY ===",
            f"Total steps: {len(consolidated_findings.findings)}",
            f"Files examined: {len(consolidated_findings.files_checked)}",
            f"Relevant files identified: {len(consolidated_findings.relevant_files)}",
            f"Code elements analyzed: {len(consolidated_findings.relevant_context)}",
            f"Refactoring opportunities identified: {len(consolidated_findings.issues_found)}",
            "",
            "=== INVESTIGATION PROGRESSION ===",
        ]

        for finding in consolidated_findings.findings:
            summary_parts.append(finding)

        return "\\n".join(summary_parts)

    def should_include_files_in_expert_prompt(self) -> bool:
        """Include files in expert analysis for comprehensive refactoring validation."""
        return True

    def should_embed_system_prompt(self) -> bool:
        """Embed system prompt in expert analysis for proper context."""
        return True

    def get_expert_thinking_mode(self) -> str:
        """Use high thinking mode for thorough refactoring analysis."""
        return "high"

    def get_expert_analysis_instruction(self) -> str:
        """Get specific instruction for refactoring expert analysis."""
        return (
            "Please provide comprehensive refactoring analysis based on the investigation findings. "
            "Focus on validating the identified opportunities, ensuring completeness of the analysis, "
            "and providing final recommendations for refactoring implementation, following the structured "
            "format specified in the system prompt."
        )

    # Hook method overrides for refactor-specific behavior

    def prepare_step_data(self, request) -> dict:
        """
        Map refactor workflow-specific fields for internal processing.
        """
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": request.findings,
            "files_checked": request.files_checked,
            "relevant_files": request.relevant_files,
            "relevant_context": request.relevant_context,
            "issues_found": request.issues_found,
            "confidence": request.confidence,
            "hypothesis": request.findings,  # Map findings to hypothesis for compatibility
            "images": request.images or [],
        }
        return step_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """
        Refactor workflow skips expert analysis when the CLI agent has "complete" confidence.
        """
        return request.confidence == "complete" and not request.next_step_required

    def store_initial_issue(self, step_description: str):
        """Store initial request for expert analysis."""
        self.initial_request = step_description

    # Inheritance hook methods for refactor-specific behavior

    # Override inheritance hooks for refactor-specific behavior

    def get_completion_status(self) -> str:
        """Refactor tools use refactor-specific status."""
        return "refactoring_analysis_complete_ready_for_implementation"

    def get_completion_data_key(self) -> str:
        """Refactor uses 'complete_refactoring' key."""
        return "complete_refactoring"

    def get_final_analysis_from_request(self, request):
        """Refactor tools use 'findings' field."""
        return request.findings

    def get_confidence_level(self, request) -> str:
        """Refactor tools use 'complete' for high confidence."""
        return "complete"

    def get_completion_message(self) -> str:
        """Refactor-specific completion message."""
        return (
            "Refactoring analysis complete with COMPLETE confidence. You have identified all significant "
            "refactoring opportunities and provided comprehensive analysis. MANDATORY: Present the user with "
            "the complete refactoring results organized by type and severity, and IMMEDIATELY proceed with "
            "implementing the highest priority refactoring opportunities or provide specific guidance for "
            "improvements. Focus on actionable refactoring steps."
        )

    def get_skip_reason(self) -> str:
        """Refactor-specific skip reason."""
        return "Completed comprehensive refactoring analysis with full confidence locally"

    def get_skip_expert_analysis_status(self) -> str:
        """Refactor-specific expert analysis skip status."""
        return "skipped_due_to_complete_refactoring_confidence"

    def prepare_work_summary(self) -> str:
        """Refactor-specific work summary."""
        return self._build_refactoring_summary(self.consolidated_findings)

    def get_completion_next_steps_message(self, expert_analysis_used: bool = False) -> str:
        """
        Refactor-specific completion message.

        Args:
            expert_analysis_used: True if expert analysis was successfully executed
        """
        base_message = (
            "REFACTORING ANALYSIS IS COMPLETE. You MUST now summarize and present ALL refactoring opportunities "
            "organized by type (codesmells → decompose → modernize → organization) and severity (Critical → High → "
            "Medium → Low), specific code locations with line numbers, and exact recommendations for improvement. "
            "Clearly prioritize the top 3 refactoring opportunities that need immediate attention. Provide concrete, "
            "actionable guidance for each opportunity—make it easy for a developer to understand exactly what needs "
            "to be refactored and how to implement the improvements."
        )

        # Add expert analysis guidance only when expert analysis was actually used
        if expert_analysis_used:
            expert_guidance = self.get_expert_analysis_guidance()
            if expert_guidance:
                return f"{base_message}\n\n{expert_guidance}"

        return base_message

    def get_expert_analysis_guidance(self) -> str:
        """
        Get additional guidance for handling expert analysis results in refactor context.

        Returns:
            Additional guidance text for validating and using expert analysis findings
        """
        return (
            "IMPORTANT: Expert refactoring analysis has been provided above. You MUST review "
            "the expert's architectural insights and refactoring recommendations. Consider whether "
            "the expert's suggestions align with the codebase's evolution trajectory and current "
            "team priorities. Pay special attention to any breaking changes, migration complexity, "
            "or performance implications highlighted by the expert. Present a balanced view that "
            "considers both immediate benefits and long-term maintainability."
        )

    def get_step_guidance_message(self, request) -> str:
        """
        Refactor-specific step guidance with detailed investigation instructions.
        """
        step_guidance = self.get_refactor_step_guidance(request.step_number, request.confidence, request)
        return step_guidance["next_steps"]

    def get_refactor_step_guidance(self, step_number: int, confidence: str, request) -> dict[str, Any]:
        """
        Provide step-specific guidance for refactor workflow.
        """
        # Generate the next steps instruction based on required actions
        required_actions = self.get_required_actions(step_number, confidence, request.findings, request.total_steps)

        if step_number == 1:
            next_steps = (
                f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. You MUST first examine "
                f"the code files thoroughly for refactoring opportunities using appropriate tools. CRITICAL AWARENESS: "
                f"You need to identify code smells, decomposition opportunities, modernization possibilities, and "
                f"organization improvements across the specified refactor_type. Look for complexity issues, outdated "
                f"patterns, oversized components, and structural problems. Use file reading tools, code analysis, and "
                f"systematic examination to gather comprehensive refactoring information. Only call {self.get_name()} "
                f"again AFTER completing your investigation. When you call {self.get_name()} next time, use "
                f"step_number: {step_number + 1} and report specific files examined, refactoring opportunities found, "
                f"and improvement assessments discovered."
            )
        elif confidence in ["exploring", "incomplete"]:
            next_steps = (
                f"STOP! Do NOT call {self.get_name()} again yet. Based on your findings, you've identified areas that need "
                f"deeper refactoring analysis. MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\\n"
                + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\\n\\nOnly call {self.get_name()} again with step_number: {step_number + 1} AFTER "
                + "completing these refactoring analysis tasks."
            )
        elif confidence == "partial":
            next_steps = (
                f"WAIT! Your refactoring analysis needs final verification. DO NOT call {self.get_name()} immediately. REQUIRED ACTIONS:\\n"
                + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\\n\\nREMEMBER: Ensure you have identified all significant refactoring opportunities across all types and "
                f"verified the completeness of your analysis. Document opportunities with specific file references and "
                f"line numbers where applicable, then call {self.get_name()} with step_number: {step_number + 1}."
            )
        else:
            next_steps = (
                f"PAUSE REFACTORING ANALYSIS. Before calling {self.get_name()} step {step_number + 1}, you MUST examine more code thoroughly. "
                + "Required: "
                + ", ".join(required_actions[:2])
                + ". "
                + f"Your next {self.get_name()} call (step_number: {step_number + 1}) must include "
                f"NEW evidence from actual refactoring analysis, not just theories. NO recursive {self.get_name()} calls "
                f"without investigation work!"
            )

        return {"next_steps": next_steps}

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """
        Customize response to match refactor workflow format.
        """
        # Store initial request on first step
        if request.step_number == 1:
            self.initial_request = request.step
            # Store refactor configuration for expert analysis
            if request.relevant_files:
                self.refactor_config = {
                    "relevant_files": request.relevant_files,
                    "refactor_type": request.refactor_type,
                    "focus_areas": request.focus_areas,
                    "style_guide_examples": request.style_guide_examples,
                }

        # Convert generic status names to refactor-specific ones
        tool_name = self.get_name()
        status_mapping = {
            f"{tool_name}_in_progress": "refactoring_analysis_in_progress",
            f"pause_for_{tool_name}": "pause_for_refactoring_analysis",
            f"{tool_name}_required": "refactoring_analysis_required",
            f"{tool_name}_complete": "refactoring_analysis_complete",
        }

        if response_data["status"] in status_mapping:
            response_data["status"] = status_mapping[response_data["status"]]

        # Rename status field to match refactor workflow
        if f"{tool_name}_status" in response_data:
            response_data["refactoring_status"] = response_data.pop(f"{tool_name}_status")
            # Add refactor-specific status fields
            refactor_types = {}
            for issue in self.consolidated_findings.issues_found:
                issue_type = issue.get("type", "unknown")
                if issue_type not in refactor_types:
                    refactor_types[issue_type] = 0
                refactor_types[issue_type] += 1
            response_data["refactoring_status"]["opportunities_by_type"] = refactor_types
            response_data["refactoring_status"]["refactor_confidence"] = request.confidence

        # Map complete_refactor to complete_refactoring
        if f"complete_{tool_name}" in response_data:
            response_data["complete_refactoring"] = response_data.pop(f"complete_{tool_name}")

        # Map the completion flag to match refactor workflow
        if f"{tool_name}_complete" in response_data:
            response_data["refactoring_complete"] = response_data.pop(f"{tool_name}_complete")

        return response_data

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the refactor workflow-specific request model."""
        return RefactorRequest

    async def prepare_prompt(self, request) -> str:
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
