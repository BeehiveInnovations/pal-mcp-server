"""
Data models for tool responses and interactions
"""

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ToolModelCategory(Enum):
    """Categories for tool model selection based on requirements."""

    EXTENDED_REASONING = "extended_reasoning"  # Requires deep thinking capabilities
    FAST_RESPONSE = "fast_response"  # Speed and cost efficiency preferred
    BALANCED = "balanced"  # Balance of capability and performance


class ContinuationOffer(BaseModel):
    """Offer for Claude to continue conversation when Gemini doesn't ask follow-up"""

    continuation_id: str = Field(
        ..., description="Thread continuation ID for multi-turn conversations across different tools"
    )
    note: str = Field(..., description="Message explaining continuation opportunity to Claude")
    suggested_tool_params: Optional[dict[str, Any]] = Field(
        None, description="Suggested parameters for continued tool usage"
    )
    remaining_turns: int = Field(..., description="Number of conversation turns remaining")


class ToolOutput(BaseModel):
    """Standardized output format for all tools"""

    status: Literal[
        "success",
        "error",
        "files_required_to_continue",
        "full_codereview_required",
        "focused_review_required",
        "test_sample_needed",
        "more_tests_required",
        "refactor_analysis_complete",
        "trace_complete",
        "resend_prompt",
        "code_too_large",
        "continuation_available",
        "no_bug_found",
    ] = "success"
    content: Optional[str] = Field(None, description="The main content/response from the tool")
    content_type: Literal["text", "markdown", "json"] = "text"
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)
    continuation_offer: Optional[ContinuationOffer] = Field(
        None, description="Optional offer for Claude to continue conversation"
    )


class FilesNeededRequest(BaseModel):
    """Request for missing files / code to continue"""

    status: Literal["files_required_to_continue"] = "files_required_to_continue"
    mandatory_instructions: str = Field(..., description="Critical instructions for Claude regarding required context")
    files_needed: Optional[list[str]] = Field(
        default_factory=list, description="Specific files that are needed for analysis"
    )
    suggested_next_action: Optional[dict[str, Any]] = Field(
        None,
        description="Suggested tool call with parameters after getting clarification",
    )


class FullCodereviewRequired(BaseModel):
    """Request for full code review when scope is too large for quick review"""

    status: Literal["full_codereview_required"] = "full_codereview_required"
    important: Optional[str] = Field(None, description="Important message about escalation")
    reason: Optional[str] = Field(None, description="Reason why full review is needed")


class FocusedReviewRequired(BaseModel):
    """Request for Claude to provide smaller, focused subsets of code for review"""

    status: Literal["focused_review_required"] = "focused_review_required"
    reason: str = Field(..., description="Why the current scope is too large for effective review")
    suggestion: str = Field(
        ..., description="Suggested approach for breaking down the review into smaller, focused parts"
    )


class TestSampleNeeded(BaseModel):
    """Request for additional test samples to determine testing framework"""

    status: Literal["test_sample_needed"] = "test_sample_needed"
    reason: str = Field(..., description="Reason why additional test samples are required")


class MoreTestsRequired(BaseModel):
    """Request for continuation to generate additional tests"""

    status: Literal["more_tests_required"] = "more_tests_required"
    pending_tests: str = Field(..., description="List of pending tests to be generated")


class RefactorOpportunity(BaseModel):
    """A single refactoring opportunity with precise targeting information"""

    id: str = Field(..., description="Unique identifier for this refactoring opportunity")
    type: Literal["decompose", "codesmells", "modernize", "organization"] = Field(
        ..., description="Type of refactoring"
    )
    severity: Literal["critical", "high", "medium", "low"] = Field(..., description="Severity level")
    file: str = Field(..., description="Absolute path to the file")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    context_start_text: str = Field(..., description="Exact text from start line for verification")
    context_end_text: str = Field(..., description="Exact text from end line for verification")
    issue: str = Field(..., description="Clear description of what needs refactoring")
    suggestion: str = Field(..., description="Specific refactoring action to take")
    rationale: str = Field(..., description="Why this improves the code")
    code_to_replace: str = Field(..., description="Original code that should be changed")
    replacement_code_snippet: str = Field(..., description="Refactored version of the code")
    new_code_snippets: Optional[list[dict]] = Field(
        default_factory=list, description="Additional code snippets to be added"
    )


class RefactorAction(BaseModel):
    """Next action for Claude to implement refactoring"""

    action_type: Literal["EXTRACT_METHOD", "SPLIT_CLASS", "MODERNIZE_SYNTAX", "REORGANIZE_CODE", "DECOMPOSE_FILE"] = (
        Field(..., description="Type of action to perform")
    )
    target_file: str = Field(..., description="Absolute path to target file")
    source_lines: str = Field(..., description="Line range (e.g., '45-67')")
    description: str = Field(..., description="Step-by-step action description for Claude")


