"""
Consensus tool for multi-model perspective gathering and validation
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Optional

from mcp.types import TextContent
from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import DEFAULT_CONSENSUS_MAX_INSTANCES_PER_COMBINATION
from systemprompts import CONSENSUS_PROMPT

from .base import BaseTool, ToolRequest

logger = logging.getLogger(__name__)

# Field descriptions to avoid duplication between Pydantic and JSON schema
CONSENSUS_FIELD_DESCRIPTIONS = {
    "prompt": (
        "Description of what to get consensus on, testing objectives, and specific scope/focus areas. "
        "Be as detailed as possible about the proposal, plan, or idea you want multiple perspectives on."
    ),
    "models": (
        "List of model configurations for consensus analysis. Each model can have a specific stance and custom instructions. "
        "Example: [{'model': 'o3', 'stance': 'for', 'stance_prompt': 'Focus on benefits and opportunities...'}, "
        "{'model': 'flash', 'stance': 'against', 'stance_prompt': 'Identify risks and challenges...'}]. "
        "Maximum 2 instances per model+stance combination."
    ),
    "files": "Optional files or directories for additional context (must be FULL absolute paths - DO NOT SHORTEN)",
    "images": (
        "Optional images showing expected UI changes, design requirements, "
        "or visual references for the consensus analysis"
    ),
    "focus_areas": "Specific aspects to focus on (e.g., 'performance', 'security', 'user experience')",
    "model_config_model": "Model name to use (e.g., 'o3', 'flash', 'pro')",
    "model_config_stance": (
        "Stance for this model. Supportive: 'for', 'support', 'favor'. "
        "Critical: 'against', 'oppose', 'critical'. Neutral: 'neutral'. "
        "Defaults to 'neutral'."
    ),
    "model_config_stance_prompt": (
        "Custom stance-specific instructions for this model. "
        "If provided, this will be used instead of the default stance prompt. "
        "Should be clear, specific instructions about how this model should approach the analysis."
    ),
    "model_config_stance_schema": "Stance for this model: supportive ('for', 'support', 'favor'), critical ('against', 'oppose', 'critical'), or 'neutral'",
}


class ModelConfig(BaseModel):
    """Enhanced model configuration for consensus tool"""

    model: str = Field(..., description=CONSENSUS_FIELD_DESCRIPTIONS["model_config_model"])
    stance: Optional[str] = Field(
        default="neutral",
        description=CONSENSUS_FIELD_DESCRIPTIONS["model_config_stance"],
    )
    stance_prompt: Optional[str] = Field(
        default=None,
        description=CONSENSUS_FIELD_DESCRIPTIONS["model_config_stance_prompt"],
    )


class ConsensusRequest(ToolRequest):
    """Request model for consensus tool"""

    prompt: str = Field(..., description=CONSENSUS_FIELD_DESCRIPTIONS["prompt"])
    models: list[ModelConfig] = Field(..., description=CONSENSUS_FIELD_DESCRIPTIONS["models"])
    files: Optional[list[str]] = Field(
        default_factory=list,
        description=CONSENSUS_FIELD_DESCRIPTIONS["files"],
    )
    images: Optional[list[str]] = Field(
        default_factory=list,
        description=CONSENSUS_FIELD_DESCRIPTIONS["images"],
    )
    focus_areas: Optional[list[str]] = Field(
        default_factory=list,
        description=CONSENSUS_FIELD_DESCRIPTIONS["focus_areas"],
    )

    @field_validator("models")
    @classmethod
    def validate_models_not_empty(cls, v):
        if not v:
            raise ValueError("At least one model must be specified")
        return v


class ConsensusTool(BaseTool):
    """Multi-model consensus tool for gathering diverse perspectives on technical proposals"""

    def __init__(self):
        super().__init__()

    def get_name(self) -> str:
        return "consensus"

    def get_description(self) -> str:
        return (
            "MULTI-MODEL CONSENSUS - Gather diverse perspectives from multiple AI models on technical proposals, "
            "plans, and ideas. Perfect for validation, feasibility assessment, and getting comprehensive "
            "viewpoints on complex decisions. Supports advanced stance steering with custom instructions for each model. "
            "You can specify different stances (for/against/neutral) and provide custom stance prompts to guide each "
            "model's analysis. Example: [{'model': 'o3', 'stance': 'for', 'stance_prompt': 'Focus on implementation "
            "benefits and user value'}, {'model': 'flash', 'stance': 'against', 'stance_prompt': 'Identify potential "
            "risks and technical challenges'}]. Use neutral stances by default unless structured debate would add value."
        )

    def get_input_schema(self) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["prompt"],
                },
                "models": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "model": {
                                "type": "string",
                                "description": CONSENSUS_FIELD_DESCRIPTIONS["model_config_model"],
                            },
                            "stance": {
                                "type": "string",
                                "enum": ["for", "support", "favor", "against", "oppose", "critical", "neutral"],
                                "description": CONSENSUS_FIELD_DESCRIPTIONS["model_config_stance_schema"],
                                "default": "neutral",
                            },
                            "stance_prompt": {
                                "type": "string",
                                "description": CONSENSUS_FIELD_DESCRIPTIONS["model_config_stance_prompt"],
                            },
                        },
                        "required": ["model"],
                    },
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["models"],
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["files"],
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["images"],
                },
                "focus_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["focus_areas"],
                },
                "temperature": {
                    "type": "number",
                    "description": "Temperature (0-1, default 0.2 for consistency)",
                    "minimum": 0,
                    "maximum": 1,
                    "default": self.get_default_temperature(),
                },
                "thinking_mode": {
                    "type": "string",
                    "enum": ["minimal", "low", "medium", "high", "max"],
                    "description": (
                        "Thinking depth: minimal (0.5% of model max), low (8%), medium (33%), "
                        "high (67%), max (100% of model max)"
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
            "required": ["prompt", "models"],
        }

        return schema

    def get_system_prompt(self) -> str:
        return CONSENSUS_PROMPT

    def get_default_temperature(self) -> float:
        return 0.2  # Lower temperature for more consistent consensus responses

    def get_model_category(self) -> "ToolModelCategory":
        """Consensus uses extended reasoning models for deep analysis"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_request_model(self):
        return ConsensusRequest

    def format_conversation_turn(self, turn) -> list[str]:
        """
        Format consensus turns with individual model responses for better readability.

        This custom formatting shows the individual model responses that were
        synthesized into the consensus, making it easier to understand the
        reasoning behind the final recommendation.
        """
        parts = []

        # Add files context if present
        if turn.files:
            parts.append(f"Files used in this turn: {', '.join(turn.files)}")
            parts.append("")

        # Check if this is a consensus turn with individual responses
        if turn.model_metadata and turn.model_metadata.get("individual_responses"):
            individual_responses = turn.model_metadata["individual_responses"]

            # Add consensus header
            models_consulted = []
            for resp in individual_responses:
                model = resp["model"]
                stance = resp.get("stance", "neutral")
                if stance != "neutral":
                    models_consulted.append(f"{model}:{stance}")
                else:
                    models_consulted.append(model)

            parts.append(f"Models consulted: {', '.join(models_consulted)}")
            parts.append("")
            parts.append("=== INDIVIDUAL MODEL RESPONSES ===")
            parts.append("")

            # Add each successful model response
            for i, response in enumerate(individual_responses):
                model_name = response["model"]
                stance = response.get("stance", "neutral")
                verdict = response["verdict"]

                stance_label = f"({stance.title()} Stance)" if stance != "neutral" else "(Neutral Analysis)"
                parts.append(f"**{model_name.upper()} {stance_label}**:")
                parts.append(verdict)

                if i < len(individual_responses) - 1:
                    parts.append("")
                    parts.append("---")
                parts.append("")

            parts.append("=== END INDIVIDUAL RESPONSES ===")
            parts.append("")
            parts.append("Claude's Synthesis:")

        # Add the actual content
        parts.append(turn.content)

        return parts

    def _normalize_stance(self, stance: Optional[str]) -> str:
        """Normalize stance to canonical form."""
        if not stance:
            return "neutral"

        stance = stance.lower()

        # Define stance synonyms
        supportive_stances = {"for", "support", "favor"}
        critical_stances = {"against", "oppose", "critical"}

        # Map synonyms to canonical stance
        if stance in supportive_stances:
            return "for"
        elif stance in critical_stances:
            return "against"
        elif stance == "neutral":
            return "neutral"
        else:
            # Unknown stances default to neutral for robustness
            logger.warning(
                f"Unknown stance '{stance}' provided, defaulting to 'neutral'. Valid stances: {', '.join(sorted(supportive_stances | critical_stances))}, or 'neutral'"
            )
            return "neutral"

    def _validate_model_combinations(self, model_configs: list[ModelConfig]) -> tuple[list[ModelConfig], list[str]]:
        """Validate model configurations and enforce limits.

        Returns:
            tuple: (valid_configs, skipped_entries)
            - Each model+stance combination can appear max 2 times
            - Same model+stance limited to 2 instances
        """
        valid_configs = []
        skipped_entries = []
        combination_counts = {}  # Track (model, stance) -> count

        for config in model_configs:
            try:
                # Normalize stance
                normalized_stance = self._normalize_stance(config.stance)

                # Create normalized config
                normalized_config = ModelConfig(
                    model=config.model, stance=normalized_stance, stance_prompt=config.stance_prompt
                )

                combination_key = (config.model, normalized_stance)
                current_count = combination_counts.get(combination_key, 0)

                if current_count >= DEFAULT_CONSENSUS_MAX_INSTANCES_PER_COMBINATION:
                    # Already have max instances of this model+stance combination
                    skipped_entries.append(
                        f"{config.model}:{normalized_stance} (max {DEFAULT_CONSENSUS_MAX_INSTANCES_PER_COMBINATION} instances)"
                    )
                    continue

                combination_counts[combination_key] = current_count + 1
                valid_configs.append(normalized_config)

            except ValueError as e:
                # Invalid stance or model
                skipped_entries.append(f"{config.model} ({str(e)})")
                continue

        return valid_configs, skipped_entries

    def _get_stance_enhanced_prompt(self, stance: str, custom_stance_prompt: Optional[str] = None) -> str:
        """Get the system prompt with stance injection based on the stance."""
        base_prompt = self.get_system_prompt()

        # If custom stance prompt is provided, use it instead of default
        if custom_stance_prompt:
            # Validate stance placeholder exists exactly once
            if base_prompt.count("{stance_prompt}") != 1:
                raise ValueError(
                    "System prompt must contain exactly one '{stance_prompt}' placeholder, "
                    f"found {base_prompt.count('{stance_prompt}')}"
                )
            return base_prompt.replace("{stance_prompt}", custom_stance_prompt)

        stance_prompts = {
            "for": """SUPPORTIVE PERSPECTIVE WITH INTEGRITY

You are tasked with advocating FOR this proposal, but with CRITICAL GUARDRAILS:

MANDATORY ETHICAL CONSTRAINTS:
- This is NOT a debate for entertainment. You MUST act in good faith and in the best interest of the questioner
- You MUST think deeply about whether supporting this idea is safe, sound, and passes essential requirements
- You MUST be direct and unequivocal in saying "this is a bad idea" when it truly is
- There must be at least ONE COMPELLING reason to be optimistic, otherwise DO NOT support it

WHEN TO REFUSE SUPPORT (MUST OVERRIDE STANCE):
- If the idea is fundamentally harmful to users, project, or stakeholders
- If implementation would violate security, privacy, or ethical standards
- If the proposal is technically infeasible within realistic constraints
- If costs/risks dramatically outweigh any potential benefits

YOUR SUPPORTIVE ANALYSIS SHOULD:
- Identify genuine strengths and opportunities
- Propose solutions to overcome legitimate challenges
- Highlight synergies with existing systems
- Suggest optimizations that enhance value
- Present realistic implementation pathways

Remember: Being "for" means finding the BEST possible version of the idea IF it has merit, not blindly supporting bad ideas.""",
            "against": """CRITICAL PERSPECTIVE WITH RESPONSIBILITY

You are tasked with critiquing this proposal, but with ESSENTIAL BOUNDARIES:

MANDATORY FAIRNESS CONSTRAINTS:
- You MUST NOT oppose genuinely excellent, common-sense ideas just to be contrarian
- You MUST acknowledge when a proposal is fundamentally sound and well-conceived
- You CANNOT give harmful advice or recommend against beneficial changes
- If the idea is outstanding, say so clearly while offering constructive refinements

WHEN TO MODERATE CRITICISM (MUST OVERRIDE STANCE):
- If the proposal addresses critical user needs effectively
- If it follows established best practices with good reason
- If benefits clearly and substantially outweigh risks
- If it's the obvious right solution to the problem

YOUR CRITICAL ANALYSIS SHOULD:
- Identify legitimate risks and failure modes
- Point out overlooked complexities
- Suggest more efficient alternatives
- Highlight potential negative consequences
- Question assumptions that may be flawed

Remember: Being "against" means rigorous scrutiny to ensure quality, not undermining good ideas that deserve support.""",
            "neutral": """BALANCED PERSPECTIVE

Provide objective analysis considering both positive and negative aspects. However, if there is overwhelming evidence
that the proposal clearly leans toward being exceptionally good or particularly problematic, you MUST accurately
reflect this reality. Being "balanced" means being truthful about the weight of evidence, not artificially creating
50/50 splits when the reality is 90/10.

Your analysis should:
- Present all significant pros and cons discovered
- Weight them according to actual impact and likelihood
- If evidence strongly favors one conclusion, clearly state this
- Provide proportional coverage based on the strength of arguments
- Help the questioner see the true balance of considerations

Remember: Artificial balance that misrepresents reality is not helpful. True balance means accurate representation
of the evidence, even when it strongly points in one direction.""",
        }

        stance_prompt = stance_prompts.get(stance, stance_prompts["neutral"])

        # Validate stance placeholder exists exactly once
        if base_prompt.count("{stance_prompt}") != 1:
            raise ValueError(
                "System prompt must contain exactly one '{stance_prompt}' placeholder, "
                f"found {base_prompt.count('{stance_prompt}')}"
            )

        # Inject stance into the system prompt
        return base_prompt.replace("{stance_prompt}", stance_prompt)

    def _get_single_response(
        self, provider, model_config: ModelConfig, prompt: str, request: ConsensusRequest
    ) -> dict[str, Any]:
        """Get response from a single model - synchronous method."""
        logger.debug(f"Getting response from {model_config.model} with stance '{model_config.stance}'")

        try:
            # Provider.generate_content is synchronous, not async
            response = provider.generate_content(
                prompt=prompt,
                model_name=model_config.model,
                system_prompt=self._get_stance_enhanced_prompt(model_config.stance, model_config.stance_prompt),
                temperature=getattr(request, "temperature", None) or self.get_default_temperature(),
                thinking_mode=getattr(request, "thinking_mode", "medium"),
                images=getattr(request, "images", None) or [],
            )
            return {
                "model": model_config.model,
                "stance": model_config.stance,
                "status": "success",
                "verdict": response.content,  # Contains structured Markdown
                "metadata": {
                    "provider": getattr(provider.get_provider_type(), "value", provider.get_provider_type()),
                    "usage": response.usage if hasattr(response, "usage") else None,
                    "custom_stance_prompt": bool(model_config.stance_prompt),
                },
            }
        except Exception as e:
            logger.error(f"Error getting response from {model_config.model}:{model_config.stance}: {str(e)}")
            return {"model": model_config.model, "stance": model_config.stance, "status": "error", "error": str(e)}

    def _get_consensus_responses(
        self, provider_configs: list[tuple], prompt: str, request: ConsensusRequest
    ) -> list[dict[str, Any]]:
        """Execute all model requests sequentially - purely synchronous like other tools."""

        logger.debug(f"Processing {len(provider_configs)} models sequentially")
        responses = []

        for i, (provider, model_config) in enumerate(provider_configs):
            try:
                logger.debug(
                    f"Processing {model_config.model}:{model_config.stance} sequentially ({i+1}/{len(provider_configs)})"
                )

                # Direct synchronous call - matches pattern of other tools
                response = self._get_single_response(provider, model_config, prompt, request)
                responses.append(response)

            except Exception as e:
                logger.error(f"Failed to get response from {model_config.model}:{model_config.stance}: {str(e)}")
                responses.append(
                    {
                        "model": model_config.model,
                        "stance": model_config.stance,
                        "status": "error",
                        "error": f"Unhandled exception: {str(e)}",
                    }
                )

        logger.debug(f"Sequential processing completed for {len(responses)} models")
        return responses

    def _format_consensus_output(self, responses: list[dict[str, Any]], skipped_entries: list[str]) -> str:
        """Format the consensus responses into structured output for Claude."""

        logger.debug(f"Formatting consensus output for {len(responses)} responses")

        # Separate successful and failed responses
        successful_responses = [r for r in responses if r["status"] == "success"]
        failed_responses = [r for r in responses if r["status"] == "error"]

        logger.debug(f"Successful responses: {len(successful_responses)}, Failed: {len(failed_responses)}")

        # Prepare the structured output (minimize size for MCP stability)
        models_used = [
            f"{r['model']}:{r['stance']}" if r["stance"] != "neutral" else r["model"] for r in successful_responses
        ]
        models_errored = [
            f"{r['model']}:{r['stance']}" if r["stance"] != "neutral" else r["model"] for r in failed_responses
        ]

        # Prepare clean responses without truncation
        clean_responses = []
        for r in responses:
            if r["status"] == "success":
                clean_responses.append(
                    {
                        "model": r["model"],
                        "stance": r["stance"],
                        "status": r["status"],
                        "verdict": r.get("verdict", ""),
                        "metadata": r.get("metadata", {}),
                    }
                )
            else:
                clean_responses.append(
                    {
                        "model": r["model"],
                        "stance": r["stance"],
                        "status": r["status"],
                        "error": r.get("error", "Unknown error"),
                    }
                )

        output_data = {
            "status": "consensus_success" if successful_responses else "consensus_failed",
            "models_used": models_used,
            "models_skipped": skipped_entries,
            "models_errored": models_errored,
            "responses": clean_responses,
            "next_steps": self._get_synthesis_guidance(successful_responses, failed_responses),
        }

        return json.dumps(output_data, indent=2)

    def _get_synthesis_guidance(
        self, successful_responses: list[dict[str, Any]], failed_responses: list[dict[str, Any]]
    ) -> str:
        """Generate guidance for Claude on how to synthesize the consensus results."""

        if not successful_responses:
            return (
                "No models provided successful responses. Please retry with different models or "
                "check the error messages for guidance on resolving the issues."
            )

        if len(successful_responses) == 1:
            return (
                "Only one model provided a successful response. Synthesize based on the available "
                "perspective and indicate areas where additional expert input would be valuable "
                "due to the limited consensus data."
            )

        # Multiple successful responses - provide comprehensive synthesis guidance
        stance_counts = {"for": 0, "against": 0, "neutral": 0}
        for resp in successful_responses:
            stance = resp.get("stance", "neutral")
            stance_counts[stance] = stance_counts.get(stance, 0) + 1

        guidance = (
            "Claude, synthesize these perspectives by first identifying the key points of "
            "**agreement** and **disagreement** between the models. Then provide your final, "
            "consolidated recommendation, explaining how you weighed the different opinions and "
            "why your proposed solution is the most balanced approach. Explicitly address the "
            "most critical risks raised by each model and provide actionable next steps for implementation."
        )

        if failed_responses:
            guidance += (
                f" Note: {len(failed_responses)} model(s) failed to respond - consider this "
                "partial consensus and indicate where additional expert input would strengthen the analysis."
            )

        return guidance

    async def prepare_prompt(self, request: ConsensusRequest) -> str:
        """Prepare the consensus prompt with context files and focus areas."""
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

        # Add focus areas if specified
        if request.focus_areas:
            focus_areas_text = "\n\nSpecific focus areas for this analysis:\n" + "\n".join(
                f"- {area}" for area in request.focus_areas
            )
            user_content += focus_areas_text

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

        return user_content

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Execute consensus gathering from multiple models."""

        # Store arguments for base class methods
        self._current_arguments = arguments

        # Validate and create request
        request = ConsensusRequest(**arguments)

        # Validate model configurations and enforce limits
        valid_configs, skipped_entries = self._validate_model_combinations(request.models)

        if not valid_configs:
            error_output = {
                "status": "consensus_failed",
                "error": "No valid model configurations after validation",
                "models_skipped": skipped_entries,
                "next_steps": "Please provide valid model configurations with proper model names and stance values.",
            }
            return [TextContent(type="text", text=json.dumps(error_output, indent=2))]

        # Set up a dummy model context for consensus since we handle multiple models
        # This is needed for base class methods like prepare_prompt to work
        if not hasattr(self, "_model_context") or not self._model_context:
            from utils.model_context import ModelContext

            # Use the first model as the representative for token calculations
            first_model = valid_configs[0].model if valid_configs else "flash"
            self._model_context = ModelContext(first_model)

        # Handle conversation continuation if specified
        if request.continuation_id:
            from utils.conversation_memory import build_conversation_history, get_thread

            thread_context = get_thread(request.continuation_id)
            if thread_context:
                # Build conversation history using the same pattern as other tools
                conversation_context, _ = build_conversation_history(thread_context, self._model_context)
                if conversation_context:
                    # Add conversation context to the beginning of the prompt
                    enhanced_prompt = f"{conversation_context}\n\n{request.prompt}"
                    request.prompt = enhanced_prompt

        # Prepare the consensus prompt
        consensus_prompt = await self.prepare_prompt(request)

        # Get providers for valid model configurations with caching to avoid duplicate lookups
        provider_configs = []
        provider_cache = {}  # Cache to avoid duplicate provider lookups

        for model_config in valid_configs:
            try:
                # Check cache first
                if model_config.model in provider_cache:
                    provider = provider_cache[model_config.model]
                else:
                    # Look up provider and cache it
                    provider = self.get_model_provider(model_config.model)
                    provider_cache[model_config.model] = provider

                provider_configs.append((provider, model_config))
            except Exception as e:
                # Track failed models
                model_display = (
                    f"{model_config.model}:{model_config.stance}"
                    if model_config.stance != "neutral"
                    else model_config.model
                )
                skipped_entries.append(f"{model_display} (provider not available: {str(e)})")

        if not provider_configs:
            error_output = {
                "status": "consensus_failed",
                "error": "No model providers available",
                "models_skipped": skipped_entries,
                "next_steps": "Please check that the specified models have configured API keys and are available.",
            }
            return [TextContent(type="text", text=json.dumps(error_output, indent=2))]

        # Send to all models sequentially (purely synchronous like other tools)
        logger.debug(f"Sending consensus request to {len(provider_configs)} models")
        responses = self._get_consensus_responses(provider_configs, consensus_prompt, request)
        logger.debug(f"Received {len(responses)} responses from consensus models")

        # Enforce minimum success requirement - must have at least 1 successful response
        successful_responses = [r for r in responses if r["status"] == "success"]
        if not successful_responses:
            error_output = {
                "status": "consensus_failed",
                "error": "All model calls failed - no successful responses received",
                "models_skipped": skipped_entries,
                "models_errored": [
                    f"{r['model']}:{r['stance']}" if r["stance"] != "neutral" else r["model"]
                    for r in responses
                    if r["status"] == "error"
                ],
                "next_steps": "Please retry with different models or check the error messages for guidance on resolving the issues.",
            }
            return [TextContent(type="text", text=json.dumps(error_output, indent=2))]

        logger.debug("About to format consensus output for MCP response")

        # Structure the output and store in conversation memory
        consensus_output = self._format_consensus_output(responses, skipped_entries)

        # Log response size for debugging
        output_size = len(consensus_output)
        logger.debug(f"Consensus output size: {output_size:,} characters")

        # Store in conversation memory if continuation_id is provided
        if request.continuation_id:
            self.store_conversation_turn(
                request.continuation_id,
                consensus_output,
                request.files,
                request.images,
                responses,  # Store individual responses in metadata
                skipped_entries,
            )

        return [TextContent(type="text", text=consensus_output)]

    def store_conversation_turn(
        self,
        continuation_id: str,
        output: str,
        files: list[str],
        images: list[str],
        responses: list[dict[str, Any]],
        skipped_entries: list[str],
    ):
        """Store consensus turn in conversation memory with special metadata."""
        from utils.conversation_memory import add_turn

        # Filter successful and failed responses
        successful_responses = [r for r in responses if r["status"] == "success"]
        failed_responses = [r for r in responses if r["status"] == "error"]

        # Prepare metadata for conversation storage
        metadata = {
            "tool_type": "consensus",
            "models_used": [r["model"] for r in successful_responses],
            "models_skipped": skipped_entries,
            "models_errored": [r["model"] for r in failed_responses],
            "individual_responses": successful_responses,  # Only store successful responses
        }

        # Store the turn with special consensus metadata - add_turn is synchronous
        add_turn(
            thread_id=continuation_id,
            role="assistant",
            content=output,
            files=files or [],
            images=images or [],
            tool_name="consensus",
            model_provider="consensus",  # Special provider name
            model_name="consensus",  # Special model name
            model_metadata=metadata,
        )
