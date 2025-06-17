"""
Debug Issue tool - Root cause analysis and debugging assistance
"""

from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import DEBUG_ISSUE_PROMPT

from .base import BaseTool, ToolRequest

# Field descriptions to avoid duplication between Pydantic and JSON schema
DEBUG_FIELD_DESCRIPTIONS = {
    "prompt": (
        "Claud - you MUST first think deep. Issue description. Include what you can provide: "
        "error messages, symptoms, when it occurs, steps to reproduce, environment details, "
        "recent changes, and any other relevant information. Mention any previous attempts at fixing this issue, "
        "including any past fix that was in place but has now regressed. "
        "The more context available, the better the analysis. "
        "SYSTEMATIC INVESTIGATION: Claude MUST begin by thinking hard and performing a thorough investigation using a systematic approach. "
        "First understand the issue, find the code that may be causing it or code that is breaking, as well as any related code that could have caused this as a side effect. "
        "Claude MUST maintain detailed investigation notes in a DEBUGGING_{issue_description}.md file within the project folder, "
        "updating it as it performs step-by-step analysis of the code, trying to determine the actual root cause and understanding how a minimal, appropriate fix can be found. "
        "This file MUST contain functions, methods, files visited OR determined to be part of the problem. Claude MUST update this and remove any references that it finds to be irrelevant during its investigation. "
        "CRITICAL: If after thorough investigation Claude has very high confidence that NO BUG EXISTS that correlates to the reported symptoms, "
        "Claude should consider the possibility that the reported issue may not actually be present, may be a misunderstanding, or may be conflated with something else entirely. "
        "In such cases, Claude should gather more information from the user through targeted questioning rather than continue hunting for non-existent bugs. "
        "Once complete, Claude MUST provide Zen's debug tool with this file passed into the files parameter. "
        "It is ESSENTIAL that this detailed work is performed by Claude before sharing all the relevant details with its development assistant. This will greatly help in zeroing in on the root cause."
    ),
    "findings": (
        "Claude MUST first perform its own investigation, gather its findings and analysis. Include: steps taken to analyze the issue, "
        "code patterns discovered, initial hypotheses formed, any relevant classes/functions/methods examined, "
        "and any preliminary conclusions. If investigation yields no concrete evidence of a bug correlating to the reported symptoms, "
        "Claude should clearly state this finding and consider that the issue may not exist as described. "
        "This provides context for the assistant model's analysis."
    ),
    "files": (
        "Essential files for debugging - ONLY include files that are directly related to the issue, "
        "contain the problematic code, or are necessary for understanding the root cause. "
        "This can include any relevant log files, error description documents, investigation documents, "
        "claude's own findings as a document, related code that may help with analysis."
        "DO NOT include every file scanned during investigation (must be absolute paths)."
    ),
    "error_context": "Stack trace, snippet from logs, or additional error context. For very large text you MUST instead"
    "save the context as a temporary file within the project folder and share it as an absolute file path"
    "reference to the files parameter.",
    "images": "Optional images showing error screens, UI issues, logs displays, or visual debugging information",
}


class DebugIssueRequest(ToolRequest):
    """Request model for debug tool"""

    prompt: str = Field(..., description=DEBUG_FIELD_DESCRIPTIONS["prompt"])
    findings: Optional[str] = Field(None, description=DEBUG_FIELD_DESCRIPTIONS["findings"])
    files: Optional[list[str]] = Field(None, description=DEBUG_FIELD_DESCRIPTIONS["files"])
    error_context: Optional[str] = Field(None, description=DEBUG_FIELD_DESCRIPTIONS["error_context"])
    images: Optional[list[str]] = Field(None, description=DEBUG_FIELD_DESCRIPTIONS["images"])


