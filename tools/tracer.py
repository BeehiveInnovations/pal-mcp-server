"""
Tracer tool - Prompt generator for static code analysis workflows

This tool generates structured prompts and instructions for static code analysis.
It helps Claude create focused analysis requests and provides detailed rendering
instructions for visualizing call paths and dependency mappings.
"""

from typing import Any, Literal

from pydantic import Field

from .base import BaseTool, ToolRequest

# Field descriptions to avoid duplication between Pydantic and JSON schema
TRACER_FIELD_DESCRIPTIONS = {
    "prompt": (
        "Detailed description of what to trace and WHY you need this analysis. MUST include context about what "
        "you're trying to understand, debug, analyze or find. For precision mode: describe the specific "
        "method/function and what aspect of its execution flow you need to understand. For dependencies "
        "mode: describe the class/module and what relationships you need to map. Example: 'I need to "
        "understand how BookingManager.finalizeInvoice method is called throughout the system and what "
        "side effects it has, as I'm debugging payment processing issues' rather than just "
        "'BookingManager finalizeInvoice method'"
    ),
    "trace_mode": (
        "Trace mode: 'precision' (for methods/functions - shows execution flow and usage patterns) or "
        "'dependencies' (for classes/modules/protocols - shows structural relationships)"
    ),
    "images": (
        "Optional images of system architecture diagrams, flow charts, or visual references to help "
        "understand the tracing context"
    ),
}


class TracerRequest(ToolRequest):
    """
    Request model for the tracer tool.

    This model defines the parameters for generating analysis prompts.
    """

    prompt: str = Field(..., description=TRACER_FIELD_DESCRIPTIONS["prompt"])
    trace_mode: Literal["precision", "dependencies"] = Field(..., description=TRACER_FIELD_DESCRIPTIONS["trace_mode"])
    images: list[str] = Field(default_factory=list, description=TRACER_FIELD_DESCRIPTIONS["images"])


class TracerTool(BaseTool):
    """
    Tracer tool implementation.

    This tool generates structured prompts and instructions for static code analysis.
    It creates detailed requests and provides rendering instructions for Claude.
    """

    def get_name(self) -> str:
        return "tracer"

    def get_description(self) -> str:
        return (
            "ANALYSIS PROMPT GENERATOR - Creates structured prompts for static code analysis. "
            "Helps generate detailed analysis requests with specific method/function names, file paths, and "
            "component context. "
            "Type 'precision': For methods/functions - traces execution flow, call chains, call stacks, and "
            "shows when/how they are used. "
            "Type 'dependencies': For classes/modules/protocols - maps structural relationships and "
            "bidirectional dependencies. "
            "Returns detailed instructions on how to perform the analysis and format the results. "
            "Use this to create focused analysis requests that can be fed back to Claude with the appropriate "
            "code files. "
        )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": TRACER_FIELD_DESCRIPTIONS["prompt"],
                },
                "trace_mode": {
                    "type": "string",
                    "enum": ["precision", "dependencies"],
                    "description": TRACER_FIELD_DESCRIPTIONS["trace_mode"],
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": TRACER_FIELD_DESCRIPTIONS["images"],
                },
            },
            "required": ["prompt", "trace_mode"],
        }

    def get_model_category(self):
        """Tracer is a simple prompt generator"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.FAST_RESPONSE

    def get_request_model(self):
        return TracerRequest

    def get_system_prompt(self) -> str:
        """Not used in this simplified tool."""
        return ""

    async def prepare_prompt(self, request: TracerRequest) -> str:
        """Not used in this simplified tool."""
        return ""

    async def execute(self, arguments: dict[str, Any]) -> list:
        """Generate analysis prompt and instructions."""

        request = TracerRequest(**arguments)

        # Create enhanced prompt with specific instructions
        enhanced_prompt = self._create_enhanced_prompt(request.prompt, request.trace_mode)

        # Get rendering instructions
        rendering_instructions = self._get_rendering_instructions(request.trace_mode)

        # Create response with both the enhanced prompt and instructions
        response_content = f"""THIS IS A STATIC CODE ANALYSIS REQUEST:

{enhanced_prompt}

## Analysis Instructions

{rendering_instructions}

CRITICAL: Comprehensive Search and Call-Graph Generation:
First, think and identify and collect all relevant code, files, and declarations connected to the method, class, or module
in question:

- If you are unable to find the code or mentioned files, look for the relevant code in subfolders. If unsure, ask the user
to confirm location of folder / filename
- You MUST carry this task using your own tools, do NOT delegate this to any other model
- DO NOT automatically use any zen tools (including zen:analyze, zen:debug, zen:chat, etc.) to perform this analysis.
- EXCEPTION: If files are very large or the codebase is too complex for direct analysis due to context limitations,
you may use zen tools with a larger context model to assist with analysis by passing only the relevant files
- Understand carefully and fully how this code is used, what it depends on, and what other parts of the system depend on it
- Think through what other components or services are affected by this code's execution — directly or indirectly.
- Consider what happens when the code succeeds or fails, and what ripple effects a change to it would cause.


Finally, present your output in a clearly structured format, following rendering guidelines exactly.

IMPORTANT: If using this tool in conjunction with other work, another tool or another checklist item must be completed
immediately then do not stop after displaying your output, proceed directly to your next step.
"""

        from mcp.types import TextContent

        return [TextContent(type="text", text=response_content)]

    def _create_enhanced_prompt(self, original_prompt: str, trace_mode: str) -> str:
        """Create an enhanced, specific prompt for analysis."""
        mode_guidance = {
            "precision": "Follow the exact execution path from the specified method/function, including all method calls, branching logic, and side effects. Track the complete flow from entry point through all called functions. Show when and how this method/function is used throughout the codebase.",
            "dependencies": "Map all bidirectional dependencies for the specified class/module/protocol: what calls this target (incoming) and what it calls (outgoing). Include imports, inheritance, state access, type relationships, and structural connections.",
        }

        return f"""

TARGET: {original_prompt}
MODE: {trace_mode}

**Specific Instructions**:
{mode_guidance[trace_mode]}

**CRITICAL: Comprehensive File Search Requirements**:
- If you are unable to find the code or mentioned files, look for the relevant code in subfolders. If unsure, ask the user
to confirm location of folder / filename
- DO NOT automatically use any zen tools (including zen:analyze, zen:debug, zen:chat, etc.) to perform this analysis
- EXCEPTION: If files are very large or the codebase is too complex for direct analysis due to context limitations,
you may use zen tools with a larger context model to assist with analysis by passing only the relevant files

**What to identify** (works with any programming language/project):
- Exact method/function names with full signatures and parameter types
- Complete file paths and line numbers for all references
- Class/module context, namespace, and package relationships
- Conditional branches, their conditions, and execution paths
- Side effects (database, network, filesystem, state changes, logging)
- Type relationships, inheritance, polymorphic dispatch, and interfaces
- Cross-module/cross-service dependencies and API boundaries
- Configuration dependencies, environment variables, and external resources
- Error handling paths, exception propagation, and recovery mechanisms
- Async/concurrent execution patterns and synchronization points
- Memory allocation patterns and resource lifecycle management

**Analysis Focus**:
Provide concrete, code-based evidence for all findings. Reference specific line numbers and include exact method signatures. Identify uncertain paths where parameters or runtime context affects flow. Consider project scope and architectural patterns (monolith, microservices, layered, etc.).
"""

    def _get_rendering_instructions(self, trace_mode: str) -> str:
        """
        Get mode-specific rendering instructions for Claude.

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
