"""
Precommit Workflow tool - Step-by-step pre-commit validation with expert analysis

This tool provides a structured workflow for comprehensive pre-commit validation.
It guides the CLI agent through systematic investigation steps with forced pauses between each step
to ensure thorough code examination, git change analysis, and issue detection before proceeding.
The tool supports finding updates and expert analysis integration.

Key features:
- Step-by-step pre-commit investigation workflow with progress tracking
- Context-aware file embedding (references during investigation, full content for analysis)
- Automatic git repository discovery and change analysis
- Expert analysis integration with external models (default)
- Support for multiple repositories and change types
- Configurable validation type (external with expert model or internal only)
"""

import logging
from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic import Field, model_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import PRECOMMIT_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions for precommit workflow
PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS = {
    "step": (
        "Step 1: outline how you'll validate the git changes. Later steps: report findings. Review diffs and impacts, use `relevant_files`, and avoid pasting large snippets."
    ),
    "step_number": "Current pre-commit step number (starts at 1).",
    "total_steps": (
        "Planned number of validation steps. External validation: use at most three (analysis → follow-ups → summary). Internal validation: a single step. Honour these limits when resuming via continuation_id."
    ),
    "next_step_required": (
        "True to continue with another step, False when validation is complete. "
        "CRITICAL: If total_steps>=3 or when `precommit_type = external`, set to True until the final step. "
        "When continuation_id is provided: Follow the same validation rules based on precommit_type."
    ),
    "findings": "Record git diff insights, risks, missing tests, security concerns, and positives; update previous notes as you go.",
    "files_checked": "Absolute paths for every file examined, including ruled-out candidates.",
    "relevant_files": "Absolute paths of files involved in the change or validation (code, configs, tests, docs). Must be absolute full non-abbreviated paths.",
    "relevant_context": "Key functions/methods touched by the change (e.g. 'Class.method', 'function_name').",
    "issues_found": "List issues with severity (critical/high/medium/low) plus descriptions (bugs, security, performance, coverage).",
    "precommit_type": "'external' (default, triggers expert model) or 'internal' (local-only validation).",
    "images": "Optional absolute paths to screenshots or diagrams that aid validation.",
    "path": "Absolute path to the repository root. Required in step 1.",
    "compare_to": "Optional git ref (branch/tag/commit) to diff against; falls back to staged/unstaged changes.",
    "include_staged": "Whether to inspect staged changes (ignored when `compare_to` is set).",
    "include_unstaged": "Whether to inspect unstaged changes (ignored when `compare_to` is set).",
    "focus_on": "Optional emphasis areas such as security, performance, or test coverage.",
    "severity_filter": "Lowest severity to include when reporting issues.",
}