class RefactorAnalysisComplete(BaseModel):
    """Complete refactor analysis with prioritized opportunities"""

    status: Literal["refactor_analysis_complete"] = "refactor_analysis_complete"
    refactor_opportunities: list[RefactorOpportunity] = Field(..., description="List of refactoring opportunities")
    priority_sequence: list[str] = Field(..., description="Recommended order of refactoring IDs")
    next_actions_for_claude: list[RefactorAction] = Field(..., description="Specific actions for Claude to implement")


class CodeTooLargeRequest(BaseModel):
    """Request to reduce file selection due to size constraints"""

    status: Literal["code_too_large"] = "code_too_large"
    content: str = Field(..., description="Message explaining the size constraint")
    content_type: Literal["text"] = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResendPromptRequest(BaseModel):
    """Request to resend prompt via file due to size limits"""

    status: Literal["resend_prompt"] = "resend_prompt"
    content: str = Field(..., description="Instructions for handling large prompt")
    content_type: Literal["text"] = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceEntryPoint(BaseModel):
    """Entry point information for trace analysis"""

    file: str = Field(..., description="Absolute path to the file")
    class_or_struct: str = Field(..., description="Class or module name")
    method: str = Field(..., description="Method or function name")
    signature: str = Field(..., description="Full method signature")
    parameters: Optional[dict[str, Any]] = Field(default_factory=dict, description="Parameter values used in analysis")


class TraceTarget(BaseModel):
    """Target information for dependency analysis"""

    file: str = Field(..., description="Absolute path to the file")
    class_or_struct: str = Field(..., description="Class or module name")
    method: str = Field(..., description="Method or function name")
    signature: str = Field(..., description="Full method signature")


class CallPathStep(BaseModel):
    """A single step in the call path trace"""

    from_info: dict[str, Any] = Field(..., description="Source location information", alias="from")
    to: dict[str, Any] = Field(..., description="Target location information")
    reason: str = Field(..., description="Reason for the call or dependency")
    condition: Optional[str] = Field(None, description="Conditional logic if applicable")
    ambiguous: bool = Field(False, description="Whether this call is ambiguous")


class BranchingPoint(BaseModel):
    """A branching point in the execution flow"""

    file: str = Field(..., description="File containing the branching point")
    method: str = Field(..., description="Method containing the branching point")
    line: int = Field(..., description="Line number of the branching point")
    condition: str = Field(..., description="Branching condition")
    branches: list[str] = Field(..., description="Possible execution branches")
    ambiguous: bool = Field(False, description="Whether the branching is ambiguous")


class SideEffect(BaseModel):
    """A side effect detected in the trace"""

    type: str = Field(..., description="Type of side effect")
    description: str = Field(..., description="Description of the side effect")
    file: str = Field(..., description="File where the side effect occurs")
    method: str = Field(..., description="Method where the side effect occurs")
    line: int = Field(..., description="Line number of the side effect")


class UnresolvedDependency(BaseModel):
    """An unresolved dependency in the trace"""

    reason: str = Field(..., description="Reason why the dependency is unresolved")
    affected_file: str = Field(..., description="File affected by the unresolved dependency")
    line: int = Field(..., description="Line number of the unresolved dependency")


class IncomingDependency(BaseModel):
    """An incoming dependency (what calls this target)"""

    from_file: str = Field(..., description="Source file of the dependency")
    from_class: str = Field(..., description="Source class of the dependency")
    from_method: str = Field(..., description="Source method of the dependency")
    line: int = Field(..., description="Line number of the dependency")
    type: str = Field(..., description="Type of dependency")


class OutgoingDependency(BaseModel):
    """An outgoing dependency (what this target calls)"""

    to_file: str = Field(..., description="Target file of the dependency")
    to_class: str = Field(..., description="Target class of the dependency")
    to_method: str = Field(..., description="Target method of the dependency")
    line: int = Field(..., description="Line number of the dependency")
    type: str = Field(..., description="Type of dependency")


class TypeDependency(BaseModel):
    """A type-level dependency (inheritance, imports, etc.)"""

    dependency_type: str = Field(..., description="Type of dependency")
    source_file: str = Field(..., description="Source file of the dependency")
    source_entity: str = Field(..., description="Source entity (class, module)")
    target: str = Field(..., description="Target entity")


class StateAccess(BaseModel):
    """State access information"""

    file: str = Field(..., description="File where state is accessed")
    method: str = Field(..., description="Method accessing the state")
    access_type: str = Field(..., description="Type of access (reads, writes, etc.)")
    state_entity: str = Field(..., description="State entity being accessed")


