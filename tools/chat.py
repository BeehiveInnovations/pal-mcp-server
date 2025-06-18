"""
Chat tool - General development chat and collaborative thinking
"""

from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_BALANCED
from systemprompts import CHAT_PROMPT

from .base import BaseTool, ToolRequest

# Field descriptions to avoid duplication between Pydantic and JSON schema
CHAT_FIELD_DESCRIPTIONS = {
    "prompt": (
        "You MUST provide a thorough, expressive question or share an idea with as much context as possible. "
        "Remember: you're talking to an assistant who has deep expertise and can provide nuanced insights. Include your "
        "current thinking, specific challenges, background context, what you've already tried, and what "
        "kind of response would be most helpful. The more context and detail you provide, the more "
        "valuable and targeted the response will be."
    ),
    "files": "Optional files for context (must be FULL absolute paths to real files / folders - DO NOT SHORTEN)",
    "images": (
        "Optional images for visual context. Useful for UI discussions, diagrams, visual problems, "
        "error screens, or architectural mockups. (must be FULL absolute paths to real files / folders - DO NOT SHORTEN - OR these can be bas64 data)"
    ),
}


class ChatRequest(ToolRequest):
    """Request model for chat tool"""

    prompt: str = Field(..., description=CHAT_FIELD_DESCRIPTIONS["prompt"])
    files: Optional[list[str]] = Field(default_factory=list, description=CHAT_FIELD_DESCRIPTIONS["files"])
    images: Optional[list[str]] = Field(default_factory=list, description=CHAT_FIELD_DESCRIPTIONS["images"])


class ChatTool(BaseTool):
    """General development chat and collaborative thinking tool"""

    def get_name(self) -> str:
        return "chat"

    def get_description(self) -> str:
        return (
            "GENERAL CHAT & COLLABORATIVE THINKING - Use the AI model as your thinking partner! "
            "Perfect for: bouncing ideas during your own analysis, getting second opinions on your plans, "
            "collaborative brainstorming, validating your checklists and approaches, exploring alternatives. "
            "Also great for: explanations, comparisons, general development questions. "
            "Use this when you want to ask questions, brainstorm ideas, get opinions, discuss topics, "
            "share your thinking, or need explanations about concepts and approaches. "
            "Note: If you're not currently using a top-tier model such as Opus 4 or above, these tools can "
            "provide enhanced capabilities."
        )

    def get_input_schema(self) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": CHAT_FIELD_DESCRIPTIONS["prompt"],
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CHAT_FIELD_DESCRIPTIONS["files"],
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CHAT_FIELD_DESCRIPTIONS["images"],
                },
                "model": self.get_model_field_schema(),
                "temperature": {
                    "type": "number",
                    "description": "Response creativity (0-1, default 0.5)",
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
                        "researching solutions to complex problems, or when current documentation and "
                        "community insights would enhance the analysis."
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
            "required": ["prompt"] + (["model"] if self.is_effective_auto_mode() else []),
        }

        return schema

    def get_system_prompt(self) -> str:
        return CHAT_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_BALANCED

    def get_model_category(self) -> "ToolModelCategory":
        """Chat prioritizes fast responses and cost efficiency"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.FAST_RESPONSE

    def get_request_model(self):
        return ChatRequest

    async def prepare_prompt(self, request: ChatRequest) -> str:
        """Prepare the chat prompt with optional context files"""
        # Check for prompt.txt in files
        prompt_content, updated_files = self.handle_prompt_file(request.files)

        # Use prompt.txt content if available, otherwise use the prompt field
        user_content = prompt_content if prompt_content else request.prompt

        # Check user input size at MCP transport boundary (before adding internal content)
        size_check = self.check_prompt_size(user_content)
        if size_check:
            # Need to return error, but prepare_prompt returns str
            # Use exception to handle this cleanly

            from tools.models import ToolOutput

            raise ValueError(f"MCP_SIZE_CHECK:{ToolOutput(**size_check).model_dump_json()}")

        # Update request files list
        if updated_files is not None:
            request.files = updated_files

        # Add context files if provided (using centralized file handling with filtering)
        if request.files:
            file_content, processed_files = self._prepare_file_content_for_prompt(
                request.files, request.continuation_id, "Context files"
            )
            self._actually_processed_files = processed_files
            if file_content:
                user_content = f"{user_content}\n\n=== CONTEXT FILES ===\n{file_content}\n=== END CONTEXT ===="

        # Check token limits
        self._validate_token_limit(user_content, "Content")

        # Add web search instruction if enabled
        websearch_instruction = self.get_websearch_instruction(
            request.use_websearch,
            """When discussing topics, consider if searches for these would help:
- Documentation for any technologies or concepts mentioned
- Current best practices and patterns
- Recent developments or updates
- Community discussions and solutions""",
        )

        # Combine system prompt with user content
        full_prompt = f"""{self.get_system_prompt()}{websearch_instruction}

=== USER REQUEST ===
{user_content}
=== END REQUEST ===

Please provide a thoughtful, comprehensive response:"""

        return full_prompt

    def format_response(self, response: str, request: ChatRequest, model_info: Optional[dict] = None) -> str:
        """Format the chat response"""
        return (
            f"{response}\n\n---\n\n**Claude's Turn:** Evaluate this perspective alongside your analysis to "
            "form a comprehensive solution and continue with the user's request and task at hand."
        )
