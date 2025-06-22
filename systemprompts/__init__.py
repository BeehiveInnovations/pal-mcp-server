"""
System prompts for Gemini tools
"""

from .analyze_prompt import ANALYZE_PROMPT
from .chat_prompt import CHAT_PROMPT
from .codereview_prompt import CODEREVIEW_PROMPT
from .consensus_prompt import CONSENSUS_PROMPT
from .debug_prompt import DEBUG_ISSUE_PROMPT
from .docgen_prompt import DOCGEN_PROMPT
from .planner_prompt import PLANNER_PROMPT
from .precommit_prompt import PRECOMMIT_PROMPT
from .refactor_prompt import REFACTOR_PROMPT
from .testgen_prompt import TESTGEN_PROMPT
from .thinkdeep_prompt import THINKDEEP_PROMPT
from .tracer_prompt import TRACER_PROMPT

__all__ = [
    "THINKDEEP_PROMPT",
    "CODEREVIEW_PROMPT",
    "DEBUG_ISSUE_PROMPT",
    "DOCGEN_PROMPT",
    "ANALYZE_PROMPT",
    "CHAT_PROMPT",
    "CONSENSUS_PROMPT",
    "PLANNER_PROMPT",
    "PRECOMMIT_PROMPT",
    "REFACTOR_PROMPT",
    "TESTGEN_PROMPT",
    "TRACER_PROMPT",
]