class TraceComplete(BaseModel):
    """Complete trace analysis response"""

    status: Literal["trace_complete"] = "trace_complete"
    trace_type: Literal["precision", "dependencies"] = Field(..., description="Type of trace performed")

    # Precision mode fields
    entry_point: Optional[TraceEntryPoint] = Field(None, description="Entry point for precision trace")
    call_path: Optional[list[CallPathStep]] = Field(default_factory=list, description="Call path for precision trace")
    branching_points: Optional[list[BranchingPoint]] = Field(default_factory=list, description="Branching points")
    side_effects: Optional[list[SideEffect]] = Field(default_factory=list, description="Side effects detected")
    unresolved: Optional[list[UnresolvedDependency]] = Field(
        default_factory=list, description="Unresolved dependencies"
    )

    # Dependencies mode fields
    target: Optional[TraceTarget] = Field(None, description="Target for dependency analysis")
    incoming_dependencies: Optional[list[IncomingDependency]] = Field(
        default_factory=list, description="Incoming dependencies"
    )
    outgoing_dependencies: Optional[list[OutgoingDependency]] = Field(
        default_factory=list, description="Outgoing dependencies"
    )
    type_dependencies: Optional[list[TypeDependency]] = Field(default_factory=list, description="Type dependencies")
    state_access: Optional[list[StateAccess]] = Field(default_factory=list, description="State access information")


class DiagnosticHypothesis(BaseModel):
    """A debugging hypothesis with context and next steps"""

    rank: int = Field(..., description="Ranking of this hypothesis (1 = most likely)")
    confidence: Literal["high", "medium", "low"] = Field(..., description="Confidence level")
    hypothesis: str = Field(..., description="Description of the potential root cause")
    reasoning: str = Field(..., description="Why this hypothesis is plausible")
    next_step: str = Field(..., description="Suggested action to test/validate this hypothesis")


class StructuredDebugResponse(BaseModel):
    """Enhanced debug response with multiple hypotheses"""

    summary: str = Field(..., description="Brief summary of the issue")
    hypotheses: list[DiagnosticHypothesis] = Field(..., description="Ranked list of potential causes")
    immediate_actions: list[str] = Field(
        default_factory=list,
        description="Immediate steps to take regardless of root cause",
    )
    additional_context_needed: Optional[list[str]] = Field(
        default_factory=list,
        description="Additional files or information that would help with analysis",
    )


class DebugHypothesis(BaseModel):
    """A debugging hypothesis with detailed analysis"""

    name: str = Field(..., description="Name/title of the hypothesis")
    confidence: Literal["High", "Medium", "Low"] = Field(..., description="Confidence level")
    root_cause: str = Field(..., description="Technical explanation of the root cause")
    evidence: str = Field(..., description="Logs or code clues supporting this hypothesis")
    correlation: str = Field(..., description="How symptoms map to the cause")
    validation: str = Field(..., description="Quick test to confirm the hypothesis")
    minimal_fix: str = Field(..., description="Smallest change to resolve the issue")
    regression_check: str = Field(..., description="Why this fix is safe")
    file_references: list[str] = Field(default_factory=list, description="File:line format for exact locations")


class DebugAnalysisComplete(BaseModel):
    """Complete debugging analysis with systematic investigation tracking"""

    status: Literal["analysis_complete"] = "analysis_complete"
    investigation_id: str = Field(..., description="Auto-generated unique ID for this investigation")
    summary: str = Field(..., description="Brief description of the problem and its impact")
    investigation_steps: list[str] = Field(..., description="Steps taken during the investigation")
    hypotheses: list[DebugHypothesis] = Field(..., description="Ranked hypotheses with detailed analysis")
    key_findings: list[str] = Field(..., description="Important discoveries made during analysis")
    immediate_actions: list[str] = Field(..., description="Steps to take regardless of which hypothesis is correct")
    recommended_tools: list[str] = Field(default_factory=list, description="Additional tools recommended for analysis")
    prevention_strategy: Optional[str] = Field(
        None, description="Targeted measures to prevent this exact issue from recurring"
    )
    investigation_summary: str = Field(
        ..., description="Comprehensive summary of the complete investigation process and conclusions"
    )


class NoBugFound(BaseModel):
    """Response when thorough investigation finds no concrete evidence of a bug"""

    status: Literal["no_bug_found"] = "no_bug_found"
    summary: str = Field(..., description="Summary of what was thoroughly investigated")
    investigation_steps: list[str] = Field(..., description="Steps taken during the investigation")
    areas_examined: list[str] = Field(..., description="Code areas and potential failure points examined")
    confidence_level: Literal["High", "Medium", "Low"] = Field(
        ..., description="Confidence level in the no-bug finding"
    )
    alternative_explanations: list[str] = Field(
        ..., description="Possible alternative explanations for reported symptoms"
    )
    recommended_questions: list[str] = Field(..., description="Questions to clarify the issue with the user")
    next_steps: list[str] = Field(..., description="Suggested actions to better understand the reported issue")


# Registry mapping status strings to their corresponding Pydantic models
SPECIAL_STATUS_MODELS = {
    "files_required_to_continue": FilesNeededRequest,
    "full_codereview_required": FullCodereviewRequired,
    "focused_review_required": FocusedReviewRequired,
    "test_sample_needed": TestSampleNeeded,
    "more_tests_required": MoreTestsRequired,
    "refactor_analysis_complete": RefactorAnalysisComplete,
    "trace_complete": TraceComplete,
    "resend_prompt": ResendPromptRequest,
    "code_too_large": CodeTooLargeRequest,
    "analysis_complete": DebugAnalysisComplete,
    "no_bug_found": NoBugFound,
}
