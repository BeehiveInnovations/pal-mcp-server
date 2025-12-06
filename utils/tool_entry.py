"""
Shared tool entry point logic for MCP server and Skills mode.

This module provides unified pre-execution processing that ensures consistent
behavior between MCP server mode and Skills standalone mode.

DESIGN PRINCIPLE:
- MCP server mode imports and uses parse_model_option from this module
- Skills mode calls prepare_tool_arguments which uses the same functions
- Both modes share the same underlying utilities (model resolution, file validation, etc.)

This ensures that:
1. Tools behave identically regardless of invocation method
2. continuation_id works across both modes (via SQLite storage in Skills mode)
3. Model options (model:for, model:against) are parsed consistently
4. File size validation is applied uniformly
5. ModelContext is created and passed to tools

SINGLE SOURCE OF TRUTH:
- parse_model_option: Defined here, imported by server.py
- prepare_tool_arguments: Used by Skills mode
- reconstruct_thread_context_for_skills: Skills version of context reconstruction
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def parse_model_option(model_string: str) -> tuple[str, Optional[str]]:
    """
    Parse model:option format into model name and option.

    SINGLE SOURCE OF TRUTH: This function is the canonical implementation.
    server.py imports and uses this function directly.

    Handles different formats:
    - OpenRouter models: preserve :free, :beta, :preview suffixes as part of model name
    - Ollama/Custom models: split on : to extract tags like :latest
    - Consensus stance: extract options like :for, :against

    Args:
        model_string: String that may contain "model:option" format

    Returns:
        tuple: (model_name, option) where option may be None
    """
    if ":" in model_string and not model_string.startswith("http"):  # Avoid parsing URLs
        # Check if this looks like an OpenRouter model (contains /)
        if "/" in model_string and model_string.count(":") == 1:
            # Could be openai/gpt-4:something - check what comes after colon
            parts = model_string.split(":", 1)
            suffix = parts[1].strip().lower()

            # Known OpenRouter suffixes to preserve
            if suffix in ["free", "beta", "preview"]:
                return model_string.strip(), None

        # For other patterns (Ollama tags, consensus stances), split normally
        parts = model_string.split(":", 1)
        model_name = parts[0].strip()
        model_option = parts[1].strip() if len(parts) > 1 else None
        return model_name, model_option
    return model_string.strip(), None


async def prepare_tool_arguments(
    tool,
    arguments: dict[str, Any],
    tool_name: str,
    *,
    skip_continuation: bool = False,
) -> dict[str, Any]:
    """
    Prepare tool arguments with full pre-execution processing.

    This function replicates the logic from server.py handle_call_tool(),
    providing the same processing for Skills mode:

    1. continuation_id handling (thread context reconstruction)
    2. model:option parsing
    3. Model resolution (handles 'auto' mode)
    4. ModelContext creation
    5. File size validation

    Args:
        tool: The tool instance
        arguments: Raw input arguments from CLI/caller
        tool_name: Name of the tool being executed
        skip_continuation: If True, skip continuation_id processing (for testing)

    Returns:
        Enhanced arguments dict with:
        - _model_context: ModelContext instance
        - _resolved_model_name: Resolved model name
        - model: Updated with resolved model
        - (if continuation_id): Enhanced prompt with conversation history

    Raises:
        ValueError: For invalid continuation_id or unavailable models
        ToolExecutionError-like dict: For file size validation failures
    """
    from config import DEFAULT_MODEL
    from utils.model_resolution import ModelResolutionError, resolve_model

    enhanced_args = arguments.copy()

    # =========================================================================
    # 1. Handle continuation_id (thread context reconstruction)
    # =========================================================================
    if not skip_continuation and "continuation_id" in enhanced_args and enhanced_args["continuation_id"]:
        continuation_id = enhanced_args["continuation_id"]
        logger.debug(f"[SKILLS] Resuming conversation thread: {continuation_id}")
        enhanced_args = await reconstruct_thread_context_for_skills(enhanced_args, tool)

    # =========================================================================
    # 2. Parse model:option format
    # =========================================================================
    model_name = enhanced_args.get("model") or DEFAULT_MODEL
    model_name, model_option = parse_model_option(model_name)
    if model_option:
        logger.debug(f"[SKILLS] Parsed model format - model: '{model_name}', option: '{model_option}'")

    # =========================================================================
    # 3. Skip model resolution for tools that don't require models
    # =========================================================================
    if not tool.requires_model():
        logger.debug(f"[SKILLS] Tool {tool_name} doesn't require model - skipping model processing")
        return enhanced_args

    # =========================================================================
    # 4. Resolve model (handles 'auto' mode)
    # =========================================================================
    tool_category = tool.get_model_category()

    try:
        resolved_model = resolve_model(model_name, tool_category, tool_name=tool_name)
        enhanced_args["model"] = resolved_model
        logger.debug(f"[SKILLS] Resolved model: {resolved_model}")
    except ModelResolutionError:
        # Re-raise with context for caller to handle
        raise

    # =========================================================================
    # 5. Create ModelContext
    # =========================================================================
    from utils.model_context import ModelContext

    model_context = ModelContext(resolved_model, model_option)
    enhanced_args["_model_context"] = model_context
    enhanced_args["_resolved_model_name"] = resolved_model
    logger.debug(
        f"[SKILLS] ModelContext created for {resolved_model} "
        f"with {model_context.capabilities.context_window} token capacity"
    )
    if model_option:
        logger.debug(f"[SKILLS] Model option stored: '{model_option}'")

    # =========================================================================
    # 6. File size validation
    # =========================================================================
    from utils.file_utils import check_total_file_size

    argument_files = enhanced_args.get("absolute_file_paths")
    if argument_files:
        logger.debug(f"[SKILLS] Checking file sizes for {len(argument_files)} files")
        file_size_check = check_total_file_size(argument_files, resolved_model)
        if file_size_check:
            logger.warning(f"[SKILLS] File size check failed for {tool_name}")
            # Return error dict that caller should handle
            raise FileSizeExceededError(file_size_check)

    return enhanced_args


class FileSizeExceededError(Exception):
    """Raised when file sizes exceed the model's token limit."""

    def __init__(self, error_response: dict):
        self.error_response = error_response
        super().__init__(error_response.get("content", "File size exceeded"))


