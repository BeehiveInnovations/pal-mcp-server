"""
CodeReview Workflow tool - Systematic code review with step-by-step analysis

This tool provides a structured workflow for comprehensive code review and analysis.
It guides the CLI agent through systematic investigation steps with forced pauses between each step
to ensure thorough code examination, issue identification, and quality assessment before proceeding.
The tool supports complex review scenarios including security analysis, performance evaluation,
and architectural assessment.

Key features:
- Step-by-step code review workflow with progress tracking
- Context-aware file embedding (references during investigation, full content for analysis)
- Automatic issue tracking with severity classification
- Expert analysis integration with external models
- Support for focused reviews (security, performance, architecture)
- Confidence-based workflow optimization
"""

import logging
from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic import Field, model_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import CODEREVIEW_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions for code review workflow
CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS = {
    "step": (
        "Review narrative. Step 1: outline the review strategy. Later steps: report findings. MUST cover quality, security, "
        "performance, and architecture. Reference code via `relevant_files`; avoid dumping large snippets."
    ),
    "step_number": "Current review step (starts at 1) – each step should build on the last.",
    "total_steps": (
        "Number of review steps planned. External validation: two steps (analysis + summary). Internal validation: one step. "
        "Use the same limits when continuing an existing review via continuation_id."
    ),
    "next_step_required": (
        "True when another review step follows. External validation: step 1 → True, step 2 → False. Internal validation: set False immediately. "
        "Apply the same rule on continuation flows."
    ),
    "findings": "Capture findings (positive and negative) across quality, security, performance, and architecture; update each step.",
    "files_checked": "Absolute paths of every file reviewed, including those ruled out.",
    "relevant_files": "Step 1: list all files/dirs under review. Must be absolute full non-abbreviated paths. Final step: narrow to files tied to key findings.",
    "relevant_context": "Functions or methods central to findings (e.g. 'Class.method' or 'function_name').",
    "issues_found": "Issues with severity (critical/high/medium/low) and descriptions.",
    "review_validation_type": "Set 'external' (default) for expert follow-up or 'internal' for local-only review.",
    "images": "Optional diagram or screenshot paths that clarify review context.",
    "review_type": "Review focus: full, security, performance, or quick.",
    "focus_on": "Optional note on areas to emphasise (e.g. 'threading', 'auth flow').",
    "standards": "Coding standards or style guides to enforce.",
    "severity_filter": "Lowest severity to include when reporting issues (critical/high/medium/low/all).",
}


