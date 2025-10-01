"""
Tracer Workflow tool - Step-by-step code tracing and dependency analysis

This tool provides a structured workflow for comprehensive code tracing and analysis.
It guides the CLI agent through systematic investigation steps with forced pauses between each step
to ensure thorough code examination, dependency mapping, and execution flow analysis before proceeding.

The tracer guides users through sequential code analysis with full context awareness and
the ability to revise and adapt as understanding deepens.

Key features:
- Sequential tracing with systematic investigation workflow
- Support for precision tracing (execution flow) and dependencies tracing (structural relationships)
- Self-contained completion with detailed output formatting instructions
- Context-aware analysis that builds understanding step by step
- No external expert analysis needed - provides comprehensive guidance internally

Perfect for: method/function execution flow analysis, dependency mapping, call chain tracing,
structural relationship analysis, architectural understanding, and code comprehension.
"""

import logging
from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic import Field, field_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import TRACER_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions for tracer workflow
TRACER_WORKFLOW_FIELD_DESCRIPTIONS = {
    "step": (
        "The plan for the current tracing step. Step 1: State the tracing strategy. Later steps: Report findings and adapt the plan. "
        "CRITICAL: For 'precision' mode, focus on execution flow and call chains. For 'dependencies' mode, focus on structural relationships. "
        "If trace_mode is 'ask' in step 1, you MUST prompt the user to choose a mode."
    ),
    "step_number": (
        "The index of the current step in the tracing sequence, beginning at 1. Each step should build upon or "
        "revise the previous one."
    ),
    "total_steps": (
        "Your current estimate for how many steps will be needed to complete the tracing analysis. "
        "Adjust as new findings emerge."
    ),
    "next_step_required": (
        "Set to true if you plan to continue the investigation with another step. False means you believe the "
        "tracing analysis is complete and ready for final output formatting."
    ),
    "findings": (
        "Summary of discoveries from this step, including execution paths, dependency relationships, call chains, and structural patterns. "
        "IMPORTANT: Document both direct (immediate calls) and indirect (transitive, side effects) relationships."
    ),
    "files_checked": (
        "List all files examined (absolute paths). Include even ruled-out files to track exploration path."
    ),
    "relevant_files": (
        "Subset of files_checked directly relevant to the tracing target (absolute paths). Include implementation files, "
        "dependencies, or files demonstrating key relationships."
    ),
    "relevant_context": (
        "List methods/functions central to the tracing analysis, in 'ClassName.methodName' or 'functionName' format. "
        "Prioritize those in the execution flow or dependency chain."
    ),
    "confidence": (
        "Your confidence in the tracing analysis. Use: 'exploring', 'low', 'medium', 'high', 'very_high', 'almost_certain', 'certain'. "
        "CRITICAL: 'certain' implies the analysis is 100% complete locally and PREVENTS external model validation."
    ),
    "trace_mode": "Type of tracing: 'ask' (default - prompts user to choose mode), 'precision' (execution flow) or 'dependencies' (structural relationships)",
    "target_description": (
        "Description of what to trace and WHY. Include context about what you're trying to understand or analyze."
    ),
    "images": ("Optional paths to architecture diagrams or flow charts that help understand the tracing context."),
}