def _get_fallback_model(tool) -> Optional[str]:
    """
    Get a fallback model when the requested model is unavailable.

    This logic is shared between MCP server and Skills mode to ensure
    consistent fallback behavior.

    Args:
        tool: The tool instance (for model category resolution)

    Returns:
        Fallback model name, or None if no models are available
    """
    from providers.registry import ModelProviderRegistry

    fallback_model = None

    # First try to get a preferred fallback for the tool's category
    if tool is not None:
        try:
            fallback_model = ModelProviderRegistry.get_preferred_fallback_model(tool.get_model_category())
        except Exception:
            pass

    # If no category-specific fallback, use any available model
    if fallback_model is None:
        available_models = ModelProviderRegistry.get_available_model_names()
        if available_models:
            fallback_model = available_models[0]

    return fallback_model


async def reconstruct_thread_context_for_skills(
    arguments: dict[str, Any],
    tool,
) -> dict[str, Any]:
    """
    Reconstruct conversation context for Skills mode.

    This mirrors the reconstruct_thread_context function from server.py,
    adapted for Skills mode which uses SQLite storage for cross-process persistence.

    Args:
        arguments: Original arguments with continuation_id
        tool: The tool instance (for model category resolution)

    Returns:
        Enhanced arguments with conversation history embedded
    """
    from utils.conversation_memory import add_turn, build_conversation_history, get_thread
    from utils.follow_up import get_follow_up_instructions
    from utils.model_context import ModelContext

    continuation_id = arguments["continuation_id"]

    # Get thread context from storage (SQLite in Skills mode)
    logger.debug(f"[SKILLS] Looking up thread {continuation_id} in storage")
    context = get_thread(continuation_id)

    if not context:
        logger.warning(f"[SKILLS] Thread not found: {continuation_id}")
        raise ValueError(
            f"Conversation thread '{continuation_id}' was not found or has expired. "
            f"This may happen if the conversation was created more than 3 hours ago. "
            f"Please restart the conversation by providing your full question/prompt without the "
            f"continuation_id parameter."
        )

    # Add user's new input to the conversation
    user_prompt = arguments.get("prompt", "")
    if user_prompt:
        user_files = arguments.get("absolute_file_paths") or []
        logger.debug(f"[SKILLS] Adding user turn to thread {continuation_id}")
        success = add_turn(continuation_id, "user", user_prompt, files=user_files)
        if not success:
            logger.warning(f"[SKILLS] Failed to add user turn to thread {continuation_id}")

    # Determine if tool requires a model
    requires_model = tool.requires_model() if tool else True

    # Check if we should use the model from the previous conversation turn
    model_from_args = arguments.get("model")
    if requires_model and not model_from_args and context.turns:
        for turn in reversed(context.turns):
            if turn.role == "assistant" and turn.model_name:
                arguments["model"] = turn.model_name
                logger.debug(f"[SKILLS] Using model from previous turn: {turn.model_name}")
                break

    # Create model context for history building
    model_context = arguments.get("_model_context")

    if requires_model and model_context is None:
        try:
            model_context = ModelContext.from_arguments(arguments)
            arguments.setdefault("_resolved_model_name", model_context.model_name)
        except ValueError:
            # Fallback to any available model
            from providers.registry import ModelProviderRegistry

            fallback_model = _get_fallback_model(tool)

            if fallback_model is None:
                raise ValueError("No available models for conversation continuation")

            logger.debug(f"[SKILLS] Using fallback model '{fallback_model}' for context reconstruction")
            model_context = ModelContext(fallback_model)
            arguments["_model_context"] = model_context
            arguments["_resolved_model_name"] = fallback_model

    # Verify provider availability for the model (same as MCP server mode)
    # This ensures we don't fail later when trying to use an unavailable model
    if requires_model and model_context:
        from providers.registry import ModelProviderRegistry

        provider = ModelProviderRegistry.get_provider_for_model(model_context.model_name)
        if provider is None:
            # Model is not available, try to find a fallback
            fallback_model = _get_fallback_model(tool)

            if fallback_model is None:
                raise ValueError(
                    f"Conversation continuation failed: model '{model_context.model_name}' "
                    f"is not available with current API keys."
                )

            logger.debug(
                f"[SKILLS] Model '{model_context.model_name}' unavailable; "
                f"swapping to '{fallback_model}' for context reconstruction"
            )
            model_context = ModelContext(fallback_model)
            arguments["_model_context"] = model_context
            arguments["_resolved_model_name"] = fallback_model
    elif not requires_model and model_context is None:
        # Tool doesn't require model but we need one for context reconstruction
        from providers.registry import ModelProviderRegistry

        fallback_model = _get_fallback_model(tool)

        if fallback_model is None:
            raise ValueError(
                "Conversation continuation failed: no available models detected for context reconstruction."
            )

        logger.debug(
            f"[SKILLS] Using fallback model '{fallback_model}' for context reconstruction "
            f"of tool without model requirement"
        )
        model_context = ModelContext(fallback_model)
        arguments["_model_context"] = model_context
        arguments["_resolved_model_name"] = fallback_model

    # Build conversation history with model-specific limits
    logger.debug(f"[SKILLS] Building conversation history for thread {continuation_id}")
    conversation_history, conversation_tokens = build_conversation_history(context, model_context)
    logger.debug(f"[SKILLS] Conversation history built: {conversation_tokens:,} tokens")

    # Add follow-up instructions
    follow_up_instructions = get_follow_up_instructions(len(context.turns))

    # Merge conversation history with current prompt
    original_prompt = arguments.get("prompt", "")

    if conversation_history:
        enhanced_prompt = (
            f"{conversation_history}\n\n=== NEW USER INPUT ===\n{original_prompt}\n\n{follow_up_instructions}"
        )
    else:
        enhanced_prompt = f"{original_prompt}\n\n{follow_up_instructions}"

    # Build enhanced arguments
    enhanced_arguments = arguments.copy()
    enhanced_arguments["prompt"] = enhanced_prompt
    enhanced_arguments["_original_user_prompt"] = original_prompt

    # Calculate remaining token budget
    if model_context:
        token_allocation = model_context.calculate_token_allocation()
        remaining_tokens = token_allocation.content_tokens - conversation_tokens
        enhanced_arguments["_remaining_tokens"] = max(0, remaining_tokens)
        enhanced_arguments["_model_context"] = model_context

        logger.debug(f"[SKILLS] Token budget - remaining: {remaining_tokens:,}")

    # Merge initial context parameters
    if context.initial_context:
        for key, value in context.initial_context.items():
            if key not in enhanced_arguments and key not in ["temperature", "thinking_mode", "model"]:
                enhanced_arguments[key] = value

    logger.info(f"[SKILLS] Reconstructed context for thread {continuation_id} (turn {len(context.turns)})")

    return enhanced_arguments