class DebugIssueTool(BaseTool):
    """Advanced debugging and root cause analysis tool"""

    def get_name(self) -> str:
        return "debug"

    def get_description(self) -> str:
        return (
            "DEBUG & ROOT CAUSE ANALYSIS - Expert debugging for complex issues with systematic investigation support. "
            "Use this when you need to debug code, find out why something is failing, identify root causes, "
            "trace errors, or diagnose issues. "
            "MANDATORY: Claud you MUST first think deep and follow these instructions when using this tool"
            "SYSTEMATIC INVESTIGATION WORKFLOW: "
            "Claude MUST begin by thinking hard and performing a thorough investigation using a systematic approach. "
            "First understand the issue, find the code that may be causing it or code that is breaking, as well as any related code that could have caused this as a side effect. "
            "Claude MUST maintain detailed investigation notes while it performs its analysis, "
            "updating it as it performs step-by-step analysis of the code, trying to determine the actual root cause and understanding how a minimal, appropriate fix can be found. "
            "This file MUST contain functions, methods, files visited OR determined to be part of the problem. Claude MUST update this and remove any references that it finds to be irrelevant during its investigation. "
            "Once complete, Claude MUST provide Zen's debug tool with this file passed into the files parameter. "
            "1. INVESTIGATE SYSTEMATICALLY: Claude MUST think and use a methodical approach to trace through error reports, "
            "examine code, and gather evidence step by step "
            "2. DOCUMENT FINDINGS: Maintain detailed investigation notes to "
            "keep the user informed during its initial investigation. This investigation MUST be shared with this tool for the assistant "
            "to be able to help more effectively. "
            "3. USE TRACER TOOL: For complex method calls, class references, or side effects use Zen's tracer tool and include its output as part of the "
            "prompt or additional context "
            "4. COLLECT EVIDENCE: Document important discoveries and validation attempts "
            "5. PROVIDE COMPREHENSIVE FINDINGS: Pass complete findings to this tool for expert analysis "
            "INVESTIGATION METHODOLOGY: "
            "- Start with error messages/symptoms and work backwards to root cause "
            "- Examine code flow and identify potential failure points "
            "- Use tracer tool for complex method interactions and dependencies if and as needed but continue with the investigation after using it "
            "- Test hypotheses against actual code and logs and confirm the idea holds "
            "- Document everything systematically "
            "- CRITICAL: If investigation yields no concrete evidence of a bug, consider that the reported issue may not exist as described and gather more information through questioning "
            "ESSENTIAL FILES ONLY: Include only files (documents, code etc) directly related to the issue. "
            "Focus on quality over quantity for assistant model analysis. "
            "STRUCTURED OUTPUT: Assistant models return JSON responses with hypothesis "
            "ranking, evidence correlation, and actionable fixes. "
            "Choose thinking_mode based on issue complexity: 'low' for simple errors, "
            "'medium' for standard debugging (default), 'high' for complex system issues, "
            "'max' for extremely challenging bugs requiring deepest analysis. "
            "Note: If you're not currently using a top-tier model such as Opus 4 or above, these tools can provide enhanced capabilities."
        )

    def get_input_schema(self) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": DEBUG_FIELD_DESCRIPTIONS["prompt"],
                },
                "model": self.get_model_field_schema(),
                "findings": {
                    "type": "string",
                    "description": DEBUG_FIELD_DESCRIPTIONS["findings"],
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": DEBUG_FIELD_DESCRIPTIONS["files"],
                },
                "error_context": {
                    "type": "string",
                    "description": DEBUG_FIELD_DESCRIPTIONS["error_context"],
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": DEBUG_FIELD_DESCRIPTIONS["images"],
                },
                "temperature": {
                    "type": "number",
                    "description": "Temperature (0-1, default 0.2 for accuracy)",
                    "minimum": 0,
                    "maximum": 1,
                },
                "thinking_mode": {
                    "type": "string",
                    "enum": ["minimal", "low", "medium", "high", "max"],
                    "description": "Thinking depth: minimal (0.5% of model max), low (8%), medium (33%), high (67%), max (100% of model max)",
                },
                "use_websearch": {
                    "type": "boolean",
                    "description": "Enable web search for documentation, best practices, and current information. Particularly useful for: brainstorming sessions, architectural design discussions, exploring industry best practices, working with specific frameworks/technologies, researching solutions to complex problems, or when current documentation and community insights would enhance the analysis.",
                    "default": True,
                },
                "continuation_id": {
                    "type": "string",
                    "description": "Thread continuation ID for multi-turn conversations. Can be used to continue conversations across different tools. Only provide this if continuing a previous conversation thread.",
                },
            },
            "required": ["prompt"] + (["model"] if self.is_effective_auto_mode() else []),
        }

        return schema

    def get_system_prompt(self) -> str:
        return DEBUG_ISSUE_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    # Line numbers are enabled by default from base class for precise error location

    def get_model_category(self) -> "ToolModelCategory":
        """Debug requires deep analysis and reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_request_model(self):
        return DebugIssueRequest

    async def prepare_prompt(self, request: DebugIssueRequest) -> str:
        """Prepare the debugging prompt"""
        # Check for prompt.txt in files
        prompt_content, updated_files = self.handle_prompt_file(request.files)

        # If prompt.txt was found, use it as prompt or error_context
        if prompt_content:
            if not request.prompt or request.prompt == "":
                request.prompt = prompt_content
            else:
                request.error_context = prompt_content

        # Check user input sizes at MCP transport boundary (before adding internal content)
        size_check = self.check_prompt_size(request.prompt)
        if size_check:
            from tools.models import ToolOutput

            raise ValueError(f"MCP_SIZE_CHECK:{ToolOutput(**size_check).model_dump_json()}")

        if request.error_context:
            size_check = self.check_prompt_size(request.error_context)
            if size_check:
                from tools.models import ToolOutput

                raise ValueError(f"MCP_SIZE_CHECK:{ToolOutput(**size_check).model_dump_json()}")

        # Update request files list
        if updated_files is not None:
            request.files = updated_files

        # File size validation happens at MCP boundary in server.py

        # Build context sections
        context_parts = [f"=== ISSUE DESCRIPTION ===\n{request.prompt}\n=== END DESCRIPTION ==="]

        if request.findings:
            context_parts.append(f"\n=== CLAUDE'S INVESTIGATION FINDINGS ===\n{request.findings}\n=== END FINDINGS ===")

        if request.error_context:
            context_parts.append(f"\n=== ERROR CONTEXT/STACK TRACE ===\n{request.error_context}\n=== END CONTEXT ===")

        # Add relevant files if provided
        if request.files:
            # Use centralized file processing logic
            continuation_id = getattr(request, "continuation_id", None)
            file_content, processed_files = self._prepare_file_content_for_prompt(
                request.files, continuation_id, "Code"
            )
            self._actually_processed_files = processed_files

            if file_content:
                context_parts.append(
                    f"\n=== ESSENTIAL FILES FOR DEBUGGING ===\n{file_content}\n=== END ESSENTIAL FILES ==="
                )

        full_context = "\n".join(context_parts)

        # Check token limits
        self._validate_token_limit(full_context, "Context")

        # Add web search instruction if enabled
        websearch_instruction = self.get_websearch_instruction(
            request.use_websearch,
            """When debugging issues, consider if searches for these would help:
