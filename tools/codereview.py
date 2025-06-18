"""
Code Review tool - Comprehensive code analysis and review

This tool provides professional-grade code review capabilities using
the chosen model's understanding of code patterns, best practices, and common issues.
It can analyze individual files or entire codebases, providing actionable
feedback categorized by severity.

Key Features:
- Multi-file and directory support
- Configurable review types (full, security, performance, quick)
- Severity-based issue filtering
- Custom focus areas and coding standards
- Structured output with specific remediation steps
"""

from typing import Any, Optional

from pydantic import Field

from config import TEMPERATURE_ANALYTICAL
from systemprompts import CODEREVIEW_PROMPT

from .base import BaseTool, ToolRequest

# Field descriptions to avoid duplication between Pydantic and JSON schema
CODEREVIEW_FIELD_DESCRIPTIONS = {
    "files": "Code files or directories to review that are relevant to the code that needs review or are closely "
    "related to the code or component that needs to be reviewed (must be FULL absolute paths to real files / folders - DO NOT SHORTEN)."
    "Validate that these files exist on disk before sharing and only share code that is relevant.",
    "prompt": (
        "User's summary of what the code does, expected behavior, constraints, and review objectives. "
        "IMPORTANT: Before using this tool, you should first perform its own preliminary review - "
        "examining the code structure, identifying potential issues, understanding the business logic, "
        "and noting areas of concern. Include your initial observations about code quality, potential "
        "bugs, architectural patterns, and specific areas that need deeper scrutiny. This dual-perspective "
        "approach (your analysis + external model's review) provides more comprehensive feedback and "
        "catches issues that either reviewer might miss alone."
    ),
    "images": (
        "Optional images of architecture diagrams, UI mockups, design documents, or visual references "
        "for code review context"
    ),
    "review_type": "Type of review to perform",
    "focus_on": "Specific aspects to focus on, or additional context that would help understand areas of concern",
    "standards": "Coding standards to enforce",
    "severity_filter": "Minimum severity level to report",
}


class CodeReviewRequest(ToolRequest):
    """
    Request model for the code review tool.

    This model defines all parameters that can be used to customize
    the code review process, from selecting files to specifying
    review focus and standards.
    """

    files: list[str] = Field(..., description=CODEREVIEW_FIELD_DESCRIPTIONS["files"])
    prompt: str = Field(..., description=CODEREVIEW_FIELD_DESCRIPTIONS["prompt"])
    images: Optional[list[str]] = Field(None, description=CODEREVIEW_FIELD_DESCRIPTIONS["images"])
    review_type: str = Field("full", description=CODEREVIEW_FIELD_DESCRIPTIONS["review_type"])
    focus_on: Optional[str] = Field(None, description=CODEREVIEW_FIELD_DESCRIPTIONS["focus_on"])
    standards: Optional[str] = Field(None, description=CODEREVIEW_FIELD_DESCRIPTIONS["standards"])
    severity_filter: str = Field("all", description=CODEREVIEW_FIELD_DESCRIPTIONS["severity_filter"])


