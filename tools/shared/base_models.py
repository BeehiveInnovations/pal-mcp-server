"""
Base models for Zen MCP tools.

This module contains the shared Pydantic models used across all tools,
extracted to avoid circular imports and promote code reuse.

Key Models:
- ToolRequest: Base request model for all tools
- WorkflowRequest: Extended request model for workflow-based tools
- ConsolidatedFindings: Model for tracking workflow progress
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# Shared field descriptions to avoid duplication
COMMON_FIELD_DESCRIPTIONS = {
    "model": (
        "Model to use. See tool's input schema for available models and their capabilities. "
        "Use 'auto' to let Claude select the best model for the task."
    ),
    "temperature": (
        "Temperature for response (0.0 to 1.0). Lower values are more focused and deterministic, "
        "higher values are more creative. Tool-specific defaults apply if not specified."
    ),
    "thinking_mode": (
        "Thinking depth: minimal (0.5% of model max), low (8%), medium (33%), high (67%), "
        "max (100% of model max). Higher modes enable deeper reasoning at the cost of speed."
    ),
    "use_websearch": (
        "Enable web search for documentation, best practices, and current information. "
        "When enabled, the model can request Claude to perform web searches and share results back "
        "during conversations. Particularly useful for: brainstorming sessions, architectural design "
        "discussions, exploring industry best practices, working with specific frameworks/technologies, "
        "researching solutions to complex problems, or when current documentation and community insights "
        "would enhance the analysis."
    ),
    "continuation_id": (
        "Thread continuation ID for multi-turn conversations. When provided, the complete conversation "
        "history is automatically embedded as context. Your response should build upon this history "
        "without repeating previous analysis or instructions. Focus on providing only new insights, "
        "additional findings, or answers to follow-up questions. Can be used across different tools."
    ),
    "images": (
        "Optional image(s) for visual context. Accepts absolute file paths or "
        "base64 data URLs. Only provide when user explicitly mentions images. "
        "When including images, please describe what you believe each image contains "
        "to aid with contextual understanding. Useful for UI discussions, diagrams, "
        "visual problems, error screens, architecture mockups, and visual analysis tasks."
    ),
    "files": ("Optional files for context (must be FULL absolute paths to real files / folders - DO NOT SHORTEN)"),
}

# Workflow-specific field descriptions
WORKFLOW_FIELD_DESCRIPTIONS = {
    "step": "Current work step content and findings from your overall work",
    "step_number": "Current step number in the work sequence (starts at 1)",
    "total_steps": "Estimated total steps needed to complete the work",
    "next_step_required": "Whether another work step is needed after this one",
    "findings": "Important findings, evidence and insights discovered in this step of the work",
    "files_checked": "List of files examined during this work step",
    "relevant_files": "Files identified as relevant to the issue/goal",
    "relevant_context": "Methods/functions identified as involved in the issue",
    "issues_found": "Issues identified with severity levels during work",
    "confidence": (
        "Confidence level in findings: exploring (just starting), low (early investigation), "
        "medium (some evidence), high (strong evidence), very_high (comprehensive understanding), "
        "almost_certain (near complete confidence), certain (100% confidence locally - no external validation needed)"
    ),
    "hypothesis": "Current theory about the issue/goal based on work",
    "backtrack_from_step": "Step number to backtrack from if work needs revision",
    "use_assistant_model": (
        "Whether to use assistant model for expert analysis after completing the workflow steps. "
        "Set to False to skip expert analysis and rely solely on Claude's investigation. "
        "Defaults to True for comprehensive validation."
    ),
}


class ToolRequest(BaseModel):
    """
    Base request model for all Zen MCP tools.

    This model defines common fields that all tools accept, including
    model selection, temperature control, and conversation threading.
    Tool-specific request models should inherit from this class.
    """

    # Model configuration
    model: Optional[str] = Field(None, description=COMMON_FIELD_DESCRIPTIONS["model"])
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0, description=COMMON_FIELD_DESCRIPTIONS["temperature"])
    thinking_mode: Optional[str] = Field(None, description=COMMON_FIELD_DESCRIPTIONS["thinking_mode"])

    # Features
    use_websearch: Optional[bool] = Field(True, description=COMMON_FIELD_DESCRIPTIONS["use_websearch"])

    # Conversation support
    continuation_id: Optional[str] = Field(None, description=COMMON_FIELD_DESCRIPTIONS["continuation_id"])

    # Visual context
    images: Optional[list[str]] = Field(None, description=COMMON_FIELD_DESCRIPTIONS["images"])


class BaseWorkflowRequest(ToolRequest):
    """
    Minimal base request model for workflow tools.

    This provides only the essential fields that ALL workflow tools need,
    allowing for maximum flexibility in tool-specific implementations.
    """

    # Core workflow fields that ALL workflow tools need
    step: str = Field(..., description=WORKFLOW_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., ge=1, description=WORKFLOW_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., ge=1, description=WORKFLOW_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"])


class WorkflowRequest(BaseWorkflowRequest):
    """
    Extended request model for workflow-based tools.

    This model extends ToolRequest with fields specific to the workflow
    pattern, where tools perform multi-step work with forced pauses between steps.

    Used by: debug, precommit, codereview, refactor, thinkdeep, analyze
    """

    # Required workflow fields
    step: str = Field(..., description=WORKFLOW_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., ge=1, description=WORKFLOW_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., ge=1, description=WORKFLOW_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"])

    # Work tracking fields
    findings: str = Field(..., description=WORKFLOW_FIELD_DESCRIPTIONS["findings"])
    files_checked: list[str] = Field(default_factory=list, description=WORKFLOW_FIELD_DESCRIPTIONS["files_checked"])
    relevant_files: list[str] = Field(default_factory=list, description=WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"])
    relevant_context: list[str] = Field(
        default_factory=list, description=WORKFLOW_FIELD_DESCRIPTIONS["relevant_context"]
    )
    issues_found: list[dict] = Field(default_factory=list, description=WORKFLOW_FIELD_DESCRIPTIONS["issues_found"])
    confidence: str = Field("low", description=WORKFLOW_FIELD_DESCRIPTIONS["confidence"])

    # Optional workflow fields
    hypothesis: Optional[str] = Field(None, description=WORKFLOW_FIELD_DESCRIPTIONS["hypothesis"])
    backtrack_from_step: Optional[int] = Field(
        None, ge=1, description=WORKFLOW_FIELD_DESCRIPTIONS["backtrack_from_step"]
    )
    use_assistant_model: Optional[bool] = Field(True, description=WORKFLOW_FIELD_DESCRIPTIONS["use_assistant_model"])

    @field_validator("files_checked", "relevant_files", "relevant_context", mode="before")
    @classmethod
    def convert_string_to_list(cls, v):
        """Convert string inputs to empty lists to handle malformed inputs gracefully."""
        if isinstance(v, str):
            logger.warning(f"Field received string '{v}' instead of list, converting to empty list")
            return []
        return v


class ConsolidatedFindings(BaseModel):
    """
    Model for tracking consolidated findings across workflow steps.

    This model accumulates findings, files, methods, and issues
    discovered during multi-step work. It's used by
    BaseWorkflowMixin to track progress across workflow steps.
    """

    files_checked: set[str] = Field(default_factory=set, description="All files examined across all steps")
    relevant_files: set[str] = Field(
        default_factory=set,
        description="A subset of files_checked that have been identified as relevant for the work at hand",
    )
    relevant_context: set[str] = Field(
        default_factory=set, description="All methods/functions identified during overall work being performed"
    )
    findings: list[str] = Field(default_factory=list, description="Chronological list of findings from each work step")
    hypotheses: list[dict] = Field(default_factory=list, description="Evolution of hypotheses across work steps")
    issues_found: list[dict] = Field(default_factory=list, description="All issues found with severity levels")
    images: list[str] = Field(default_factory=list, description="Images collected during overall work")
    confidence: str = Field("low", description="Latest confidence level from work steps")


# Tool-specific field descriptions are now declared in each tool file
# This keeps concerns separated and makes each tool self-contained
