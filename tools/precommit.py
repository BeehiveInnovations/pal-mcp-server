"""
Precommit Workflow tool - Step-by-step pre-commit validation with expert analysis

This tool provides a structured workflow for comprehensive pre-commit validation.
It guides the CLI agent through systematic investigation steps with forced pauses between each step
to ensure thorough code examination, git change analysis, and issue detection before proceeding.
The tool supports backtracking, finding updates, and expert analysis integration.

Key features:
- Step-by-step pre-commit investigation workflow with progress tracking
- Context-aware file embedding (references during investigation, full content for analysis)
- Automatic git repository discovery and change analysis
- Expert analysis integration with external models
- Support for multiple repositories and change types
- Confidence-based workflow optimization
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
        "Describe what you're currently investigating for pre-commit validation by thinking deeply about the changes "
        "and their potential impact. In step 1, clearly state your investigation plan and begin forming a systematic "
        "approach after thinking carefully about what needs to be validated. CRITICAL: Remember to thoroughly examine "
        "all git repositories, staged/unstaged changes, and understand the scope and intent of modifications. "
        "Consider not only immediate correctness but also potential future consequences, security implications, "
        "performance impacts, and maintainability concerns. Map out changed files, understand the business logic, "
        "and identify areas requiring deeper analysis. In all later steps, continue exploring with precision: "
        "trace dependencies, verify hypotheses, and adapt your understanding as you uncover more evidence."
        "IMPORTANT: When referring to code, use the relevant_files parameter to pass relevant files and only use the prompt to refer to "
        "function / method names or very small code snippets if absolutely necessary to explain the issue. Do NOT "
        "pass large code snippets in the prompt as this is exclusively reserved for descriptive text only. "
    ),
    "step_number": (
        "The index of the current step in the pre-commit investigation sequence, beginning at 1. Each step should "
        "build upon or revise the previous one."
    ),
    "total_steps": (
        "Your current estimate for how many steps will be needed to complete the pre-commit investigation. "
        "Adjust as new findings emerge. IMPORTANT: When continuation_id is provided (continuing a previous "
        "conversation), set this to 1 as we're not starting a new multi-step investigation."
    ),
    "next_step_required": (
        "Set to true if you plan to continue the investigation with another step. False means you believe the "
        "pre-commit analysis is complete and ready for expert validation. IMPORTANT: When continuation_id is "
        "provided (continuing a previous conversation), set this to False to immediately proceed with expert analysis."
    ),
    "findings": (
        "Summarize everything discovered in this step about the changes being committed. Include analysis of git diffs, "
        "file modifications, new functionality, potential issues identified, code quality observations, and security "
        "considerations. Be specific and avoid vague language—document what you now know about the changes and how "
        "they affect your assessment. IMPORTANT: Document both positive findings (good patterns, proper implementations) "
        "and concerns (potential bugs, missing tests, security risks). In later steps, confirm or update past findings "
        "with additional evidence."
    ),
    "files_checked": (
        "List all files (as absolute paths, do not clip or shrink file names) examined during the pre-commit "
        "investigation so far. Include even files ruled out or found to be unchanged, as this tracks your "
        "exploration path."
    ),
    "relevant_files": (
        "Subset of files_checked (as full absolute paths) that contain changes or are directly relevant to the "
        "commit validation. Only list those that are directly tied to the changes being committed, their dependencies, "
        "or files that need validation. This could include modified files, related configuration, tests, or "
        "documentation."
    ),
    "relevant_context": (
        "List methods, functions, classes, or modules that are central to the changes being committed, in the format "
        "'ClassName.methodName', 'functionName', or 'module.ClassName'. Prioritize those that are modified, added, "
        "or significantly affected by the changes."
    ),
    "issues_found": (
        "List of issues identified during the investigation. Each issue should be a dictionary with 'severity' "
        "(critical, high, medium, low) and 'description' fields. Include potential bugs, security concerns, "
        "performance issues, missing tests, incomplete implementations, etc."
    ),
    "confidence": (
        "Indicate your current confidence in the assessment. Use: 'exploring' (starting analysis), 'low' (early "
        "investigation), 'medium' (some evidence gathered), 'high' (strong evidence), "
        "'very_high' (very strong evidence), 'almost_certain' (nearly complete validation), 'certain' (200% confidence - "
        "analysis is complete and all issues are identified with no need for external model validation). "
        "Do NOT use 'certain' unless the pre-commit validation is thoroughly complete, use 'very_high' or 'almost_certain' "
        "instead if not 200% sure. "
        "Using 'certain' means you have complete confidence locally and prevents external model validation. Also "
        "do NOT set confidence to 'certain' if the user has strongly requested that external validation MUST be performed."
    ),
    "backtrack_from_step": (
        "If an earlier finding or assessment needs to be revised or discarded, specify the step number from which to "
        "start over. Use this to acknowledge investigative dead ends and correct the course."
    ),
    "images": (
        "Optional list of absolute paths to screenshots, UI mockups, or visual references that help validate the "
        "changes. Only include if they materially assist understanding or assessment of the commit."
    ),
    "path": (
        "Starting absolute path to the directory to search for git repositories (must be FULL absolute paths - "
        "DO NOT SHORTEN)."
    ),
    "compare_to": (
        "Optional: A git ref (branch, tag, commit hash) to compare against. Check remote branches if local does not exist."
        "If not provided, investigates local staged and unstaged changes."
    ),
    "include_staged": "Include staged changes in the investigation. Only applies if 'compare_to' is not set.",
    "include_unstaged": "Include uncommitted (unstaged) changes in the investigation. Only applies if 'compare_to' is not set.",
    "focus_on": "Specific aspects to focus on (e.g., 'security implications', 'performance impact', 'test coverage').",
    "severity_filter": "Minimum severity level to report on the changes.",
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
    confidence: Optional[str] = Field("low", description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["confidence"])

    # Optional backtracking field
    backtrack_from_step: Optional[int] = Field(
        None, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["backtrack_from_step"]
    )

    # Optional images for visual validation
    images: Optional[list[str]] = Field(default=None, description=PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["images"])

    # Precommit-specific fields (only used in step 1 to initialize)
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
    use_websearch: Optional[bool] = Field(default=None, exclude=True)

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
            "COMPREHENSIVE PRECOMMIT WORKFLOW - Step-by-step pre-commit validation with expert analysis. "
            "This tool guides you through a systematic investigation process where you:\n\n"
            "1. Start with step 1: describe your pre-commit validation plan\n"
            "2. STOP and investigate git changes, repository status, and file modifications\n"
            "3. Report findings in step 2 with concrete evidence from actual changes\n"
            "4. Continue investigating between each step\n"
            "5. Track findings, relevant files, and issues throughout\n"
            "6. Update assessments as understanding evolves\n"
            "7. Once investigation is complete, receive expert analysis\n\n"
            "IMPORTANT: This tool enforces investigation between steps:\n"
            "- After each call, you MUST investigate before calling again\n"
            "- Each step must include NEW evidence from git analysis\n"
            "- No recursive calls without actual investigation work\n"
            "- The tool will specify which step number to use next\n"
            "- Follow the required_actions list for investigation guidance\n\n"
            "Perfect for: comprehensive pre-commit validation, multi-repository analysis, "
            "security review, change impact assessment, completeness verification."
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
                "minimum": 1,
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
            "confidence": {
                "type": "string",
                "enum": ["exploring", "low", "medium", "high", "very_high", "almost_certain", "certain"],
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["confidence"],
            },
            "backtrack_from_step": {
                "type": "integer",
                "minimum": 1,
                "description": PRECOMMIT_WORKFLOW_FIELD_DESCRIPTIONS["backtrack_from_step"],
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

    def get_required_actions(self, step_number: int, confidence: str, findings: str, total_steps: int) -> list[str]:
        """Define required actions for each investigation phase."""
        if step_number == 1:
            # Initial pre-commit investigation tasks
            return [
                "Search for all git repositories in the specified path using appropriate tools",
                "Check git status to identify staged, unstaged, and untracked changes as required",
                "Examine the actual file changes using git diff or file reading tools",
                "Understand what functionality was added, modified, or removed",
                "Identify the scope and intent of the changes being committed",
            ]
        elif confidence in ["exploring", "low"]:
            # Need deeper investigation
            return [
                "Examine the specific files you've identified as changed or relevant",
                "Analyze the logic and implementation details of modifications",
                "Check for potential issues: bugs, security risks, performance problems",
                "Verify that changes align with good coding practices and patterns",
                "Look for missing tests, documentation, or configuration updates",
            ]
        elif confidence in ["medium", "high"]:
            # Close to completion - need final verification
            return [
                "Verify all identified issues have been properly documented",
                "Check for any missed dependencies or related files that need review",
                "Confirm the completeness and correctness of your assessment",
                "Ensure all security, performance, and quality concerns are captured",
                "Validate that your findings are comprehensive and actionable",
            ]
        else:
            # General investigation needed
            return [
                "Continue examining the changes and their potential impact",
                "Gather more evidence using appropriate investigation tools",
                "Test your assumptions about the changes and their effects",
                "Look for patterns that confirm or refute your current assessment",
            ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """
        Decide when to call external model based on investigation completeness.

        Don't call expert analysis if the CLI agent has certain confidence - trust their judgment.
        """
        # Check if user requested to skip assistant model
        if request and not self.get_request_use_assistant_model(request):
            return False

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
                f"Step {h['step']} ({h['confidence']} confidence): {h['hypothesis']}"
                for h in consolidated_findings.hypotheses
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
            "confidence": request.confidence,
            "hypothesis": request.findings,  # Map findings to hypothesis for compatibility
            "images": request.images or [],
        }
        return step_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """
        Precommit workflow skips expert analysis when the CLI agent has "certain" confidence.
        """
        return request.confidence == "certain" and not request.next_step_required

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

    def get_confidence_level(self, request) -> str:
        """Precommit tools use 'certain' for high confidence."""
        return "certain"

    def get_completion_message(self) -> str:
        """Precommit-specific completion message."""
        return (
            "Pre-commit validation complete with CERTAIN confidence. You have identified all issues "
            "and verified commit readiness. MANDATORY: Present the user with the complete validation results "
            "and IMMEDIATELY proceed with commit if no critical issues found, or provide specific fix guidance "
            "if issues need resolution. Focus on actionable next steps."
        )

    def get_skip_reason(self) -> str:
        """Precommit-specific skip reason."""
        return "Completed comprehensive pre-commit validation with full confidence locally"

    def get_skip_expert_analysis_status(self) -> str:
        """Precommit-specific expert analysis skip status."""
        return "skipped_due_to_certain_validation_confidence"

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
            "PRE-COMMIT VALIDATION IS COMPLETE. You MUST now summarize and present ALL validation results, "
            "identified issues with their severity levels, and exact commit recommendations. Clearly state whether "
            "the changes are ready for commit or require fixes first. Provide concrete, actionable guidance for "
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
        step_guidance = self.get_precommit_step_guidance(request.step_number, request.confidence, request)
        return step_guidance["next_steps"]

    def get_precommit_step_guidance(self, step_number: int, confidence: str, request) -> dict[str, Any]:
        """
        Provide step-specific guidance for precommit workflow.
        """
        # Check if this is a continuation - if so, skip workflow and go to expert analysis
        continuation_id = self.get_request_continuation_id(request)
        if continuation_id:
            return {
                "next_steps": (
                    "Continuing previous conversation. The expert analysis will now be performed based on the "
                    "accumulated context from the previous conversation. The analysis will build upon the prior "
                    "findings without repeating the investigation steps."
                )
            }

        # Generate the next steps instruction based on required actions
        required_actions = self.get_required_actions(step_number, confidence, request.findings, request.total_steps)

        if step_number == 1:
            next_steps = (
                f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. You MUST first investigate "
                f"the git repositories and changes using appropriate tools. CRITICAL AWARENESS: You need to discover "
                f"all git repositories, examine staged/unstaged changes, understand what's being committed, and identify "
                f"potential issues before proceeding. Use git status, git diff, file reading tools, and code analysis "
                f"to gather comprehensive information. Only call {self.get_name()} again AFTER completing your investigation. "
                f"When you call {self.get_name()} next time, use step_number: {step_number + 1} and report specific "
                f"files examined, changes analyzed, and validation findings discovered."
            )
        elif confidence in ["exploring", "low"]:
            next_steps = (
                f"STOP! Do NOT call {self.get_name()} again yet. Based on your findings, you've identified areas that need "
                f"deeper analysis. MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\\n"
                + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\\n\\nOnly call {self.get_name()} again with step_number: {step_number + 1} AFTER "
                + "completing these validations."
            )
        elif confidence in ["medium", "high"]:
            next_steps = (
                f"WAIT! Your validation needs final verification. DO NOT call {self.get_name()} immediately. REQUIRED ACTIONS:\\n"
                + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\\n\\nREMEMBER: Ensure you have identified all potential issues and verified commit readiness. "
                f"Document findings with specific file references and issue descriptions, then call {self.get_name()} "
                f"with step_number: {step_number + 1}."
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
            response_data["validation_status"]["assessment_confidence"] = self.get_request_confidence(request)

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
