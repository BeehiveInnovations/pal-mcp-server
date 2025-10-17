"""
Challenge tool - Encourages critical thinking and thoughtful disagreement

This tool takes a user's statement and returns it wrapped in instructions that
encourage the CLI agent to challenge ideas and think critically before agreeing. It helps
avoid reflexive agreement by prompting deeper analysis and genuine evaluation.

This is a simple, self-contained tool that doesn't require AI model access.
"""

from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from tools.shared.base_models import ToolRequest
from tools.shared.exceptions import ToolExecutionError

from .simple.base import SimpleTool

# Field descriptions for the Challenge tool
CHALLENGE_FIELD_DESCRIPTIONS = {
    "prompt": (
        "Statement to scrutinize. If you invoke `challenge` manually, strip the word 'challenge' and pass just the statement. "
        "Automatic invocations send the full user message as-is; do not modify it."
    ),
}


class ChallengeRequest(ToolRequest):
    """Request model for Challenge tool"""

    prompt: str = Field(..., description=CHALLENGE_FIELD_DESCRIPTIONS["prompt"])


class ChallengeTool(SimpleTool):
    """
    Challenge tool for encouraging critical thinking and avoiding automatic agreement.

    This tool wraps user statements in instructions that encourage the CLI agent to:
    - Challenge ideas and think critically before responding
    - Evaluate whether they actually agree or disagree
    - Provide thoughtful analysis rather than reflexive agreement

    The tool is self-contained and doesn't require AI model access - it simply
    transforms the input prompt into a structured critical thinking challenge.
    """

    def get_name(self) -> str:
        return "challenge"

    def get_description(self) -> str:
        return (
            "Prevents reflexive agreement by forcing critical thinking and reasoned analysis when a statement is challenged. "
            "Trigger automatically when a user critically questions, disagrees or appears to push back on earlier answers, and use it manually to sanity-check contentious claims."
        )

    def get_system_prompt(self) -> str:
        # Challenge tool doesn't need a system prompt since it doesn't call AI
        return ""

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Challenge doesn't need a model category since it doesn't use AI"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.FAST_RESPONSE  # Default, but not used

    def requires_model(self) -> bool:
        """
        Challenge tool doesn't require model resolution at the MCP boundary.

        Like the planner tool, this is a pure data processing tool that transforms
        the input without calling external AI models.

        Returns:
            bool: False - challenge doesn't need AI model access
        """
        return False

    def get_request_model(self):
        """Return the Challenge-specific request model"""
        return ChallengeRequest

    def get_input_schema(self) -> dict[str, Any]:
        """
        Generate input schema for the challenge tool.

        Since this tool doesn't require a model, we exclude model-related fields.
        """
        schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": CHALLENGE_FIELD_DESCRIPTIONS["prompt"],
                },
            },
            "required": ["prompt"],
        }

        return schema

    async def execute(self, arguments: dict[str, Any]) -> list:
        """
        Execute the challenge tool by wrapping the prompt in critical thinking instructions.

        This is the main execution method that transforms the user's statement into
        a structured challenge that encourages thoughtful re-evaluation.
        """
        import json

        from mcp.types import TextContent

        try:
            # Validate request
            request = self.get_request_model()(**arguments)

            # Wrap the prompt in challenge instructions
            wrapped_prompt = self._wrap_prompt_for_challenge(request.prompt)

            # Return the wrapped prompt as the response
            response_data = {
                "status": "challenge_accepted",
                "original_statement": request.prompt,
                "challenge_prompt": wrapped_prompt,
                "instructions": (
                    "Present the challenge_prompt to yourself and follow its instructions. "
                    "Reassess the statement carefully and critically before responding. "
                    "If, after reflection, you find reasons to disagree or qualify it, explain your reasoning. "
                    "Likewise, if you find reasons to agree, articulate them clearly and justify your agreement."
                ),
            }

            return [TextContent(type="text", text=json.dumps(response_data, indent=2, ensure_ascii=False))]

        except ToolExecutionError:
            raise
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in challenge tool execution: {e}", exc_info=True)

            error_data = {
                "status": "error",
                "error": str(e),
                "content": f"Failed to create challenge prompt: {str(e)}",
            }

            raise ToolExecutionError(json.dumps(error_data, ensure_ascii=False)) from e

    def _wrap_prompt_for_challenge(self, prompt: str) -> str:
        """
        Wrap the user's statement in instructions that encourage critical challenge.

        Args:
            prompt: The original user statement to wrap

        Returns:
            The statement wrapped in challenge instructions
        """
        return (
            f"CRITICAL REASSESSMENT – Do not automatically agree:\n\n"
            f'"{prompt}"\n\n'
            f"Carefully evaluate the statement above. Is it accurate, complete, and well-reasoned? "
            f"Investigate if needed before replying, and stay focused. If you identify flaws, gaps, or misleading "
            f"points, explain them clearly. Likewise, if you find the reasoning sound, explain why it holds up. "
            f"Respond with thoughtful analysis—stay to the point and avoid reflexive agreement."
        )

    # Required method implementations from SimpleTool

    async def prepare_prompt(self, request: ChallengeRequest) -> str:
        """Not used since challenge doesn't call AI models"""
        return ""

    def format_response(self, response: str, request: ChallengeRequest, model_info: Optional[dict] = None) -> str:
        """Not used since challenge doesn't call AI models"""
        return response

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        """Tool-specific field definitions for Challenge"""
        return {
            "prompt": {
                "type": "string",
                "description": CHALLENGE_FIELD_DESCRIPTIONS["prompt"],
            },
        }

    def get_required_fields(self) -> list[str]:
        """Required fields for Challenge tool"""
        return ["prompt"]
