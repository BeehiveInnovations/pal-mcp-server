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
        "Describe what you're currently investigating for code review by thinking deeply about the code structure, "
        "patterns, and potential issues. In step 1, clearly state your review plan and begin forming a systematic "
        "approach after thinking carefully about what needs to be analyzed. You must begin by passing the file path "
        "for the initial code you are about to review in relevant_files. CRITICAL: Remember to thoroughly examine "
        "code quality, security implications, performance concerns, and architectural patterns. Consider not only "
        "obvious bugs and issues but also subtle concerns like over-engineering, unnecessary complexity, design "
        "patterns that could be simplified, areas where architecture might not scale well, missing abstractions, "
        "and ways to reduce complexity while maintaining functionality. Map out the codebase structure, understand "
        "the business logic, and identify areas requiring deeper analysis. In all later steps, continue exploring "
        "with precision: trace dependencies, verify assumptions, and adapt your understanding as you uncover more evidence."
    ),
    "step_number": (
        "The index of the current step in the code review sequence, beginning at 1. Each step should build upon or "
        "revise the previous one."
    ),
    "total_steps": (
        "Your current estimate for how many steps will be needed to complete the code review. "
        "Adjust as new findings emerge."
    ),
    "next_step_required": (
        "Set to true if you plan to continue the investigation with another step. False means you believe the "
        "code review analysis is complete and ready for expert validation."
    ),
    "findings": (
        "Summarize everything discovered in this step about the code being reviewed. Include analysis of code quality, "
        "security concerns, performance issues, architectural patterns, design decisions, potential bugs, code smells, "
        "and maintainability considerations. Be specific and avoid vague language—document what you now know about "
        "the code and how it affects your assessment. IMPORTANT: Document both positive findings (good patterns, "
        "proper implementations, well-designed components) and concerns (potential issues, anti-patterns, security "
        "risks, performance bottlenecks). In later steps, confirm or update past findings with additional evidence."
    ),
    "files_checked": (
        "List all files (as absolute paths, do not clip or shrink file names) examined during the code review "
        "investigation so far. Include even files ruled out or found to be unrelated, as this tracks your "
        "exploration path."
    ),
    "relevant_files": (
        "For when this is the first step, please pass absolute file paths of relevant code to review (do not clip "
        "file paths). When used for the final step, this contains a subset of files_checked (as full absolute paths) "
        "that contain code directly relevant to the review or contain significant issues, patterns, or examples worth "
        "highlighting. Only list those that are directly tied to important findings, security concerns, performance "
        "issues, or architectural decisions. This could include core implementation files, configuration files, or "
        "files with notable patterns."
    ),
    "relevant_context": (
        "List methods, functions, classes, or modules that are central to the code review findings, in the format "
        "'ClassName.methodName', 'functionName', or 'module.ClassName'. Prioritize those that contain issues, "
        "demonstrate patterns, show security concerns, or represent key architectural decisions."
    ),
    "issues_found": (
        "List of issues identified during the investigation. Each issue should be a dictionary with 'severity' "
        "(critical, high, medium, low) and 'description' fields. Include security vulnerabilities, performance "
        "bottlenecks, code quality issues, architectural concerns, maintainability problems, over-engineering, "
        "unnecessary complexity, etc."
    ),
    "confidence": (
        "Indicate your current confidence in the code review assessment. Use: 'exploring' (starting analysis), 'low' "
        "(early investigation), 'medium' (some evidence gathered), 'high' (strong evidence), "
        "'very_high' (very strong evidence), 'almost_certain' (nearly complete review), 'certain' (100% confidence - "
        "code review is thoroughly complete and all significant issues are identified with no need for external model validation). "
        "Do NOT use 'certain' unless the code review is comprehensively complete, use 'very_high' or 'almost_certain' instead if not 100% sure. "
        "Using 'certain' means you have complete confidence locally and prevents external model validation."
    ),
    "backtrack_from_step": (
        "If an earlier finding or assessment needs to be revised or discarded, specify the step number from which to "
        "start over. Use this to acknowledge investigative dead ends and correct the course."
    ),
    "images": (
        "Optional list of absolute paths to architecture diagrams, UI mockups, design documents, or visual references "
        "that help with code review context. Only include if they materially assist understanding or assessment."
    ),
    "review_type": "Type of review to perform (full, security, performance, quick)",
    "focus_on": "Specific aspects to focus on or additional context that would help understand areas of concern",
    "standards": "Coding standards to enforce during the review",
    "severity_filter": "Minimum severity level to report on the issues found",
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
    confidence: Optional[str] = Field("low", description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["confidence"])

    # Optional backtracking field
    backtrack_from_step: Optional[int] = Field(
        None, description=CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["backtrack_from_step"]
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
    use_websearch: Optional[bool] = Field(default=None, exclude=True)

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
            "COMPREHENSIVE CODE REVIEW WORKFLOW - Step-by-step code review with expert analysis. "
            "This tool guides you through a systematic investigation process where you:\n\n"
            "1. Start with step 1: describe your code review investigation plan\n"
            "2. STOP and investigate code structure, patterns, and potential issues\n"
            "3. Report findings in step 2 with concrete evidence from actual code analysis\n"
            "4. Continue investigating between each step\n"
            "5. Track findings, relevant files, and issues throughout\n"
            "6. Update assessments as understanding evolves\n"
            "7. Once investigation is complete, receive expert analysis\n\n"
            "IMPORTANT: This tool enforces investigation between steps:\n"
            "- After each call, you MUST investigate before calling again\n"
            "- Each step must include NEW evidence from code examination\n"
            "- No recursive calls without actual investigation work\n"
            "- The tool will specify which step number to use next\n"
            "- Follow the required_actions list for investigation guidance\n\n"
            "Perfect for: comprehensive code review, security audits, performance analysis, "
            "architectural assessment, code quality evaluation, anti-pattern detection."
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
            "confidence": {
                "type": "string",
                "enum": ["exploring", "low", "medium", "high", "very_high", "almost_certain", "certain"],
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["confidence"],
            },
            "backtrack_from_step": {
                "type": "integer",
                "minimum": 1,
                "description": CODEREVIEW_WORKFLOW_FIELD_DESCRIPTIONS["backtrack_from_step"],
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

    def get_required_actions(self, step_number: int, confidence: str, findings: str, total_steps: int) -> list[str]:
        """Define required actions for each investigation phase."""
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
        elif confidence in ["exploring", "low"]:
            # Need deeper investigation
            return [
                "Examine specific code sections you've identified as concerning",
                "Analyze security implications: input validation, authentication, authorization",
                "Check for performance issues: algorithmic complexity, resource usage, inefficiencies",
                "Look for architectural problems: tight coupling, missing abstractions, scalability issues",
                "Identify code quality issues: readability, maintainability, error handling",
                "Search for over-engineering, unnecessary complexity, or design patterns that could be simplified",
            ]
        elif confidence in ["medium", "high"]:
            # Close to completion - need final verification
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
            "confidence": request.confidence,
            "hypothesis": request.findings,  # Map findings to hypothesis for compatibility
            "images": request.images or [],
        }
        return step_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """
        Code review workflow skips expert analysis when the CLI agent has "certain" confidence.
        """
        return request.confidence == "certain" and not request.next_step_required

    def store_initial_issue(self, step_description: str):
        """Store initial request for expert analysis."""
        self.initial_request = step_description

    # Override inheritance hooks for code review-specific behavior

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
            "Code review complete with CERTAIN confidence. You have identified all significant issues "
            "and provided comprehensive analysis. MANDATORY: Present the user with the complete review results "
            "categorized by severity, and IMMEDIATELY proceed with implementing the highest priority fixes "
            "or provide specific guidance for improvements. Focus on actionable recommendations."
        )

    def get_skip_reason(self) -> str:
        """Code review-specific skip reason."""
        return "Completed comprehensive code review with full confidence locally"

    def get_skip_expert_analysis_status(self) -> str:
        """Code review-specific expert analysis skip status."""
        return "skipped_due_to_certain_review_confidence"

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
        step_guidance = self.get_code_review_step_guidance(request.step_number, request.confidence, request)
        return step_guidance["next_steps"]

    def get_code_review_step_guidance(self, step_number: int, confidence: str, request) -> dict[str, Any]:
        """
        Provide step-specific guidance for code review workflow.
        """
        # Generate the next steps instruction based on required actions
        required_actions = self.get_required_actions(step_number, confidence, request.findings, request.total_steps)

        if step_number == 1:
            next_steps = (
                f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. You MUST first examine "
                f"the code files thoroughly using appropriate tools. CRITICAL AWARENESS: You need to understand "
                f"the code structure, identify potential issues across security, performance, and quality dimensions, "
                f"and look for architectural concerns, over-engineering, unnecessary complexity, and scalability issues. "
                f"Use file reading tools, code analysis, and systematic examination to gather comprehensive information. "
                f"Only call {self.get_name()} again AFTER completing your investigation. When you call "
                f"{self.get_name()} next time, use step_number: {step_number + 1} and report specific "
                f"files examined, issues found, and code quality assessments discovered."
            )
        elif confidence in ["exploring", "low"]:
            next_steps = (
                f"STOP! Do NOT call {self.get_name()} again yet. Based on your findings, you've identified areas that need "
                f"deeper analysis. MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\\n"
                + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\\n\\nOnly call {self.get_name()} again with step_number: {step_number + 1} AFTER "
                + "completing these code review tasks."
            )
        elif confidence in ["medium", "high"]:
            next_steps = (
                f"WAIT! Your code review needs final verification. DO NOT call {self.get_name()} immediately. REQUIRED ACTIONS:\\n"
                + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\\n\\nREMEMBER: Ensure you have identified all significant issues across all severity levels and "
                f"verified the completeness of your review. Document findings with specific file references and "
                f"line numbers where applicable, then call {self.get_name()} with step_number: {step_number + 1}."
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
            response_data["code_review_status"]["review_confidence"] = self.get_request_confidence(request)

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
