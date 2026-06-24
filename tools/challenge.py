"""
Challenge tool - Independent adversarial red-team review via Gemma

This tool takes a statement and submits it to an external Gemma model acting as an
adversarial red-team reviewer. The model actively tries to break the reasoning, exposes
weak assumptions, and identifies risks, then ends with a deterministic
`VERDICT: pass|fail|tie` line. Absent/malformed verdict defaults to fail (no silent pass).

TASK-20260624-560: this tool previously string-wrapped the prompt and never called any
model (requires_model()=False, custom execute() override). It now inherits
SimpleTool.execute() and makes a REAL Gemma call (26b primary, 31b cascade fallback via
the provider), matching what pal-mcp-protocol Rule 6.a has always claimed.
"""

from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from tools.shared.base_models import ToolRequest

from .simple.base import SimpleTool

# Field descriptions for the Challenge tool
CHALLENGE_FIELD_DESCRIPTIONS = {
    "prompt": (
        "Statement to scrutinize. If you invoke `challenge` manually, strip the word 'challenge' and pass just the statement. "
        "Automatic invocations send the full user message as-is; do not modify it."
    ),
}

# System prompt instructing Gemma to act as an adversarial red-team reviewer and to end
# its response with a single deterministic verdict line. Default-to-fail on uncertainty
# preserves the requirements-gate "no silent APPROVED" guarantee (TASK-20260624-560).
CHALLENGE_SYSTEM_PROMPT = """You are an adversarial red-team reviewer. Your job is to actively challenge the reasoning presented, find logical flaws, expose weak assumptions, and identify risks (technical correctness, completeness, edge cases, cascade risk, governance compliance).

Be a devil's advocate. Try hard to BREAK the argument. If you genuinely cannot find fatal flaws, say so — but look hard first.

After your critique, end your response with EXACTLY ONE line, and nothing after it:
VERDICT: pass
VERDICT: fail
VERDICT: tie

Use "pass" only when no material flaws remain, "fail" when material flaws are found, and "tie" when genuinely balanced. Default to VERDICT: fail if you are uncertain."""


class ChallengeRequest(ToolRequest):
    """Request model for Challenge tool"""

    prompt: str = Field(..., description=CHALLENGE_FIELD_DESCRIPTIONS["prompt"])


class ChallengeTool(SimpleTool):
    """
    Challenge tool for encouraging critical thinking and avoiding automatic agreement.

    This tool submits the statement to an external Gemma model acting as an adversarial
    red-team reviewer, which:
    - Actively challenges the reasoning and tries to break the argument
    - Exposes weak assumptions, edge cases, cascade risk, and governance gaps
    - Ends with a deterministic VERDICT: pass|fail|tie line (default fail on uncertainty)

    TASK-20260624-560: inherits SimpleTool.execute() and makes a REAL Gemma call. The
    prior self-contained string-wrap (requires_model()=False) is removed.
    """

    def get_name(self) -> str:
        return "challenge"

    def get_description(self) -> str:
        return (
            "Prevents reflexive agreement by forcing critical thinking and reasoned analysis when a statement is challenged. "
            "Trigger automatically when a user critically questions, disagrees or appears to push back on earlier answers, and use it manually to sanity-check contentious claims."
        )

    def get_system_prompt(self) -> str:
        # Adversarial red-team system prompt; forces a trailing VERDICT line (TASK-560).
        return CHALLENGE_SYSTEM_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Challenge needs thorough adversarial reasoning, like precommit/codereview."""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def requires_model(self) -> bool:
        """
        Challenge requires model resolution: it makes a REAL Gemma call via the inherited
        SimpleTool.execute() to perform an independent adversarial red-team review.

        TASK-20260624-560: was False (string-wrap, zero Gemma calls). Now True so the
        MCP boundary resolves a model context and the inherited execute() calls Gemma
        (26b primary, 31b cascade fallback handled at the provider level).

        Returns:
            bool: True - challenge calls an external AI model
        """
        return True

    def get_request_model(self):
        """Return the Challenge-specific request model"""
        return ChallengeRequest

    def get_input_schema(self) -> dict[str, Any]:
        """
        Generate input schema for the challenge tool.

        TASK-20260624-560: challenge now calls Gemma, so an OPTIONAL `model` field is
        exposed. It is intentionally NOT required — existing callers that pass only
        `prompt` keep working, and the inherited SimpleTool.execute() resolves
        DEFAULT_MODEL (gemma-4-26b-a4b-it) when `model` is omitted (base.py model
        fallback), so a real Gemma call always occurs.
        """
        schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": CHALLENGE_FIELD_DESCRIPTIONS["prompt"],
                },
                "model": self.get_model_field_schema(),
            },
            "required": ["prompt"],
        }

        return schema

    # NOTE (TASK-20260624-560): the former custom execute() override (a pure string-wrap
    # that never called Gemma) has been DELETED. ChallengeTool now inherits
    # SimpleTool.execute() (tools/simple/base.py), which performs the real Gemma call via
    # provider.generate_content using get_system_prompt() + prepare_prompt() below.

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
        """
        Build the user prompt for the Gemma red-team call.

        Wraps the statement in the proven critique framing, then runs it through
        build_standard_prompt() so the CHALLENGE_SYSTEM_PROMPT, web-search guidance,
        and any file context are assembled consistently with the other SimpleTools.
        The trailing VERDICT: line is enforced by the system prompt (TASK-560).
        """
        wrapped = self._wrap_prompt_for_challenge(request.prompt)
        return self.build_standard_prompt(self.get_system_prompt(), wrapped, request)

    def format_response(self, response: str, request: ChallengeRequest, model_info: Optional[dict] = None) -> str:
        """
        Return Gemma's full critique verbatim, including the trailing VERDICT: line.

        Callers normalize pass/fail/tie from the VERDICT line; absent/malformed verdict
        is treated as fail by the consumer (no silent APPROVED — TASK-560).
        """
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