class TracerRequest(WorkflowRequest):
    """Request model for tracer workflow investigation steps"""

    # Required fields for each investigation step
    step: str = Field(..., description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"])

    # Investigation tracking fields
    findings: str = Field(..., description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["findings"])
    files_checked: list[str] = Field(
        default_factory=list, description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["files_checked"]
    )
    relevant_files: list[str] = Field(
        default_factory=list, description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"]
    )
    relevant_context: list[str] = Field(
        default_factory=list, description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["relevant_context"]
    )
    confidence: Optional[str] = Field("exploring", description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["confidence"])

    # Tracer-specific fields (used in step 1 to initialize)
    trace_mode: Optional[Literal["precision", "dependencies", "ask"]] = Field(
        "ask", description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["trace_mode"]
    )
    target_description: Optional[str] = Field(
        None, description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["target_description"]
    )
    images: Optional[list[str]] = Field(default=None, description=TRACER_WORKFLOW_FIELD_DESCRIPTIONS["images"])

    # Exclude fields not relevant to tracing workflow
    issues_found: list[dict] = Field(default_factory=list, exclude=True, description="Tracing doesn't track issues")
    hypothesis: Optional[str] = Field(default=None, exclude=True, description="Tracing doesn't use hypothesis")
    backtrack_from_step: Optional[int] = Field(
        default=None, exclude=True, description="Tracing doesn't use backtracking"
    )

    # Exclude other non-tracing fields
    temperature: Optional[float] = Field(default=None, exclude=True)
    thinking_mode: Optional[str] = Field(default=None, exclude=True)
    use_assistant_model: Optional[bool] = Field(default=False, exclude=True, description="Tracing is self-contained")

    @field_validator("step_number")
    @classmethod
    def validate_step_number(cls, v):
        if v < 1:
            raise ValueError("step_number must be at least 1")
        return v

    @field_validator("total_steps")
    @classmethod
    def validate_total_steps(cls, v):
        if v < 1:
            raise ValueError("total_steps must be at least 1")
        return v


class TracerTool(WorkflowTool):
    """
    Tracer workflow tool for step-by-step code tracing and dependency analysis.

    This tool implements a structured tracing workflow that guides users through
    methodical investigation steps, ensuring thorough code examination, dependency
    mapping, and execution flow analysis before reaching conclusions. It supports
    both precision tracing (execution flow) and dependencies tracing (structural relationships).
    """

    def __init__(self):
        super().__init__()
        self.initial_request = None
        self.trace_config = {}

    def get_name(self) -> str:
        return "tracer"

    def get_description(self) -> str:
        return (
            "Performs systematic code tracing with modes for execution flow or dependency mapping. "
            "Use for method execution analysis, call chain tracing, dependency mapping, and architectural understanding. "
            "Supports precision mode (execution flow) and dependencies mode (structural relationships)."
        )

    def get_system_prompt(self) -> str:
        return TRACER_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Tracer requires analytical reasoning for code analysis"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def requires_model(self) -> bool:
        """
        Tracer tool doesn't require model resolution at the MCP boundary.

        The tracer is a structured workflow tool that organizes tracing steps
        and provides detailed output formatting guidance without calling external AI models.

        Returns:
            bool: False - tracer doesn't need AI model access
        """
        return False

    def get_workflow_request_model(self):
        """Return the tracer-specific request model."""
        return TracerRequest

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        """Return tracing-specific field definitions beyond the standard workflow fields."""
        return {
            # Tracer-specific fields
            "trace_mode": {
                "type": "string",
                "enum": ["precision", "dependencies", "ask"],
                "description": TRACER_WORKFLOW_FIELD_DESCRIPTIONS["trace_mode"],
            },
            "target_description": {
                "type": "string",
                "description": TRACER_WORKFLOW_FIELD_DESCRIPTIONS["target_description"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": TRACER_WORKFLOW_FIELD_DESCRIPTIONS["images"],
            },
        }

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema using WorkflowSchemaBuilder with field exclusion."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Exclude investigation-specific fields that tracing doesn't need
        excluded_workflow_fields = [
            "issues_found",  # Tracing doesn't track issues
            "hypothesis",  # Tracing doesn't use hypothesis
            "backtrack_from_step",  # Tracing doesn't use backtracking
        ]

        # Exclude common fields that tracing doesn't need
        excluded_common_fields = [
            "temperature",  # Tracing doesn't need temperature control
            "thinking_mode",  # Tracing doesn't need thinking mode
            "files",  # Tracing uses relevant_files instead
        ]

        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=self.get_tool_fields(),
            required_fields=["target_description", "trace_mode"],  # Step 1 requires these
            model_field_schema=self.get_model_field_schema(),
            auto_mode=self.is_effective_auto_mode(),
            tool_name=self.get_name(),
            excluded_workflow_fields=excluded_workflow_fields,
            excluded_common_fields=excluded_common_fields,
        )

    # ================================================================================
    # Abstract Methods - Required Implementation from BaseWorkflowMixin
    # ================================================================================

    def get_required_actions(
        self, step_number: int, confidence: str, findings: str, total_steps: int, request=None
    ) -> list[str]:
        """Define required actions for each tracing phase."""
        if step_number == 1:
            # Check if we're in ask mode and need to prompt for mode selection
            if self.get_trace_mode() == "ask":
                return [
                    "MUST ask user to choose between precision or dependencies mode",
                    "Explain precision mode: traces execution flow, call chains, and usage patterns (best for methods/functions)",
                    "Explain dependencies mode: maps structural relationships and bidirectional dependencies (best for classes/modules)",
                    "Wait for user's mode selection before proceeding with investigation",
                ]

            # Initial tracing investigation tasks (when mode is already selected)
            return [
                "Search for and locate the target method/function/class/module in the codebase",
                "Read and understand the implementation of the target code",
                "Identify the file location, complete signature, and basic structure",
                "Begin mapping immediate relationships (what it calls, what calls it)",
                "Understand the context and purpose of the target code",
            ]
        elif confidence in ["exploring", "low"]:
            # Need deeper investigation
            return [
                "Trace deeper into the execution flow or dependency relationships",
                "Examine how the target code is used throughout the codebase",
                "Map additional layers of dependencies or call chains",
                "Look for conditional execution paths, error handling, and edge cases",
                "Understand the broader architectural context and patterns",
            ]
        elif confidence in ["medium", "high"]:
            # Close to completion - need final verification
            return [
                "Verify completeness of the traced relationships and execution paths",
                "Check for any missed dependencies, usage patterns, or execution branches",
                "Confirm understanding of side effects, state changes, and external interactions",
                "Validate that the tracing covers all significant code relationships",
                "Prepare comprehensive findings for final output formatting",
            ]
        else:
            # General investigation needed
            return [
                "Continue systematic tracing of code relationships and execution paths",
                "Gather more evidence using appropriate code analysis techniques",
                "Test assumptions about code behavior and dependency relationships",
                "Look for patterns that enhance understanding of the code structure",
                "Focus on areas that haven't been thoroughly traced yet",
            ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """Tracer is self-contained and doesn't need expert analysis."""
        return False

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Tracer doesn't use expert analysis."""
        return ""

    def requires_expert_analysis(self) -> bool:
        """Tracer is self-contained like the planner tool."""
        return False

    # ================================================================================
    # Workflow Customization - Match Planner Behavior
    # ================================================================================

    def prepare_step_data(self, request) -> dict:
        """
        Prepare step data from request with tracer-specific fields.
        """
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": request.findings,
            "files_checked": request.files_checked,
            "relevant_files": request.relevant_files,
            "relevant_context": request.relevant_context,
            "issues_found": [],  # Tracer doesn't track issues
            "confidence": request.confidence or "exploring",
            "hypothesis": None,  # Tracer doesn't use hypothesis
            "images": request.images or [],
            # Tracer-specific fields
            "trace_mode": request.trace_mode,
            "target_description": request.target_description,
        }
        return step_data

    def build_base_response(self, request, continuation_id: str = None) -> dict:
        """
        Build the base response structure with tracer-specific fields.
        """
        # Use work_history from workflow mixin for consistent step tracking
        current_step_count = len(self.work_history) + 1

        response_data = {
            "status": f"{self.get_name()}_in_progress",
            "step_number": request.step_number,
            "total_steps": request.total_steps,
            "next_step_required": request.next_step_required,
            "step_content": request.step,
            f"{self.get_name()}_status": {
                "files_checked": len(self.consolidated_findings.files_checked),
                "relevant_files": len(self.consolidated_findings.relevant_files),
                "relevant_context": len(self.consolidated_findings.relevant_context),
                "issues_found": len(self.consolidated_findings.issues_found),
                "images_collected": len(self.consolidated_findings.images),
                "current_confidence": self.get_request_confidence(request),
                "step_history_length": current_step_count,
            },
            "metadata": {
                "trace_mode": self.trace_config.get("trace_mode", "unknown"),
                "target_description": self.trace_config.get("target_description", ""),
                "step_history_length": current_step_count,
            },
        }

        if continuation_id:
            response_data["continuation_id"] = continuation_id

        return response_data

    def handle_work_continuation(self, response_data: dict, request) -> dict:
        """
        Handle work continuation with tracer-specific guidance.
        """
        response_data["status"] = f"pause_for_{self.get_name()}"
        response_data[f"{self.get_name()}_required"] = True

        # Get tracer-specific required actions
        required_actions = self.get_required_actions(
            request.step_number, request.confidence or "exploring", request.findings, request.total_steps
        )
        response_data["required_actions"] = required_actions

        # Generate step-specific guidance
        if request.step_number == 1:
            # Check if we're in ask mode and need to prompt for mode selection
            if self.get_trace_mode() == "ask":
                response_data["next_steps"] = (
                    f"STOP! You MUST ask the user to choose a tracing mode before proceeding. "
                    f"Present these options clearly:\\n\\n"
                    f"**PRECISION MODE**: Traces execution flow, call chains, and usage patterns. "
                    f"Best for understanding how a specific method or function works, what it calls, "
                    f"and how data flows through the execution path.\\n\\n"
                    f"**DEPENDENCIES MODE**: Maps structural relationships and bidirectional dependencies. "
                    f"Best for understanding how a class or module relates to other components, "
                    f"what depends on it, and what it depends on.\\n\\n"
                    f"After the user selects a mode, call {self.get_name()} again with step_number: 1 "
                    f"but with the chosen trace_mode (either 'precision' or 'dependencies')."
                )
            else:
                response_data["next_steps"] = (
                    f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. You MUST first investigate "
                    f"the codebase to understand the target code. CRITICAL AWARENESS: You need to find and understand "
                    f"the target method/function/class/module, examine its implementation, and begin mapping its "
                    f"relationships. Use file reading tools, code search, and systematic examination to gather "
                    f"comprehensive information about the target. Only call {self.get_name()} again AFTER completing "
                    f"your investigation. When you call {self.get_name()} next time, use step_number: {request.step_number + 1} "
                    f"and report specific files examined, code structure discovered, and initial relationship findings."
                )
        elif request.confidence in ["exploring", "low"]:
            next_step = request.step_number + 1
            response_data["next_steps"] = (
                f"STOP! Do NOT call {self.get_name()} again yet. Based on your findings, you've identified areas that need "
                f"deeper tracing analysis. MANDATORY ACTIONS before calling {self.get_name()} step {next_step}:\\n"
                + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\\n\\nOnly call {self.get_name()} again with step_number: {next_step} AFTER "
                + "completing these tracing investigations."
            )
        elif request.confidence in ["medium", "high"]:
            next_step = request.step_number + 1
            response_data["next_steps"] = (
                f"WAIT! Your tracing analysis needs final verification. DO NOT call {self.get_name()} immediately. "
                f"REQUIRED ACTIONS:\\n"
                + "\\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\\n\\nREMEMBER: Ensure you have traced all significant relationships and execution paths. "
                f"Document findings with specific file references and method signatures, then call {self.get_name()} "
                f"with step_number: {next_step}."
            )
        else:
            # General investigation needed
            next_step = request.step_number + 1
            remaining_steps = request.total_steps - request.step_number
            response_data["next_steps"] = (
                f"Continue systematic tracing with step {next_step}. Approximately {remaining_steps} steps remaining. "
                f"Focus on deepening your understanding of the code relationships and execution patterns."
            )

        return response_data

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """
        Customize response to match tracer tool format with output instructions.
        """
        # Store trace configuration on first step
        if request.step_number == 1:
            self.initial_request = request.step
            self.trace_config = {
                "trace_mode": request.trace_mode,
                "target_description": request.target_description,
            }

            # Update metadata with trace configuration
            if "metadata" in response_data:
                response_data["metadata"]["trace_mode"] = request.trace_mode or "unknown"
                response_data["metadata"]["target_description"] = request.target_description or ""

            # If in ask mode, mark this as mode selection phase
            if request.trace_mode == "ask":
                response_data["mode_selection_required"] = True
                response_data["status"] = "mode_selection_required"

        # Add tracer-specific output instructions for final steps
        if not request.next_step_required:
            response_data["tracing_complete"] = True
            response_data["trace_summary"] = f"TRACING COMPLETE: {request.step}"

            # Get mode-specific output instructions
            trace_mode = self.trace_config.get("trace_mode", "precision")
            rendering_instructions = self._get_rendering_instructions(trace_mode)

            response_data["output"] = {
                "instructions": (
                    "This is a structured tracing analysis response. Present the comprehensive tracing findings "
                    "using the specific rendering format for the trace mode. Follow the exact formatting guidelines "
                    "provided in rendering_instructions. Include all discovered relationships, execution paths, "
                    "and dependencies with precise file references and line numbers."
                ),
                "format": f"{trace_mode}_trace_analysis",
                "rendering_instructions": rendering_instructions,
                "presentation_guidelines": {
                    "completed_trace": (
                        "Use the exact rendering format specified for the trace mode. Include comprehensive "
                        "diagrams, tables, and structured analysis. Reference specific file paths and line numbers. "
                        "Follow formatting rules precisely."
                    ),
                    "step_content": "Present as main analysis with clear structure and actionable insights.",
                    "continuation": "Use continuation_id for related tracing sessions or follow-up analysis",
                },
            }
            response_data["next_steps"] = (
                f"Tracing analysis complete. Present the comprehensive {trace_mode} trace analysis to the user "
                f"using the exact rendering format specified in the output instructions. Follow the formatting "
                f"guidelines precisely, including diagrams, tables, and file references. After presenting the "
                f"analysis, offer to help with related tracing tasks or use the continuation_id for follow-up analysis."
            )

        # Convert generic status names to tracer-specific ones
        tool_name = self.get_name()
        status_mapping = {
            f"{tool_name}_in_progress": "tracing_in_progress",
            f"pause_for_{tool_name}": "pause_for_tracing",
            f"{tool_name}_required": "tracing_required",
            f"{tool_name}_complete": "tracing_complete",
        }

        if response_data["status"] in status_mapping:
            response_data["status"] = status_mapping[response_data["status"]]

        return response_data

    def _get_rendering_instructions(self, trace_mode: str) -> str:
        """
        Get mode-specific rendering instructions for the CLI agent.

        Args:
            trace_mode: Either "precision" or "dependencies"

        Returns:
            str: Complete rendering instructions for the specified mode
        """
        if trace_mode == "precision":
            return self._get_precision_rendering_instructions()
        else:  # dependencies mode
            return self._get_dependencies_rendering_instructions()

    def _get_precision_rendering_instructions(self) -> str:
        """Get rendering instructions for precision trace mode."""
        return """
## MANDATORY RENDERING INSTRUCTIONS FOR PRECISION TRACE

You MUST render the trace analysis using ONLY the Vertical Indented Flow Style:

### CALL FLOW DIAGRAM - Vertical Indented Style

**EXACT FORMAT TO FOLLOW:**
```
[ClassName::MethodName] (file: /complete/file/path.ext, line: ##)
↓
[AnotherClass::calledMethod] (file: /path/to/file.ext, line: ##)
↓
[ThirdClass::nestedMethod] (file: /path/file.ext, line: ##)
  ↓
  [DeeperClass::innerCall] (file: /path/inner.ext, line: ##) ? if some_condition
  ↓
  [ServiceClass::processData] (file: /services/service.ext, line: ##)
    ↓
    [RepositoryClass::saveData] (file: /data/repo.ext, line: ##)
    ↓
    [ClientClass::sendRequest] (file: /clients/client.ext, line: ##)
      ↓
      [EmailService::sendEmail] (file: /email/service.ext, line: ##) ⚠️ ambiguous branch
      →
      [SMSService::sendSMS] (file: /sms/service.ext, line: ##) ⚠️ ambiguous branch
```

**CRITICAL FORMATTING RULES:**

1. **Method Names**: Use the actual naming convention of the project language you're analyzing. Automatically detect and adapt to the project's conventions (camelCase, snake_case, PascalCase, etc.) based on the codebase structure and file extensions.

2. **Vertical Flow Arrows**:
   - Use `↓` for standard sequential calls (vertical flow)
   - Use `→` for parallel/alternative calls (horizontal branch)
   - NEVER use other arrow types

3. **Indentation Logic**:
   - Start at column 0 for entry point
   - Indent 2 spaces for each nesting level
   - Maintain consistent indentation for same call depth
   - Sibling calls at same level should have same indentation

4. **Conditional Calls**:
   - Add `? if condition_description` after method for conditional execution
   - Use actual condition names from code when possible

5. **Ambiguous Branches**:
   - Mark with `⚠️ ambiguous branch` when execution path is uncertain
   - Use `→` to show alternative paths at same indentation level

6. **File Path Format**:
   - Use complete relative paths from project root
   - Include actual file extensions from the project
   - Show exact line numbers where method is defined

### ADDITIONAL ANALYSIS VIEWS

**1. BRANCHING & SIDE EFFECT TABLE**

| Location | Condition | Branches | Uncertain |
|----------|-----------|----------|-----------|
| CompleteFileName.ext:## | if actual_condition_from_code | method1(), method2(), else skip | No |
| AnotherFile.ext:## | if boolean_check | callMethod(), else return | No |
| ThirdFile.ext:## | if validation_passes | processData(), else throw | Yes |

**2. SIDE EFFECTS**
```
Side Effects:
- [database] Specific database operation description (CompleteFileName.ext:##)
- [network] Specific network call description (CompleteFileName.ext:##)
- [filesystem] Specific file operation description (CompleteFileName.ext:##)
- [state] State changes or property modifications (CompleteFileName.ext:##)
- [memory] Memory allocation or cache operations (CompleteFileName.ext:##)
```

**3. USAGE POINTS**
```
Usage Points:
1. FileName.ext:## - Context description of where/why it's called
2. AnotherFile.ext:## - Context description of usage scenario
3. ThirdFile.ext:## - Context description of calling pattern
4. FourthFile.ext:## - Context description of integration point
```

**4. ENTRY POINTS**
```
Entry Points:
- ClassName::methodName (context: where this flow typically starts)
- AnotherClass::entryMethod (context: alternative entry scenario)
- ThirdClass::triggerMethod (context: event-driven entry point)
```

**ABSOLUTE REQUIREMENTS:**
- Use ONLY the vertical indented style for the call flow diagram
- Present ALL FOUR additional analysis views (Branching Table, Side Effects, Usage Points, Entry Points)
- Adapt method naming to match the project's programming language conventions
- Use exact file paths and line numbers from the actual codebase
- DO NOT invent or guess method names or locations
- Follow indentation rules precisely for call hierarchy
- Mark uncertain execution paths clearly
- Provide contextual descriptions in Usage Points and Entry Points sections
- Include comprehensive side effects categorization (database, network, filesystem, state, memory)"""

    def _get_dependencies_rendering_instructions(self) -> str:
        """Get rendering instructions for dependencies trace mode."""
        return """
## MANDATORY RENDERING INSTRUCTIONS FOR DEPENDENCIES TRACE

You MUST render the trace analysis using ONLY the Bidirectional Arrow Flow Style:

### DEPENDENCY FLOW DIAGRAM - Bidirectional Arrow Style

**EXACT FORMAT TO FOLLOW:**
```
INCOMING DEPENDENCIES → [TARGET_CLASS/MODULE] → OUTGOING DEPENDENCIES

CallerClass::callerMethod ←────┐
AnotherCaller::anotherMethod ←─┤
ThirdCaller::thirdMethod ←─────┤
                               │
                    [TARGET_CLASS/MODULE]
                               │
                               ├────→ FirstDependency::method
                               ├────→ SecondDependency::method
                               └────→ ThirdDependency::method

TYPE RELATIONSHIPS:
InterfaceName ──implements──→ [TARGET_CLASS] ──extends──→ BaseClass
DTOClass ──uses──→ [TARGET_CLASS] ──uses──→ EntityClass
```

**CRITICAL FORMATTING RULES:**

1. **Target Placement**: Always place the target class/module in square brackets `[TARGET_NAME]` at the center
2. **Incoming Dependencies**: Show on the left side with `←` arrows pointing INTO the target
3. **Outgoing Dependencies**: Show on the right side with `→` arrows pointing OUT FROM the target
4. **Arrow Alignment**: Use consistent spacing and alignment for visual clarity
5. **Method Naming**: Use the project's actual naming conventions detected from the codebase
6. **File References**: Include complete file paths and line numbers

**VISUAL LAYOUT RULES:**

1. **Header Format**: Always start with the flow direction indicator
2. **Left Side (Incoming)**:
   - List all callers with `←` arrows
   - Use `┐`, `┤`, `┘` box drawing characters for clean connection lines
   - Align arrows consistently

3. **Center (Target)**:
   - Enclose target in square brackets
   - Position centrally between incoming and outgoing

4. **Right Side (Outgoing)**:
   - List all dependencies with `→` arrows
   - Use `├`, `└` box drawing characters for branching
   - Maintain consistent spacing

5. **Type Relationships Section**:
   - Use `──relationship──→` format with double hyphens
   - Show inheritance, implementation, and usage relationships
   - Place below the main flow diagram

**DEPENDENCY TABLE:**

| Type | From/To | Method | File | Line |
|------|---------|--------|------|------|
| incoming_call | From: CallerClass | callerMethod | /complete/path/file.ext | ## |
| outgoing_call | To: TargetClass | targetMethod | /complete/path/file.ext | ## |
| implements | Self: ThisClass | — | /complete/path/file.ext | — |
| extends | Self: ThisClass | — | /complete/path/file.ext | — |
| uses_type | Self: ThisClass | — | /complete/path/file.ext | — |

**ABSOLUTE REQUIREMENTS:**
- Use ONLY the bidirectional arrow flow style shown above
- Automatically detect and use the project's naming conventions
- Use exact file paths and line numbers from the actual codebase
- DO NOT invent or guess method/class names
- Maintain visual alignment and consistent spacing
- Include type relationships section when applicable
- Show clear directional flow with proper arrows"""

    # ================================================================================
    # Hook Method Overrides for Tracer-Specific Behavior
    # ================================================================================

    def get_completion_status(self) -> str:
        """Tracer uses tracing-specific status."""
        return "tracing_complete"

    def get_completion_data_key(self) -> str:
        """Tracer uses 'complete_tracing' key."""
        return "complete_tracing"

    def get_completion_message(self) -> str:
        """Tracer-specific completion message."""
        return (
            "Tracing analysis complete. Present the comprehensive trace analysis to the user "
            "using the specified rendering format and offer to help with related tracing tasks."
        )

    def get_skip_reason(self) -> str:
        """Tracer-specific skip reason."""
        return "Tracer is self-contained and completes analysis without external assistance"

    def get_skip_expert_analysis_status(self) -> str:
        """Tracer-specific expert analysis skip status."""
        return "skipped_by_tool_design"

    def store_initial_issue(self, step_description: str):
        """Store initial tracing description."""
        self.initial_tracing_description = step_description

    def get_initial_request(self, fallback_step: str) -> str:
        """Get initial tracing description."""
        try:
            return self.initial_tracing_description
        except AttributeError:
            return fallback_step

    def get_request_confidence(self, request) -> str:
        """Get confidence from request for tracer workflow."""
        try:
            return request.confidence or "exploring"
        except AttributeError:
            return "exploring"

    def get_trace_mode(self) -> str:
        """Get current trace mode. Override for custom trace mode handling."""
        try:
            return self.trace_config.get("trace_mode", "ask")
        except AttributeError:
            return "ask"

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the tracer-specific request model."""
        return TracerRequest

    async def prepare_prompt(self, request) -> str:
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