class CodeReviewTool(BaseTool):
    """
    Professional code review tool implementation.

    This tool analyzes code for bugs, security vulnerabilities, performance
    issues, and code quality problems. It provides detailed feedback with
    severity ratings and specific remediation steps.
    """

    def get_name(self) -> str:
        return "codereview"

    def get_description(self) -> str:
        return (
            "PROFESSIONAL CODE REVIEW - Comprehensive analysis for bugs, security, and quality. "
            "Supports both individual files and entire directories/projects. "
            "Use this when you need to review code, check for issues, find bugs, or perform security audits. "
            "ALSO use this to validate claims about code, verify code flow and logic, confirm assertions, "
            "cross-check functionality, or investigate how code actually behaves when you need to be certain. "
            "I'll identify issues by severity (Critical→High→Medium→Low) with specific fixes. "
            "Supports focused reviews: security, performance, or quick checks. "
            "Choose thinking_mode based on review scope: 'low' for small code snippets, "
            "'medium' for standard files/modules (default), 'high' for complex systems/architectures, "
            "'max' for critical security audits or large codebases requiring deepest analysis. "
            "Note: If you're not currently using a top-tier model such as Opus 4 or above, these tools "
            "can provide enhanced capabilities."
        )

    def get_input_schema(self) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CODEREVIEW_FIELD_DESCRIPTIONS["files"],
                },
                "model": self.get_model_field_schema(),
                "prompt": {
                    "type": "string",
                    "description": CODEREVIEW_FIELD_DESCRIPTIONS["prompt"],
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CODEREVIEW_FIELD_DESCRIPTIONS["images"],
                },
                "review_type": {
                    "type": "string",
                    "enum": ["full", "security", "performance", "quick"],
                    "default": "full",
                    "description": CODEREVIEW_FIELD_DESCRIPTIONS["review_type"],
                },
                "focus_on": {
                    "type": "string",
                    "description": CODEREVIEW_FIELD_DESCRIPTIONS["focus_on"],
                },
                "standards": {
                    "type": "string",
                    "description": CODEREVIEW_FIELD_DESCRIPTIONS["standards"],
                },
                "severity_filter": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low", "all"],
                    "default": "all",
                    "description": CODEREVIEW_FIELD_DESCRIPTIONS["severity_filter"],
                },
                "temperature": {
                    "type": "number",
                    "description": "Temperature (0-1, default 0.2 for consistency)",
                    "minimum": 0,
                    "maximum": 1,
                },
                "thinking_mode": {
                    "type": "string",
                    "enum": ["minimal", "low", "medium", "high", "max"],
                    "description": (
                        "Thinking depth: minimal (0.5% of model max), low (8%), medium (33%), high (67%), "
                        "max (100% of model max)"
                    ),
                },
                "use_websearch": {
                    "type": "boolean",
                    "description": (
                        "Enable web search for documentation, best practices, and current information. "
                        "Particularly useful for: brainstorming sessions, architectural design discussions, "
                        "exploring industry best practices, working with specific frameworks/technologies, "
                        "researching solutions to complex problems, or when current documentation and community "
                        "insights would enhance the analysis."
                    ),
                    "default": True,
                },
                "continuation_id": {
                    "type": "string",
                    "description": (
                        "Thread continuation ID for multi-turn conversations. Can be used to continue "
                        "conversations across different tools. Only provide this if continuing a previous "
                        "conversation thread."
                    ),
                },
            },
            "required": ["files", "prompt"] + (["model"] if self.is_effective_auto_mode() else []),
        }

        return schema

    def get_system_prompt(self) -> str:
        return CODEREVIEW_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    # Line numbers are enabled by default from base class for precise feedback

    def get_request_model(self):
        return CodeReviewRequest

    async def prepare_prompt(self, request: CodeReviewRequest) -> str:
        """
        Prepare the code review prompt with customized instructions.

        This method reads the requested files, validates token limits,
        and constructs a detailed prompt based on the review parameters.

        Args:
            request: The validated review request

        Returns:
            str: Complete prompt for the model

        Raises:
            ValueError: If the code exceeds token limits
        """
        # Check for prompt.txt in files
        prompt_content, updated_files = self.handle_prompt_file(request.files)

        # If prompt.txt was found, incorporate it into the prompt
        if prompt_content:
            request.prompt = prompt_content + "\n\n" + request.prompt

        # Update request files list
        if updated_files is not None:
            request.files = updated_files

        # File size validation happens at MCP boundary in server.py

        # Check user input size at MCP transport boundary (before adding internal content)
        user_content = request.prompt
        size_check = self.check_prompt_size(user_content)
        if size_check:
            from tools.models import ToolOutput

            raise ValueError(f"MCP_SIZE_CHECK:{ToolOutput(**size_check).model_dump_json()}")

        # Also check focus_on field if provided (user input)
        if request.focus_on:
            focus_size_check = self.check_prompt_size(request.focus_on)
            if focus_size_check:
                from tools.models import ToolOutput

                raise ValueError(f"MCP_SIZE_CHECK:{ToolOutput(**focus_size_check).model_dump_json()}")

        # Use centralized file processing logic
        continuation_id = getattr(request, "continuation_id", None)
        file_content, processed_files = self._prepare_file_content_for_prompt(request.files, continuation_id, "Code")
        self._actually_processed_files = processed_files

        # Build customized review instructions based on review type
        review_focus = []
        if request.review_type == "security":
            review_focus.append("Focus on security vulnerabilities and authentication issues")
        elif request.review_type == "performance":
            review_focus.append("Focus on performance bottlenecks and optimization opportunities")
        elif request.review_type == "quick":
            review_focus.append("Provide a quick review focusing on critical issues only")

        # Add any additional focus areas specified by the user
        if request.focus_on:
            review_focus.append(f"Pay special attention to: {request.focus_on}")

        # Include custom coding standards if provided
        if request.standards:
            review_focus.append(f"Enforce these standards: {request.standards}")

        # Apply severity filtering to reduce noise if requested
        if request.severity_filter != "all":
            review_focus.append(f"Only report issues of {request.severity_filter} severity or higher")

        focus_instruction = "\n".join(review_focus) if review_focus else ""

        # Add web search instruction if enabled
        websearch_instruction = self.get_websearch_instruction(
            request.use_websearch,
            """When reviewing code, consider if searches for these would help:
- Security vulnerabilities and CVEs for libraries/frameworks used
- Best practices for the languages and frameworks in the code
- Common anti-patterns and their solutions
- Performance optimization techniques
- Recent updates or deprecations in APIs used""",
        )

        # Construct the complete prompt with system instructions and code
        full_prompt = f"""{self.get_system_prompt()}{websearch_instruction}

=== USER CONTEXT ===
{request.prompt}
=== END CONTEXT ===

{focus_instruction}

=== CODE TO REVIEW ===
{file_content}
=== END CODE ===

Please provide a code review aligned with the user's context and expectations, following the format specified """
        "in the system prompt." ""

        return full_prompt

    def format_response(self, response: str, request: CodeReviewRequest, model_info: Optional[dict] = None) -> str:
        """
        Format the review response.

        Args:
            response: The raw review from the model
            request: The original request for context
            model_info: Optional dict with model metadata

        Returns:
            str: Formatted response with next steps
        """
        return f"""{response}

---

**Your Next Steps:**

1. **Understand the Context**: First examine the specific functions, files, and code sections mentioned in """
        """the review to understand each issue thoroughly.

2. **Present Options to User**: After understanding the issues, ask the user which specific improvements """
        """they would like to implement, presenting them as a clear list of options.

3. **Implement Selected Fixes**: Only implement the fixes the user chooses, ensuring each change is made """
        """correctly and maintains code quality.

Remember: Always understand the code context before suggesting fixes, and let the user decide which """
        """improvements to implement."""