- The exact error message to find known solutions
- Framework-specific error codes and their meanings
- Similar issues in forums, GitHub issues, or Stack Overflow
- Workarounds and patches for known bugs
- Version-specific issues and compatibility problems""",
        )

        # Combine everything
        full_prompt = f"""{self.get_system_prompt()}{websearch_instruction}

{full_context}

Please debug this issue following the structured format in the system prompt.
Focus on finding the root cause and providing actionable solutions."""

        return full_prompt

    def _get_model_name(self, model_info: Optional[dict]) -> str:
        """Extract friendly model name from model info."""
        if model_info and model_info.get("model_response"):
            return model_info["model_response"].friendly_name or "the model"
        return "the model"

    def _generate_systematic_next_steps(self, model_name: str) -> str:
        """Generate next steps for systematic investigation completion."""
        return f"""**Expert Analysis Complete**

{model_name} has analyzed your systematic investigation findings.

**Next Steps:**
1. **UPDATE INVESTIGATION DOCUMENT**: Add the expert analysis to your DEBUGGING_*.md file
2. **REVIEW HYPOTHESES**: Examine the ranked hypotheses and evidence validation
3. **IMPLEMENT FIXES**: Apply recommended minimal fixes in order of likelihood
4. **VALIDATE CHANGES**: Test each fix thoroughly to ensure no regressions
5. **DOCUMENT RESOLUTION**: Update investigation document with final resolution"""

    def _generate_standard_analysis_steps(self, model_name: str) -> str:
        """Generate next steps for standard analysis completion."""
        return f"""**Expert Analysis Complete**

{model_name} has analyzed your investigation findings.

**Next Steps:**
1. **REVIEW HYPOTHESES**: Examine the ranked hypotheses and evidence
2. **IMPLEMENT FIXES**: Apply recommended minimal fixes in order of likelihood
3. **VALIDATE CHANGES**: Test each fix thoroughly to ensure no regressions"""

    def _generate_general_analysis_steps(self, model_name: str) -> str:
        """Generate next steps for general analysis responses."""
        return f"""**Analysis from {model_name}**

**Next Steps:** Continue your systematic investigation based on the guidance provided, then return
with comprehensive findings for expert analysis."""

    def format_response(self, response: str, request: DebugIssueRequest, model_info: Optional[dict] = None) -> str:
        """Format the debugging response for Claude to present to user"""
        # The base class automatically handles structured responses like 'clarification_required'
        # and 'analysis_complete' via SPECIAL_STATUS_MODELS, so we only handle normal text responses here

        model_name = self._get_model_name(model_info)

        # For normal text responses, provide general guidance
        next_steps = self._generate_general_analysis_steps(model_name)

        return f"""{response}

---

{next_steps}"""