class PrecommitRequest(WorkflowRequest):
    """Request model for precommit workflow investigation steps"""

    # Required fields for each investigation step
    step: str = Field(..., description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"])

    # Investigation tracking fields
    findings: str = Field(..., description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["findings"])
    files_checked: list[str] = Field(
        default_factory=list, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["files_checked"]
    )
    relevant_files: list[str] = Field(
        default_factory=list, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"]
    )
    relevant_context: list[str] = Field(
        default_factory=list, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["relevant_context"]
    )
    issues_found: list[dict] = Field(
        default_factory=list, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["issues_found"]
    )
    precommit_type: Optional[Literal["external", "internal"]] = Field(
        "external", description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["precommit_type"]
    )

    # Optional images for visual validation
    images: Optional[list[str]] = Field(default=None, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["images"])

    # Precommit-specific fields (only used in step 1 to initialize)
    # Required for step 1, validated in model_validator
    path: Optional[str] = Field(None, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["path"])
    compare_to: Optional[str] = Field(None, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["compare_to"])
    include_staged: Optional[bool] = Field(True, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["include_staged"])
    include_unstaged: Optional[bool] = Field(
        True, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["include_unstaged"]
    )
    focus_on: Optional[str] = Field(None, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["focus_on"])
    severity_filter: Optional[Literal["critical", "high", "medium", "low", "all"]] = Field(
        "all", description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["severity_filter"]
    )

    # Override inherited fields to exclude them from schema (except model which needs to be available)
    temperature: Optional[float] = Field(default=None, exclude=True)
    thinking_mode: Optional[str] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_step_one_requirements(self):
        """Ensure step 1 has required path field."""
        if self.step_number == 1 and not self.path:
            raise ValueError("Step 1 requires 'path' field to specify git repository location")
        return self


class PrecommitTool(WorkflowTool):
    """
    Precommit workflow tool for step-by-step pre-commit validation and expert analysis.

    This tool implements a structured pre-commit validation workflow that guides users through
    methodical investigation steps, ensuring thorough change examination, issue identification,
    and validation before reaching conclusions. It supports complex validation scenarios including
    multi-repository analysis, security review, performance validation, and integration testing.
    """

    def __init__(self):
        super().__init__()
        self.initial_request = None
        self.git_config = {}

    def get_name(self) -> str:
        return "precommit"

    def get_description(self) -> str:
        return (
            "Validates git changes and repository state before committing with systematic analysis. "
            "Use for multi-repository validation, security review, change impact assessment, and completeness verification. "
            "Guides through structured investigation with expert analysis."
        )

    def get_system_prompt(self) -> str:
        return PRECOMMIT_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Precommit requires thorough analysis and reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_workflow_request_model(self):
        """Return the precommit workflow-specific request model."""
        return PrecommitRequest

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema using WorkflowSchemaBuilder with precommit-specific overrides."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Precommit workflow-specific field overrides
        precommit_field_overrides = {
            "step": {
                "type": "string",
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["step"],
            },
            "step_number": {
                "type": "integer",
                "minimum": 1,
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["step_number"],
            },
            "total_steps": {
                "type": "integer",
                "minimum": 3,
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"],
            },
            "next_step_required": {
                "type": "boolean",
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"],
            },
            "findings": {
                "type": "string",
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["findings"],
            },
            "files_checked": {
                "type": "array",
                "items": {"type": "string"},
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["files_checked"],
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"],
            },
            "precommit_type": {
                "type": "string",
                "enum": ["external", "internal"],
                "default": "external",
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["precommit_type"],
            },
            "issues_found": {
                "type": "array",
                "items": {"type": "object"},
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["issues_found"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["images"],
            },
            # Precommit-specific fields (for step 1)
            "path": {
                "type": "string",
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["path"],
            },
            "compare_to": {
                "type": "string",
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["compare_to"],
            },
            "include_staged": {
                "type": "boolean",
                "default": True,
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["include_staged"],
            },
            "include_unstaged": {
                "type": "boolean",
                "default": True,
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["include_unstaged"],
            },
            "focus_on": {
                "type": "string",
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["focus_on"],
            },
            "severity_filter": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low", "all"],
                "default": "all",
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["severity_filter"],
            },
        }

        # Use WorkflowSchemaBuilder with precommit-specific tool fields
        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=precommit_field_overrides,
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
            precommit_type = self.get_precommit_type(request)
            if continuation_id and precommit_type == "external":
                if step_number == 1:
                    return [
                        "Execute git status to see all changes",
                        "Execute git diff --cached for staged changes (exclude binary files)",
                        "Execute git diff for unstaged changes (exclude binary files)",
                        "List any relevant untracked files as well.",
                    ]
                else:
                    return ["Complete validation and proceed to expert analysis with changeset file"]

        # Extract counts for normal flow
        findings_count = len(findings.split("\n")) if findings else 0
        issues_count = self.get_consolidated_issues_count()

        if step_number == 1:
            # Initial pre-commit investigation tasks
            return [
                "Search for all git repositories in the specified path using appropriate tools",
                "Check git status to identify staged, unstaged, and untracked changes as required",
                "Execute git status to see all changes",
                "Execute git diff --cached for staged changes (exclude binary files)",
                "Execute git diff for unstaged changes (exclude binary files)",
                "List any relevant untracked files as well.",
                "Understand what functionality was added, modified, or removed",
                "Identify the scope and intent of the changes being committed",
                "CRITICAL: You are on step 1 - you MUST set next_step_required=True and continue to at least step 3 minimum",
            ]
        elif step_number == 2:
            # Need deeper investigation
            actions = [
                "Examine the specific files you've identified as changed or relevant",
                "Analyze the logic and implementation details of modifications",
                "Check for potential issues: bugs, security risks, performance problems",
                "Verify that changes align with good coding practices and patterns",
                "Look for missing tests, documentation, or configuration updates",
            ]

            # Add step validation reminder
            if request and request.total_steps >= 3:
                actions.append(
                    f"CRITICAL: You are on step 2 of {request.total_steps} minimum steps - you MUST set next_step_required=True unless this is the final step"
                )

            return actions
        elif step_number >= 2 and (findings_count > 2 or issues_count > 0):
            # Close to completion - need final verification
            actions = [
                "Verify all identified issues have been properly documented",
                "Check for any missed dependencies or related files that need review",
                "Confirm the completeness and correctness of your assessment",
                "Ensure all security, performance, and quality concerns are captured",
                "Validate that your findings are comprehensive and actionable",
            ]

            # Add step validation reminder
            if request and request.total_steps >= 3 and step_number < request.total_steps:
                actions.append(
                    f"CRITICAL: You are on step {step_number} of {request.total_steps} minimum steps - set next_step_required=True to continue"
                )
            elif request and request.total_steps >= 3 and step_number >= request.total_steps:
                actions.append(
                    f"You are on final step {step_number} - you may now set next_step_required=False to complete"
                )

            return actions
        else:
            # General investigation needed
            actions = [
                "Continue examining the changes and their potential impact",
                "Gather more evidence using appropriate investigation tools",
                "Test your assumptions about the changes and their effects",
                "Look for patterns that confirm or refute your current assessment",
            ]

            # Add step validation reminder for all other cases
            if request and request.total_steps >= 3:
                if step_number < request.total_steps:
                    actions.append(
                        f"CRITICAL: You are on step {step_number} of {request.total_steps} minimum steps - set next_step_required=True to continue"
                    )
                else:
                    actions.append(
                        f"You are on final step {step_number} - you may now set next_step_required=False to complete"
                    )

            return actions

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
        if continuation_id and request.precommit_type == "external":
            return True  # Always perform expert analysis for external continuations

        # Check if we have meaningful investigation data
        return (
            len(consolidated_findings.relevant_files) > 0
            or len(consolidated_findings.findings) >= 2
            or len(consolidated_findings.issues_found) > 0
        )

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Prepare context for external model call for final pre-commit validation."""
        context_parts = [
            f"=== PRE-COMMIT ANALYSIS REQUEST ===\\n{self.initial_request or 'Pre-commit validation initiated'}\\n=== END REQUEST ==="
        ]

        # Add investigation summary
        investigation_summary = self._build_precommit_summary(consolidated_findings)
        context_parts.append(
            f"\\n=== AGENT'S PRE-COMMIT INVESTIGATION ===\\n{investigation_summary}\\n=== END INVESTIGATION ==="
        )

        # Add git configuration context if available
        if self.git_config:
            config_text = "\\n".join(f"- {key}: {value}" for key, value in self.git_config.items())
            context_parts.append(f"\\n=== GIT CONFIGURATION ===\\n{config_text}\\n=== END CONFIGURATION ===")

        # Add relevant methods/functions if available
        if consolidated_findings.relevant_context:
            methods_text = "\\n".join(f"- {method}" for method in consolidated_findings.relevant_context)
            context_parts.append(f"\\n=== RELEVANT CODE ELEMENTS ===\\n{methods_text}\\n=== END CODE ELEMENTS ===")

        # Add issues found evolution if available
        if consolidated_findings.issues_found:
            issues_text = "\\n".join(
                f"[{issue.get('severity', 'unknown').upper()}] {issue.get('description', 'No description')}"
                for issue in consolidated_findings.issues_found
            )
            context_parts.append(f"\\n=== ISSUES IDENTIFIED ===\\n{issues_text}\\n=== END ISSUES ===")

        # Add assessment evolution if available
        if consolidated_findings.hypotheses:
            assessments_text = "\\n".join(
                f"Step {h['step']}: {h['hypothesis']}" for h in consolidated_findings.hypotheses
            )
            context_parts.append(f"\\n=== ASSESSMENT EVOLUTION ===\\n{assessments_text}\\n=== END ASSESSMENTS ===")

        # Add images if available
        if consolidated_findings.images:
            images_text = "\\n".join(f"- {img}" for img in consolidated_findings.images)
            context_parts.append(
                f"\\n=== VISUAL VALIDATION INFORMATION ===\\n{images_text}\\n=== END VISUAL INFORMATION ==="
            )

        return "\\n".join(context_parts)

    def _build_precommit_summary(self, consolidated_findings) -> str:
        """Prepare a comprehensive summary of the pre-commit investigation."""
        summary_parts = [
            "=== SYSTEMATIC PRE-COMMIT INVESTIGATION SUMMARY ===",
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
        """Include files in expert analysis for comprehensive validation."""
        return True

    def should_embed_system_prompt(self) -> bool:
        """Embed system prompt in expert analysis for proper context."""
        return True

    def get_expert_thinking_mode(self) -> str:
        """Use high thinking mode for thorough pre-commit analysis."""
        return "high"

    def get_expert_analysis_instruction(self) -> str:
        """Get specific instruction for pre-commit expert analysis."""
        return (
            "Please provide comprehensive pre-commit validation based on the investigation findings. "
            "Focus on identifying any remaining issues, validating the completeness of the analysis, "
            "and providing final recommendations for commit readiness."
        )

    # Hook method overrides for precommit-specific behavior

    def prepare_step_data(self, request) -> dict:
        """
        Map precommit-specific fields for internal processing.
        """
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": request.findings,
            "files_checked": request.files_checked,
            "relevant_files": request.relevant_files,
            "relevant_context": request.relevant_context,
            "issues_found": request.issues_found,
            "precommit_type": request.precommit_type,
            "hypothesis": request.findings,  # Map findings to hypothesis for compatibility
            "images": request.images or [],
            "confidence": "high",  # Dummy value for workflow_mixin compatibility
        }
        return step_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """
        Precommit workflow skips expert analysis only when precommit_type is "internal".
        Default is always to use expert analysis (external).
        For continuations with external type, always perform expert analysis immediately.
        """
        # If it's a continuation and precommit_type is external, don't skip
        continuation_id = self.get_request_continuation_id(request)
        if continuation_id and request.precommit_type != "internal":
            return False  # Always do expert analysis for external continuations

        return request.precommit_type == "internal" and not request.next_step_required

    def store_initial_issue(self, step_description: str):
        """Store initial request for expert analysis."""
        self.initial_request = step_description

    # Override inheritance hooks for precommit-specific behavior

    def get_completion_status(self) -> str:
        """Precommit tools use precommit-specific status."""
        return "validation_complete_ready_for_commit"

    def get_completion_data_key(self) -> str:
        """Precommit uses 'complete_validation' key."""
        return "complete_validation"

    def get_final_analysis_from_request(self, request):
        """Precommit tools use 'findings' field."""
        return request.findings

    def get_precommit_type(self, request) -> str:
        """Get precommit type from request. Hook method for clean inheritance."""
        try:
            return request.precommit_type or "external"
        except AttributeError:
            return "external"  # Default to external validation

    def get_consolidated_issues_count(self) -> int:
        """Get count of issues from consolidated findings. Hook method for clean access."""
        try:
            return len(self.consolidated_findings.issues_found)
        except AttributeError:
            return 0

    def get_completion_message(self) -> str:
        """Precommit-specific completion message."""
        return (
            "Pre-commit validation complete. You have identified all issues "
            "and verified commit readiness. MANDATORY: Present the user with the complete validation results "
            "and IMMEDIATELY proceed with commit if no critical issues found, or provide specific fix guidance "
            "if issues need resolution. Focus on actionable next steps."
        )

    def get_skip_reason(self) -> str:
        """Precommit-specific skip reason."""
        return (
            "Completed comprehensive pre-commit validation with internal analysis only (no external model validation)"
        )

    def get_skip_expert_analysis_status(self) -> str:
        """Precommit-specific expert analysis skip status."""
        return "skipped_due_to_internal_analysis_type"

    def prepare_work_summary(self) -> str:
        """Precommit-specific work summary."""
        return self._build_precommit_summary(self.consolidated_findings)

    def get_completion_next_steps_message(self, expert_analysis_used: bool = False) -> str:
        """
        Precommit-specific completion message.

        Args:
            expert_analysis_used: True if expert analysis was successfully executed
        """
        base_message = (
            "PRE-COMMIT VALIDATION IS COMPLETE. You may delete any `zen_precommit.changeset` created. You MUST now summarize "
            "and present ALL validation results, identified issues with their severity levels, and exact commit recommendations. "
            "Clearly state whether the changes are ready for commit or require fixes first. Provide concrete, actionable guidance for "
            "any issues that need resolution—make it easy for a developer to understand exactly what needs to be "
            "done before committing."
        )

        # Add expert analysis guidance only when expert analysis was actually used
        if expert_analysis_used:
            expert_guidance = self.get_expert_analysis_guidance()
            if expert_guidance:
                return f"{base_message}\n\n{expert_guidance}"

        return base_message

    def get_expert_analysis_guidance(self) -> str:
        """
        Get additional guidance for handling expert analysis results in pre-commit context.

        Returns:
            Additional guidance text for validating and using expert analysis findings
        """
        return (
            "IMPORTANT: Expert analysis has been provided above. You MUST carefully review "
            "the expert's validation findings and security assessments. Cross-reference the "
            "expert's analysis with your own investigation to ensure all critical issues are "
            "addressed. Pay special attention to any security vulnerabilities, performance "
            "concerns, or architectural issues identified by the expert review."
        )

    def get_step_guidance_message(self, request) -> str:
        """
        Precommit-specific step guidance with detailed investigation instructions.
        """
        step_guidance = self.get_precommit_step_guidance(request.step_number, request)
        return step_guidance["next_steps"]

    def get_precommit_step_guidance(self, step_number: int, request) -> dict[str, Any]:
        """
        Provide step-specific guidance for precommit workflow.
        Uses get_required_actions to determine what needs to be done,
        then formats those actions into appropriate guidance messages.
        """
        # Get the required actions from the single source of truth
        required_actions = self.get_required_actions(
            step_number,
            request.precommit_type or "external",  # Using precommit_type as confidence proxy
            request.findings or "",
            request.total_steps,
            request,  # Pass request for continuation-aware decisions
        )

        # Check if this is a continuation to provide context-aware guidance
        continuation_id = self.get_request_continuation_id(request)
        is_external_continuation = continuation_id and request.precommit_type == "external"
        is_internal_continuation = continuation_id and request.precommit_type == "internal"

        # Format the guidance based on step number and continuation status
        if step_number == 1:
            if is_external_continuation:
                # Fast-track mode for external continuations
                next_steps = (
                    "You are on step 1 of MAXIMUM 2 steps. CRITICAL: Gather and save the complete git changeset NOW. "
                    "MANDATORY ACTIONS:\\n"
                    + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                    + "\\n\\nMANDATORY: The changeset may be large. You MUST save the required changeset as a 'zen_precommit.changeset' file "
                    "(replacing any existing one) in your work directory and include the FULL absolute path in relevant_files (exclude any "
                    "binary files). ONLY include the code changes, no extra commentary."
                    "Set next_step_required=True and step_number=2 for the next call."
                )
            elif is_internal_continuation:
                # Internal validation mode
                next_steps = (
                    "Continuing previous conversation with internal validation only. The analysis will build "
                    "upon the prior findings without external model validation. REQUIRED ACTIONS:\\n"
                    + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                )
            else:
                # Normal flow for new validations
                next_steps = (
                    f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. You MUST first investigate "
                    f"the git repositories and changes using appropriate tools. CRITICAL AWARENESS: You need to:\\n"
                    + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                    + f"\\n\\nOnly call {self.get_name()} again AFTER completing your investigation. "
                    f"When you call {self.get_name()} next time, use step_number: {step_number + 1} "
                    f"and report specific files examined, changes analyzed, and validation findings discovered."
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
            elif is_external_continuation or (not request.next_step_required and request.precommit_type == "external"):
                # Fast-track completion or about to complete - ensure changeset is saved
                next_steps = (
                    "Proceeding immediately to expert analysis. "
                    f"MANDATORY: call {self.get_name()} tool immediately again, and set next_step_required=False to "
                    f"trigger external validation NOW. "
                    f"MANDATORY: Include the entire changeset! The changeset may be large. You MUST save the required "
                    f"changeset as a 'zen_precommit.changeset' file (replacing any existing one) in your work directory "
                    f"and include the FULL absolute path in relevant_files so the expert can access the complete changeset. "
                    f"ONLY include the code changes, no extra commentary."
                )
            else:
                # Normal flow - deeper analysis needed
                next_steps = (
                    f"STOP! Do NOT call {self.get_name()} again yet. You are on step 2 of {request.total_steps} minimum required steps. "
                    f"MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\\n"
                    + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                    + f"\\n\\nRemember: You MUST set next_step_required=True until step {request.total_steps}. "
                    + f"Only call {self.get_name()} again with step_number: {step_number + 1} AFTER completing these validations."
                )

        elif step_number >= 3:
            if not request.next_step_required and request.precommit_type == "external":
                # About to complete - ensure changeset is saved
                next_steps = (
                    "Completing validation and proceeding to expert analysis. "
                    "MANDATORY: Save the complete git changeset as a 'zen_precommit.changeset' file "
                    "in your work directory and include the FULL absolute path in relevant_files."
                )
            else:
                # Later steps - final verification
                next_steps = (
                    f"WAIT! Your validation needs final verification. DO NOT call {self.get_name()} immediately. REQUIRED ACTIONS:\\n"
                    + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                    + f"\\n\\nREMEMBER: Ensure you have identified all potential issues and verified commit readiness. "
                    f"Document findings with specific file references and issue descriptions, then call {self.get_name()} "
                    f"with step_number: {step_number + 1}."
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
            elif not request.next_step_required and request.precommit_type == "external":
                next_steps = (
                    "Completing validation. "
                    "MANDATORY: Save complete git changeset as 'zen_precommit.changeset' file and include path in relevant_files, "
                    "excluding any binary files."
                )
            else:
                next_steps = (
                    f"PAUSE VALIDATION. Before calling {self.get_name()} step {step_number + 1}, you MUST examine more code and changes. "
                    + "Required: "
                    + ", ".join(required_actions[:2])
                    + ". "
                    + f"Your next {self.get_name()} call (step_number: {step_number + 1}) must include "
                    f"NEW evidence from actual change analysis, not just theories. NO recursive {self.get_name()} calls "
                    f"without investigation work!"
                )

        return {"next_steps": next_steps}

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """
        Customize response to match precommit workflow format.
        """
        # Store initial request on first step
        if request.step_number == 1:
            self.initial_request = request.step
            # Store git configuration for expert analysis
            if request.path:
                self.git_config = {
                    "path": request.path,
                    "compare_to": request.compare_to,
                    "include_staged": request.include_staged,
                    "include_unstaged": request.include_unstaged,
                    "severity_filter": request.severity_filter,
                }

        # Convert generic status names to precommit-specific ones
        tool_name = self.get_name()
        status_mapping = {
            f"{tool_name}_in_progress": "validation_in_progress",
            f"pause_for_{tool_name}": "pause_for_validation",
            f"{tool_name}_required": "validation_required",
            f"{tool_name}_complete": "validation_complete",
        }

        if response_data["status"] in status_mapping:
            response_data["status"] = status_mapping[response_data["status"]]

        # Rename status field to match precommit workflow
        if f"{tool_name}_status" in response_data:
            response_data["validation_status"] = response_data.pop(f"{tool_name}_status")
            # Add precommit-specific status fields
            response_data["validation_status"]["issues_identified"] = len(self.consolidated_findings.issues_found)
            response_data["validation_status"]["precommit_type"] = request.precommit_type or "external"

        # Map complete_precommitworkflow to complete_validation
        if f"complete_{tool_name}" in response_data:
            response_data["complete_validation"] = response_data.pop(f"complete_{tool_name}")

        # Map the completion flag to match precommit workflow
        if f"{tool_name}_complete" in response_data:
            response_data["validation_complete"] = response_data.pop(f"{tool_name}_complete")

        return response_data

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the precommit workflow-specific request model."""
        return PrecommitRequest

    async def prepare_prompt(self, request) -> str:
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