class CodeReviewRequest(WorkflowRequest):
    """Request model for code review workflow investigation steps"""

    # Required fields for each investigation step
    step: str = Field(..., description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"])

    # Investigation tracking fields
    findings: str = Field(..., description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["findings"])
    files_checked: list[str] = Field(
        default_factory=list, description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["files_checked"]
    )
    relevant_files: list[str] = Field(
        default_factory=list, description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"]
    )
    relevant_context: list[str] = Field(
        default_factory=list, description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["relevant_context"]
    )
    issues_found: list[dict] = Field(
        default_factory=list, description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["issues_found"]
    )
    # Deprecated confidence field kept for backward compatibility only
    confidence: Optional[str] = Field("low", exclude=True)
    review_validation_type: Optional[Literal["external", "internal"]] = Field(
        "external", description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS.get("review_validation_type", "")
    )

    # Optional images for visual context
    images: Optional[list[str]] = Field(default=None, description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["images"])

    # Code review-specific fields (only used in step 1 to initialize)
    review_type: Optional[Literal["full", "security", "performance", "quick"]] = Field(
        "full", description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["review_type"]
    )
    focus_on: Optional[str] = Field(None, description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["focus_on"])
    standards: Optional[str] = Field(None, description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["standards"])
    severity_filter: Optional[Literal["critical", "high", "medium", "low", "all"]] = Field(
        "all", description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["severity_filter"]
    )

    # Override inherited fields to exclude them from schema (except model which needs to be available)
    temperature: Optional[float] = Field(default=None, exclude=True)
    thinking_mode: Optional[str] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_step_one_requirements(self):
        """Ensure step 1 has required relevant_files field."""
        if self.step_number == 1 and not self.relevant_files:
            raise ValueError("Step 1 requires 'relevant_files' field to specify code files or directories to review")
        return self


class CodeReviewTool(WorkflowTool):
    """
    Code Review workflow tool for step-by-step code review and expert analysis.

    This tool implements a structured code review workflow that guides users through
    methodical investigation steps, ensuring thorough code examination, issue identification,
    and quality assessment before reaching conclusions. It supports complex review scenarios
    including security audits, performance analysis, architectural review, and maintainability assessment.
    """

    def __init__(self):
        super().__init__()
        self.initial_request = None
        self.review_config = {}

    def get_name(self) -> str:
        return "codereview"

    def get_description(self) -> str:
        return (
            "Performs systematic, step-by-step code review with expert validation. "
            "Use for comprehensive analysis covering quality, security, performance, and architecture. "
            "Guides through structured investigation to ensure thoroughness."
        )

    def get_system_prompt(self) -> str:
        return CODEREVIEW_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Code review requires thorough analysis and reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_workflow_request_model(self):
        """Return the code review workflow-specific request model."""
        return CodeReviewRequest

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema using WorkflowSchemaBuilder with code review-specific overrides."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Code review workflow-specific field overrides
        codereview_field_overrides = {
            "step": {
                "type": "string",
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["step"],
            },
            "step_number": {
                "type": "integer",
                "minimum": 1,
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["step_number"],
            },
            "total_steps": {
                "type": "integer",
                "minimum": 1,
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"],
            },
            "next_step_required": {
                "type": "boolean",
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"],
            },
            "findings": {
                "type": "string",
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["findings"],
            },
            "files_checked": {
                "type": "array",
                "items": {"type": "string"},
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["files_checked"],
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"],
            },
            "review_validation_type": {
                "type": "string",
                "enum": ["external", "internal"],
                "default": "external",
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS.get("review_validation_type", ""),
            },
            "issues_found": {
                "type": "array",
                "items": {"type": "object"},
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["issues_found"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["images"],
            },
            # Code review-specific fields (for step 1)
            "review_type": {
                "type": "string",
                "enum": ["full", "security", "performance", "quick"],
                "default": "full",
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["review_type"],
            },
            "focus_on": {
                "type": "string",
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["focus_on"],
            },
            "standards": {
                "type": "string",
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["standards"],
            },
            "severity_filter": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low", "all"],
                "default": "all",
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["severity_filter"],
            },
        }

        # Use WorkflowSchemaBuilder with code review-specific tool fields
        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=codereview_field_overrides,
            model_field_schema=self.get_model_field_schema(),
            auto_mode=self.is_effective_auto_mode(),
            tool_name=self.get_name(),
        )

    def get_required_actions(
        self, step_number: int, confidence: str, findings: str, total_steps: int, request=None
    ) -> list[str]:
        """Define required actions for each investigation phase.

        Now includes request parameter for continuation-aware decisions.
        """
        # Check for continuation - fast track mode
        if request:
            continuation_id = self.get_request_continuation_id(request)
            validation_type = self.get_review_validation_type(request)
            if continuation_id and validation_type == "external":
                if step_number == 1:
                    return [
                        "Quickly review the code files to understand context",
                        "Identify any critical issues that need immediate attention",
                        "Note main architectural patterns and design decisions",
                        "Prepare summary of key findings for expert validation",
                    ]
                else:
                    return ["Complete review and proceed to expert analysis"]

        if step_number == 1:
            # Initial code review investigation tasks
            return [
                "Read and understand the code files specified for review",
                "Examine the overall structure, architecture, and design patterns used",
                "Identify the main components, classes, and functions in the codebase",
                "Understand the business logic and intended functionality",
                "Look for obvious issues: bugs, security concerns, performance problems",
                "Note any code smells, anti-patterns, or areas of concern",
            ]
        elif step_number == 2:
            # Deeper investigation for step 2
            return [
                "Examine specific code sections you've identified as concerning",
                "Analyze security implications: input validation, authentication, authorization",
                "Check for performance issues: algorithmic complexity, resource usage, inefficiencies",
                "Look for architectural problems: tight coupling, missing abstractions, scalability issues",
                "Identify code quality issues: readability, maintainability, error handling",
                "Search for over-engineering, unnecessary complexity, or design patterns that could be simplified",
            ]
        elif step_number >= 3:
            # Final verification for later steps
            return [
                "Verify all identified issues have been properly documented with severity levels",
                "Check for any missed critical security vulnerabilities or performance bottlenecks",
                "Confirm that architectural concerns and code quality issues are comprehensively captured",
                "Ensure positive aspects and well-implemented patterns are also noted",
                "Validate that your assessment aligns with the review type and focus areas specified",
                "Double-check that findings are actionable and provide clear guidance for improvements",
            ]
        else:
            # General investigation needed
            return [
                "Continue examining the codebase for additional patterns and potential issues",
                "Gather more evidence using appropriate code analysis techniques",
                "Test your assumptions about code behavior and design decisions",
                "Look for patterns that confirm or refute your current assessment",
                "Focus on areas that haven't been thoroughly examined yet",
            ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """
        Decide when to call external model based on investigation completeness.

        For continuations with external type, always proceed with expert analysis.
        """
        # Check if user requested to skip assistant model
        if request and not self.get_request_use_assistant_model(request):
            return False

        # For continuations with external type, always proceed with expert analysis
        continuation_id = self.get_request_continuation_id(request)
        validation_type = self.get_review_validation_type(request)
        if continuation_id and validation_type == "external":
            return True  # Always perform expert analysis for external continuations

        # Check if we have meaningful investigation data
        return (
            len(consolidated_findings.relevant_files) > 0
            or len(consolidated_findings.findings) >= 2
            or len(consolidated_findings.issues_found) > 0
        )

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Prepare context for external model call for final code review validation."""
        context_parts = [
            f"=== CODE REVIEW REQUEST ===\\n{self.initial_request or 'Code review workflow initiated'}\\n=== END REQUEST ==="
        ]

        # Add investigation summary
        investigation_summary = self._build_code_review_summary(consolidated_findings)
        context_parts.append(
            f"\\n=== AGENT'S CODE REVIEW INVESTIGATION ===\\n{investigation_summary}\\n=== END INVESTIGATION ==="
        )

        # Add review configuration context if available
        if self.review_config:
            config_text = "\\n".join(f"- {key}: {value}" for key, value in self.review_config.items() if value)
            context_parts.append(f"\\n=== REVIEW CONFIGURATION ===\\n{config_text}\\n=== END CONFIGURATION ===")

        # Add relevant code elements if available
        if consolidated_findings.relevant_context:
            methods_text = "\\n".join(f"- {method}" for method in consolidated_findings.relevant_context)
            context_parts.append(f"\\n=== RELEVANT CODE ELEMENTS ===\\n{methods_text}\\n=== END CODE ELEMENTS ===")

        # Add issues found if available
        if consolidated_findings.issues_found:
            issues_text = "\\n".join(
                f"[{issue.get('severity', 'unknown').upper()}] {issue.get('description', 'No description')}"
                for issue in consolidated_findings.issues_found
            )
            context_parts.append(f"\\n=== ISSUES IDENTIFIED ===\\n{issues_text}\\n=== END ISSUES ===")

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
                f"\\n=== VISUAL REVIEW INFORMATION ===\\n{images_text}\\n=== END VISUAL INFORMATION ==="
            )

        return "\\n".join(context_parts)

    def _build_code_review_summary(self, consolidated_findings) -> str:
        """Prepare a comprehensive summary of the code review investigation."""
        summary_parts = [
            "=== SYSTEMATIC CODE REVIEW INVESTIGATION SUMMARY ===",
            f"Total steps: {len(consolidated_findings.findings)}",
            f"Files examined: {len(consolidated_findings.files_checked)}",
            f"Relevant files identified: {len(consolidated_findings.relevant_files)}",
            f"Code elements analyzed: {len(consolidated_findings.relevant_context)}",
            f"Issues identified: {len(consolidated_findings.issues_found)}",
            "",
            "=== INVESTIGATION PROGRESSION ===",
        ]

        for finding in consolidated_findings.findings:
            summary_parts.append(finding)

        return "\\n".join(summary_parts)

    def should_include_files_in_expert_prompt(self) -> bool:
        """Include files in expert analysis for comprehensive code review."""
        return True

    def should_embed_system_prompt(self) -> bool:
        """Embed system prompt in expert analysis for proper context."""
        return True

    def get_expert_thinking_mode(self) -> str:
        """Use high thinking mode for thorough code review analysis."""
        return "high"

    def get_expert_analysis_instruction(self) -> str:
        """Get specific instruction for code review expert analysis."""
        return (
            "Please provide comprehensive code review analysis based on the investigation findings. "
            "Focus on identifying any remaining issues, validating the completeness of the analysis, "
            "and providing final recommendations for code improvements, following the severity-based "
            "format specified in the system prompt."
        )

    # Hook method overrides for code review-specific behavior

    def prepare_step_data(self, request) -> dict:
        """
        Map code review-specific fields for internal processing.
        """
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": request.findings,
            "files_checked": request.files_checked,
            "relevant_files": request.relevant_files,
            "relevant_context": request.relevant_context,
            "issues_found": request.issues_found,
            "review_validation_type": self.get_review_validation_type(request),
            "hypothesis": request.findings,  # Map findings to hypothesis for compatibility
            "images": request.images or [],
            "confidence": "high",  # Dummy value for workflow_mixin compatibility
        }
        return step_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """
        Code review workflow skips expert analysis only when review_validation_type is "internal".
        Default is always to use expert analysis (external).
        For continuations with external type, always perform expert analysis immediately.
        """
        # If it's a continuation and review_validation_type is external, don't skip
        continuation_id = self.get_request_continuation_id(request)
        validation_type = self.get_review_validation_type(request)
        if continuation_id and validation_type != "internal":
            return False  # Always do expert analysis for external continuations

        # Only skip if explicitly set to internal AND review is complete
        return validation_type == "internal" and not request.next_step_required

    def store_initial_issue(self, step_description: str):
        """Store initial request for expert analysis."""
        self.initial_request = step_description

    # Override inheritance hooks for code review-specific behavior

    def get_review_validation_type(self, request) -> str:
        """Get review validation type from request. Hook method for clean inheritance."""
        try:
            return request.review_validation_type or "external"
        except AttributeError:
            return "external"  # Default to external validation

    def get_completion_status(self) -> str:
        """Code review tools use review-specific status."""
        return "code_review_complete_ready_for_implementation"

    def get_completion_data_key(self) -> str:
        """Code review uses 'complete_code_review' key."""
        return "complete_code_review"

    def get_final_analysis_from_request(self, request):
        """Code review tools use 'findings' field."""
        return request.findings

    def get_confidence_level(self, request) -> str:
        """Code review tools use 'certain' for high confidence."""
        return "certain"

    def get_completion_message(self) -> str:
        """Code review-specific completion message."""
        return (
            "Code review complete. You have identified all significant issues "
            "and provided comprehensive analysis. MANDATORY: Present the user with the complete review results "
            "categorized by severity, and IMMEDIATELY proceed with implementing the highest priority fixes "
            "or provide specific guidance for improvements. Focus on actionable recommendations."
        )

    def get_skip_reason(self) -> str:
        """Code review-specific skip reason."""
        return "Completed comprehensive code review with internal analysis only (no external model validation)"

    def get_skip_expert_analysis_status(self) -> str:
        """Code review-specific expert analysis skip status."""
        return "skipped_due_to_internal_analysis_type"

    def prepare_work_summary(self) -> str:
        """Code review-specific work summary."""
        return self._build_code_review_summary(self.consolidated_findings)

    def get_completion_next_steps_message(self, expert_analysis_used: bool = False) -> str:
        """
        Code review-specific completion message.
        """
        base_message = (
            "CODE REVIEW IS COMPLETE. You MUST now summarize and present ALL review findings organized by "
            "severity (Critical → High → Medium → Low), specific code locations with line numbers, and exact "
            "recommendations for improvement. Clearly prioritize the top 3 issues that need immediate attention. "
            "Provide concrete, actionable guidance for each issue—make it easy for a developer to understand "
            "exactly what needs to be fixed and how to implement the improvements."
        )

        # Add expert analysis guidance only when expert analysis was actually used
        if expert_analysis_used:
            expert_guidance = self.get_expert_analysis_guidance()
            if expert_guidance:
                return f"{base_message}\n\n{expert_guidance}"

        return base_message

    def get_expert_analysis_guidance(self) -> str:
        """
        Provide specific guidance for handling expert analysis in code reviews.
        """
        return (
            "IMPORTANT: Analysis from an assistant model has been provided above. You MUST critically evaluate and validate "
            "the expert findings rather than accepting them blindly. Cross-reference the expert analysis with "
            "your own investigation findings, verify that suggested improvements are appropriate for this "
            "codebase's context and patterns, and ensure recommendations align with the project's standards. "
            "Present a synthesis that combines your systematic review with validated expert insights, clearly "
            "distinguishing between findings you've independently confirmed and additional insights from expert analysis."
        )

    def get_step_guidance_message(self, request) -> str:
        """
        Code review-specific step guidance with detailed investigation instructions.
        """
        step_guidance = self.get_code_review_step_guidance(request.step_number, request)
        return step_guidance["next_steps"]

    def get_code_review_step_guidance(self, step_number: int, request) -> dict[str, Any]:
        """
        Provide step-specific guidance for code review workflow.
        Uses get_required_actions to determine what needs to be done,
        then formats those actions into appropriate guidance messages.
        """
        # Get the required actions from the single source of truth
        required_actions = self.get_required_actions(
            step_number,
            "medium",  # Dummy value for backward compatibility
            request.findings or "",
            request.total_steps,
            request,  # Pass request for continuation-aware decisions
        )

        # Check if this is a continuation to provide context-aware guidance
        continuation_id = self.get_request_continuation_id(request)
        validation_type = self.get_review_validation_type(request)
        is_external_continuation = continuation_id and validation_type == "external"
        is_internal_continuation = continuation_id and validation_type == "internal"

        # Step 1 handling
        if step_number == 1:
            if is_external_continuation:
                # Fast-track for external continuations
                return {
                    "next_steps": (
                        "You are on step 1 of MAXIMUM 2 steps for continuation. CRITICAL: Quickly review the code NOW. "
                        "MANDATORY ACTIONS:\\n"
                        + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                        + "\\n\\nSet next_step_required=True and step_number=2 for the next call to trigger expert analysis."
                    )
                }
            elif is_internal_continuation:
                # Internal validation mode
                next_steps = (
                    "Continuing previous conversation with internal validation only. The analysis will build "
                    "upon the prior findings without external model validation. REQUIRED ACTIONS:\\n"
                    + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                )
            else:
                # Normal flow for new reviews
                next_steps = (
                    f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. You MUST first examine "
                    f"the code files thoroughly using appropriate tools. CRITICAL AWARENESS: You need to:\\n"
                    + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                    + f"\\n\\nOnly call {self.get_name()} again AFTER completing your investigation. "
                    f"When you call {self.get_name()} next time, use step_number: {step_number + 1} "
                    f"and report specific files examined, issues found, and code quality assessments discovered."
                )

        elif step_number == 2:
            # CRITICAL: Check if violating minimum step requirement
            if (
                request.total_steps >= 3
                and request.step_number < request.total_steps
                and not request.next_step_required
            ):
                next_steps = (
                    f"ERROR: You set total_steps={request.total_steps} but next_step_required=False on step {request.step_number}. "
                    f"This violates the minimum step requirement. You MUST set next_step_required=True until you reach the final step. "
                    f"Call {self.get_name()} again with next_step_required=True and continue your investigation."
                )
            elif is_external_continuation or (not request.next_step_required and validation_type == "external"):
                # Fast-track completion or about to complete for external validation
                next_steps = (
                    "Proceeding immediately to expert analysis. "
                    f"MANDATORY: call {self.get_name()} tool immediately again, and set next_step_required=False to "
                    f"trigger external validation NOW."
                )
            else:
                # Normal flow - deeper analysis needed
                next_steps = (
                    f"STOP! Do NOT call {self.get_name()} again yet. You are on step 2 of {request.total_steps} minimum required steps. "
                    f"MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\\n"
                    + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                    + f"\\n\\nRemember: You MUST set next_step_required=True until step {request.total_steps}. "
                    + f"Only call {self.get_name()} again with step_number: {step_number + 1} AFTER completing these code review tasks."
                )

        elif step_number >= 3:
            if not request.next_step_required and validation_type == "external":
                # About to complete - ready for expert analysis
                next_steps = (
                    "Completing review and proceeding to expert analysis. "
                    "Ensure all findings are documented with specific file references and line numbers."
                )
            else:
                # Later steps - final verification
                next_steps = (
                    f"WAIT! Your code review needs final verification. DO NOT call {self.get_name()} immediately. REQUIRED ACTIONS:\\n"
                    + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                    + f"\\n\\nREMEMBER: Ensure you have identified all significant issues across all severity levels and "
                    f"verified the completeness of your review. Document findings with specific file references and "
                    f"line numbers where applicable, then call {self.get_name()} with step_number: {step_number + 1}."
                )
        else:
            # Fallback for any other case - check minimum step violation first
            if (
                request.total_steps >= 3
                and request.step_number < request.total_steps
                and not request.next_step_required
            ):
                next_steps = (
                    f"ERROR: You set total_steps={request.total_steps} but next_step_required=False on step {request.step_number}. "
                    f"This violates the minimum step requirement. You MUST set next_step_required=True until step {request.total_steps}."
                )
            elif not request.next_step_required and validation_type == "external":
                next_steps = (
                    "Completing review. "
                    "Ensure all findings are documented with specific file references and severity levels."
                )
            else:
                next_steps = (
                    f"PAUSE REVIEW. Before calling {self.get_name()} step {step_number + 1}, you MUST examine more code thoroughly. "
                    + "Required: "
                    + ", ".join(required_actions[:2])
                    + ". "
                    + f"Your next {self.get_name()} call (step_number: {step_number + 1}) must include "
                    f"NEW evidence from actual code analysis, not just theories. NO recursive {self.get_name()} calls "
                    f"without investigation work!"
                )

        return {"next_steps": next_steps}

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """
        Customize response to match code review workflow format.
        """
        # Store initial request on first step
        if request.step_number == 1:
            self.initial_request = request.step
            # Store review configuration for expert analysis
            if request.relevant_files:
                self.review_config = {
                    "relevant_files": request.relevant_files,
                    "review_type": request.review_type,
                    "focus_on": request.focus_on,
                    "standards": request.standards,
                    "severity_filter": request.severity_filter,
                }

        # Convert generic status names to code review-specific ones
        tool_name = self.get_name()
        status_mapping = {
            f"{tool_name}_in_progress": "code_review_in_progress",
            f"pause_for_{tool_name}": "pause_for_code_review",
            f"{tool_name}_required": "code_review_required",
            f"{tool_name}_complete": "code_review_complete",
        }

        if response_data["status"] in status_mapping:
            response_data["status"] = status_mapping[response_data["status"]]

        # Rename status field to match code review workflow
        if f"{tool_name}_status" in response_data:
            response_data["code_review_status"] = response_data.pop(f"{tool_name}_status")
            # Add code review-specific status fields
            response_data["code_review_status"]["issues_by_severity"] = {}
            for issue in self.consolidated_findings.issues_found:
                severity = issue.get("severity", "unknown")
                if severity not in response_data["code_review_status"]["issues_by_severity"]:
                    response_data["code_review_status"]["issues_by_severity"][severity] = 0
                response_data["code_review_status"]["issues_by_severity"][severity] += 1
            response_data["code_review_status"]["review_validation_type"] = self.get_review_validation_type(request)

        # Map complete_codereviewworkflow to complete_code_review
        if f"complete_{tool_name}" in response_data:
            response_data["complete_code_review"] = response_data.pop(f"complete_{tool_name}")

        # Map the completion flag to match code review workflow
        if f"{tool_name}_complete" in response_data:
            response_data["code_review_complete"] = response_data.pop(f"{tool_name}_complete")

        return response_data

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the code review workflow-specific request model."""
        return CodeReviewRequest

    async def prepare_prompt(self, request) -> str:
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
