"""
Core Tool Infrastructure for Zen MCP Tools

This module provides the fundamental base class for all tools:
- BaseTool: Abstract base class defining the tool interface

The BaseTool class defines the core contract that tools must implement and provides
common functionality for request validation, error handling, model management,
conversation handling, file processing, and response formatting.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from mcp.types import TextContent

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import MCP_PROMPT_SIZE_LIMIT
from providers import ModelProvider, ModelProviderRegistry
from utils import check_token_limit
from utils.conversation_memory import (
    ConversationTurn,
    get_conversation_file_list,
    get_thread,
)
from utils.file_utils import read_file_content, read_files

# Import models from tools.models for compatibility
try:
    from tools.models import SPECIAL_STATUS_MODELS, ContinuationOffer, ToolOutput
except ImportError:
    # Fallback in case models haven't been set up yet
    SPECIAL_STATUS_MODELS = {}
    ContinuationOffer = None
    ToolOutput = None

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Abstract base class for all Zen MCP tools.

    This class defines the interface that all tools must implement and provides
    common functionality for request handling, model creation, and response formatting.

    CONVERSATION-AWARE FILE PROCESSING:
    This base class implements the sophisticated dual prioritization strategy for
    conversation-aware file handling across all tools:

    1. FILE DEDUPLICATION WITH NEWEST-FIRST PRIORITY:
       - When same file appears in multiple conversation turns, newest reference wins
       - Prevents redundant file embedding while preserving most recent file state
       - Cross-tool file tracking ensures consistent behavior across analyze → codereview → debug

    2. CONVERSATION CONTEXT INTEGRATION:
       - All tools receive enhanced prompts with conversation history via reconstruct_thread_context()
       - File references from previous turns are preserved and accessible
       - Cross-tool knowledge transfer maintains full context without manual file re-specification

    3. TOKEN-AWARE FILE EMBEDDING:
       - Respects model-specific token allocation budgets from ModelContext
       - Prioritizes conversation history, then newest files, then remaining content
       - Graceful degradation when token limits are approached

    4. STATELESS-TO-STATEFUL BRIDGING:
       - Tools operate on stateless MCP requests but access full conversation state
       - Conversation memory automatically injected via continuation_id parameter
       - Enables natural AI-to-AI collaboration across tool boundaries

    To create a new tool:
    1. Create a new class that inherits from BaseTool
    2. Implement all abstract methods
    3. Define a request model that inherits from ToolRequest
    4. Register the tool in server.py's TOOLS dictionary
    """

    # Class-level cache for OpenRouter registry to avoid multiple loads
    _openrouter_registry_cache = None

    @classmethod
    def _get_openrouter_registry(cls):
        """Get cached OpenRouter registry instance, creating if needed."""
        # Use BaseTool class directly to ensure cache is shared across all subclasses
        if BaseTool._openrouter_registry_cache is None:
            from providers.openrouter_registry import OpenRouterModelRegistry

            BaseTool._openrouter_registry_cache = OpenRouterModelRegistry()
            logger.debug("Created cached OpenRouter registry instance")
        return BaseTool._openrouter_registry_cache

    def __init__(self):
        # Cache tool metadata at initialization to avoid repeated calls
        self.name = self.get_name()
        self.description = self.get_description()
        self.default_temperature = self.get_default_temperature()
        # Tool initialization complete

    @abstractmethod
    def get_name(self) -> str:
        """
        Return the unique name identifier for this tool.

        This name is used by MCP clients to invoke the tool and must be
        unique across all registered tools.

        Returns:
            str: The tool's unique name (e.g., "review_code", "analyze")
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        Return a detailed description of what this tool does.

        This description is shown to MCP clients (like Claude) to help them
        understand when and how to use the tool. It should be comprehensive
        and include trigger phrases.

        Returns:
            str: Detailed tool description with usage examples
        """
        pass

    @abstractmethod
    def get_input_schema(self) -> dict[str, Any]:
        """
        Return the JSON Schema that defines this tool's parameters.

        This schema is used by MCP clients to validate inputs before
        sending requests. It should match the tool's request model.

        Returns:
            Dict[str, Any]: JSON Schema object defining required and optional parameters
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Return the system prompt that configures the AI model's behavior.

        This prompt sets the context and instructions for how the model
        should approach the task. It's prepended to the user's request.

        Returns:
            str: System prompt with role definition and instructions
        """
        pass

    def requires_model(self) -> bool:
        """
        Return whether this tool requires AI model access.

        Tools that override execute() to do pure data processing (like planner)
        should return False to skip model resolution at the MCP boundary.

        Returns:
            bool: True if tool needs AI model access (default), False for data-only tools
        """
        return True

    def is_effective_auto_mode(self) -> bool:
        """
        Check if we're in effective auto mode for schema generation.

        This determines whether the model parameter should be required in the tool schema.
        Used at initialization time when schemas are generated.

        Returns:
            bool: True if model parameter should be required in the schema
        """
        from config import DEFAULT_MODEL
        from providers.registry import ModelProviderRegistry

        # Case 1: Explicit auto mode
        if DEFAULT_MODEL.lower() == "auto":
            return True

        # Case 2: Model not available (fallback to auto mode)
        if DEFAULT_MODEL.lower() != "auto":
            provider = ModelProviderRegistry.get_provider_for_model(DEFAULT_MODEL)
            if not provider:
                return True

        return False

    def _should_require_model_selection(self, model_name: str) -> bool:
        """
        Check if we should require Claude to select a model at runtime.

        This is called during request execution to determine if we need
        to return an error asking Claude to provide a model parameter.

        Args:
            model_name: The model name from the request or DEFAULT_MODEL

        Returns:
            bool: True if we should require model selection
        """
        # Case 1: Model is explicitly "auto"
        if model_name.lower() == "auto":
            return True

        # Case 2: Requested model is not available
        from providers.registry import ModelProviderRegistry

        provider = ModelProviderRegistry.get_provider_for_model(model_name)
        if not provider:
            logger = logging.getLogger(f"tools.{self.name}")
            logger.warning(f"Model '{model_name}' is not available with current API keys. Requiring model selection.")
            return True

        return False

    def _get_available_models(self) -> list[str]:
        """
        Get list of models available from enabled providers.

        Only returns models from providers that have valid API keys configured.
        This fixes the namespace collision bug where models from disabled providers
        were shown to Claude, causing routing conflicts.

        Returns:
            List of model names from enabled providers only
        """
        from providers.registry import ModelProviderRegistry

        # Get models from enabled providers only (those with valid API keys)
        all_models = ModelProviderRegistry.get_available_model_names()

        # Add OpenRouter models if OpenRouter is configured
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key and openrouter_key != "your_openrouter_api_key_here":
            try:
                registry = self._get_openrouter_registry()
                # Add all aliases from the registry (includes OpenRouter cloud models)
                for alias in registry.list_aliases():
                    if alias not in all_models:
                        all_models.append(alias)
            except Exception as e:
                import logging

                logging.debug(f"Failed to add OpenRouter models to enum: {e}")

        # Add custom models if custom API is configured
        custom_url = os.getenv("CUSTOM_API_URL")
        if custom_url:
            try:
                registry = self._get_openrouter_registry()
                # Find all custom models (is_custom=true)
                for alias in registry.list_aliases():
                    config = registry.resolve(alias)
                    # Check if this is a custom model that requires custom endpoints
                    if config and config.is_custom:
                        if alias not in all_models:
                            all_models.append(alias)
            except Exception as e:
                import logging

                logging.debug(f"Failed to add custom models to enum: {e}")

        # Remove duplicates while preserving order
        seen = set()
        unique_models = []
        for model in all_models:
            if model not in seen:
                seen.add(model)
                unique_models.append(model)

        return unique_models

    def get_model_field_schema(self) -> dict[str, Any]:
        """
        Generate the model field schema based on auto mode configuration.

        When auto mode is enabled, the model parameter becomes required
        and includes detailed descriptions of each model's capabilities.

        Returns:
            Dict containing the model field JSON schema
        """
        import os

        from config import DEFAULT_MODEL

        # Check if OpenRouter is configured
        has_openrouter = bool(
            os.getenv("OPENROUTER_API_KEY") and os.getenv("OPENROUTER_API_KEY") != "your_openrouter_api_key_here"
        )

        # Use the centralized effective auto mode check
        if self.is_effective_auto_mode():
            # In auto mode, model is required and we provide detailed descriptions
            model_desc_parts = [
                "IMPORTANT: Use the model specified by the user if provided, OR select the most suitable model "
                "for this specific task based on the requirements and capabilities listed below:"
            ]

            # Get descriptions from enabled providers
            from providers.base import ProviderType
            from providers.registry import ModelProviderRegistry

            # Map provider types to readable names
            provider_names = {
                ProviderType.GOOGLE: "Gemini models",
                ProviderType.OPENAI: "OpenAI models",
                ProviderType.XAI: "X.AI GROK models",
                ProviderType.DIAL: "DIAL models",
                ProviderType.CUSTOM: "Custom models",
                ProviderType.OPENROUTER: "OpenRouter models",
            }

            # Check available providers and add their model descriptions

            # Start with native providers
            for provider_type in [ProviderType.GOOGLE, ProviderType.OPENAI, ProviderType.XAI, ProviderType.DIAL]:
                # Only if this is registered / available
                provider = ModelProviderRegistry.get_provider(provider_type)
                if provider:
                    provider_section_added = False
                    for model_name in provider.list_models(respect_restrictions=True):
                        try:
                            # Get model config to extract description
                            model_config = provider.SUPPORTED_MODELS.get(model_name)
                            if model_config and model_config.description:
                                if not provider_section_added:
                                    model_desc_parts.append(
                                        f"\n{provider_names[provider_type]} - Available when {provider_type.value.upper()}_API_KEY is configured:"
                                    )
                                    provider_section_added = True
                                model_desc_parts.append(f"- '{model_name}': {model_config.description}")
                        except Exception:
                            # Skip models without descriptions
                            continue

            # Add custom models if custom API is configured
            custom_url = os.getenv("CUSTOM_API_URL")
            if custom_url:
                # Load custom models from registry
                try:
                    registry = self._get_openrouter_registry()
                    model_desc_parts.append(f"\nCustom models via {custom_url}:")

                    # Find all custom models (is_custom=true)
                    for alias in registry.list_aliases():
                        config = registry.resolve(alias)
                        # Check if this is a custom model that requires custom endpoints
                        if config and config.is_custom:
                            # Format context window
                            context_tokens = config.context_window
                            if context_tokens >= 1_000_000:
                                context_str = f"{context_tokens // 1_000_000}M"
                            elif context_tokens >= 1_000:
                                context_str = f"{context_tokens // 1_000}K"
                            else:
                                context_str = str(context_tokens)

                            desc_line = f"- '{alias}' ({context_str} context): {config.description}"
                            if desc_line not in model_desc_parts:  # Avoid duplicates
                                model_desc_parts.append(desc_line)
                except Exception as e:
                    import logging

                    logging.debug(f"Failed to load custom model descriptions: {e}")
                    model_desc_parts.append(f"\nCustom models: Models available via {custom_url}")

            if has_openrouter:
                # Add OpenRouter models with descriptions
                try:
                    import logging

                    registry = self._get_openrouter_registry()

                    # Group models by their model_name to avoid duplicates
                    seen_models = set()
                    model_configs = []

                    for alias in registry.list_aliases():
                        config = registry.resolve(alias)
                        if config and config.model_name not in seen_models:
                            seen_models.add(config.model_name)
                            model_configs.append((alias, config))

                    # Sort by context window (descending) then by alias
                    model_configs.sort(key=lambda x: (-x[1].context_window, x[0]))

                    if model_configs:
                        model_desc_parts.append("\nOpenRouter models (use these aliases):")
                        for alias, config in model_configs:  # Show ALL models so Claude can choose
                            # Format context window in human-readable form
                            context_tokens = config.context_window
                            if context_tokens >= 1_000_000:
                                context_str = f"{context_tokens // 1_000_000}M"
                            elif context_tokens >= 1_000:
                                context_str = f"{context_tokens // 1_000}K"
                            else:
                                context_str = str(context_tokens)

                            # Build description line
                            if config.description:
                                desc = f"- '{alias}' ({context_str} context): {config.description}"
                            else:
                                # Fallback to showing the model name if no description
                                desc = f"- '{alias}' ({context_str} context): {config.model_name}"
                            model_desc_parts.append(desc)

                        # Show all models - no truncation needed
                except Exception as e:
                    # Log for debugging but don't fail
                    import logging

                    logging.debug(f"Failed to load OpenRouter model descriptions: {e}")
                    # Fallback to simple message
                    model_desc_parts.append(
                        "\nOpenRouter models: If configured, you can also use ANY model available on OpenRouter."
                    )

            # Get all available models for the enum
            all_models = self._get_available_models()

            return {
                "type": "string",
                "description": "\n".join(model_desc_parts),
                "enum": all_models,
            }
        else:
            # Normal mode - model is optional with default
            available_models = self._get_available_models()
            models_str = ", ".join(f"'{m}'" for m in available_models)  # Show ALL models so Claude can choose

            description = f"Model to use. Native models: {models_str}."
            if has_openrouter:
                # Add OpenRouter aliases
                try:
                    registry = self._get_openrouter_registry()
                    aliases = registry.list_aliases()

                    # Show ALL aliases from the configuration
                    if aliases:
                        # Show all aliases so Claude knows every option available
                        all_aliases = sorted(aliases)
                        alias_list = ", ".join(f"'{a}'" for a in all_aliases)
                        description += f" OpenRouter aliases: {alias_list}."
                    else:
                        description += " OpenRouter: Any model available on openrouter.ai."
                except Exception:
                    description += (
                        " OpenRouter: Any model available on openrouter.ai "
                        "(e.g., 'gpt-4', 'claude-4-opus', 'mistral-large')."
                    )
            description += f" Defaults to '{DEFAULT_MODEL}' if not specified."

            return {
                "type": "string",
                "description": description,
            }

    def get_default_temperature(self) -> float:
        """
        Return the default temperature setting for this tool.

        Override this method to set tool-specific temperature defaults.
        Lower values (0.0-0.3) for analytical tasks, higher (0.7-1.0) for creative tasks.

        Returns:
            float: Default temperature between 0.0 and 1.0
        """
        return 0.5

    def wants_line_numbers_by_default(self) -> bool:
        """
        Return whether this tool wants line numbers added to code files by default.

        By default, ALL tools get line numbers for precise code references.
        Line numbers are essential for accurate communication about code locations.

        Returns:
            bool: True if line numbers should be added by default for this tool
        """
        return True  # All tools get line numbers by default for consistency

    def get_default_thinking_mode(self) -> str:
        """
        Return the default thinking mode for this tool.

        Thinking mode controls computational budget for reasoning.
        Override for tools that need more or less reasoning depth.

        Returns:
            str: One of "minimal", "low", "medium", "high", "max"
        """
        return "medium"  # Default to medium thinking for better reasoning

    def get_model_category(self) -> "ToolModelCategory":
        """
        Return the model category for this tool.

        Model category influences which model is selected in auto mode.
        Override to specify whether your tool needs extended reasoning,
        fast response, or balanced capabilities.

        Returns:
            ToolModelCategory: Category that influences model selection
        """
        from tools.models import ToolModelCategory

        return ToolModelCategory.BALANCED

    @abstractmethod
    def get_request_model(self):
        """
        Return the Pydantic model class used for validating requests.

        This model should inherit from ToolRequest and define all
        parameters specific to this tool.

        Returns:
            Type[ToolRequest]: The request model class
        """
        pass

    def validate_file_paths(self, request) -> Optional[str]:
        """
        Validate that all file paths in the request are absolute.

        This is a critical security function that prevents path traversal attacks
        and ensures all file access is properly controlled. All file paths must
        be absolute to avoid ambiguity and security issues.

        Args:
            request: The validated request object

        Returns:
            Optional[str]: Error message if validation fails, None if all paths are valid
        """
        # Only validate files/paths if they exist in the request
        file_fields = [
            "files",
            "file",
            "path",
            "directory",
            "notebooks",
            "test_examples",
            "style_guide_examples",
            "files_checked",
            "relevant_files",
        ]

        for field_name in file_fields:
            if hasattr(request, field_name):
                field_value = getattr(request, field_name)
                if field_value is None:
                    continue

                # Handle both single paths and lists of paths
                paths_to_check = field_value if isinstance(field_value, list) else [field_value]

                for path in paths_to_check:
                    if path and not os.path.isabs(path):
                        return f"All file paths must be FULL absolute paths. Invalid path: '{path}'"

        return None

    def _validate_token_limit(self, content: str, content_type: str = "Content") -> None:
        """
        Validate that content doesn't exceed the MCP prompt size limit.

        Args:
            content: The content to validate
            content_type: Description of the content type for error messages

        Raises:
            ValueError: If content exceeds size limit
        """
        is_valid, token_count = check_token_limit(content, MCP_PROMPT_SIZE_LIMIT)
        if not is_valid:
            error_msg = f"~{token_count:,} tokens. Maximum is {MCP_PROMPT_SIZE_LIMIT:,} tokens."
            logger.error(f"{self.name} tool {content_type.lower()} validation failed: {error_msg}")
            raise ValueError(f"{content_type} too large: {error_msg}")

        logger.debug(f"{self.name} tool {content_type.lower()} token validation passed: {token_count:,} tokens")

    def get_model_provider(self, model_name: str) -> ModelProvider:
        """
        Get the appropriate model provider for the given model name.

        This method performs runtime validation to ensure the requested model
        is actually available with the current API key configuration.

        Args:
            model_name: Name of the model to get provider for

        Returns:
            ModelProvider: The provider instance for the model

        Raises:
            ValueError: If the model is not available or provider not found
        """
        try:
            provider = ModelProviderRegistry.get_provider_for_model(model_name)
            if not provider:
                logger.error(f"No provider found for model '{model_name}' in {self.name} tool")
                available_models = ModelProviderRegistry.get_available_models()
                raise ValueError(f"Model '{model_name}' is not available. Available models: {available_models}")

            return provider
        except Exception as e:
            logger.error(f"Failed to get provider for model '{model_name}' in {self.name} tool: {e}")
            raise

    # === CONVERSATION AND FILE HANDLING METHODS ===

    def get_conversation_embedded_files(self, continuation_id: Optional[str]) -> list[str]:
        """
        Get list of files already embedded in conversation history.

        This method returns the list of files that have already been embedded
        in the conversation history for a given continuation thread. Tools can
        use this to avoid re-embedding files that are already available in the
        conversation context.

        Args:
            continuation_id: Thread continuation ID, or None for new conversations

        Returns:
            list[str]: List of file paths already embedded in conversation history
        """
        if not continuation_id:
            # New conversation, no files embedded yet
            return []

        thread_context = get_thread(continuation_id)
        if not thread_context:
            # Thread not found, no files embedded
            return []

        embedded_files = get_conversation_file_list(thread_context)
        logger.debug(f"[FILES] {self.name}: Found {len(embedded_files)} embedded files")
        return embedded_files

    def filter_new_files(self, requested_files: list[str], continuation_id: Optional[str]) -> list[str]:
        """
        Filter out files that are already embedded in conversation history.

        This method prevents duplicate file embeddings by filtering out files that have
        already been embedded in the conversation history. This optimizes token usage
        while ensuring tools still have logical access to all requested files through
        conversation history references.

        Args:
            requested_files: List of files requested for current tool execution
            continuation_id: Thread continuation ID, or None for new conversations

        Returns:
            list[str]: List of files that need to be embedded (not already in history)
        """
        logger.debug(f"[FILES] {self.name}: Filtering {len(requested_files)} requested files")

        if not continuation_id:
            # New conversation, all files are new
            logger.debug(f"[FILES] {self.name}: New conversation, all {len(requested_files)} files are new")
            return requested_files

        try:
            embedded_files = set(self.get_conversation_embedded_files(continuation_id))
            logger.debug(f"[FILES] {self.name}: Found {len(embedded_files)} embedded files in conversation")

            # Safety check: If no files are marked as embedded but we have a continuation_id,
            # this might indicate an issue with conversation history. Be conservative.
            if not embedded_files:
                logger.debug(f"{self.name} tool: No files found in conversation history for thread {continuation_id}")
                logger.debug(
                    f"[FILES] {self.name}: No embedded files found, returning all {len(requested_files)} requested files"
                )
                return requested_files

            # Return only files that haven't been embedded yet
            new_files = [f for f in requested_files if f not in embedded_files]
            logger.debug(
                f"[FILES] {self.name}: After filtering: {len(new_files)} new files, {len(requested_files) - len(new_files)} already embedded"
            )
            logger.debug(f"[FILES] {self.name}: New files to embed: {new_files}")

            # Log filtering results for debugging
            if len(new_files) < len(requested_files):
                skipped = [f for f in requested_files if f in embedded_files]
                logger.debug(
                    f"{self.name} tool: Filtering {len(skipped)} files already in conversation history: {', '.join(skipped)}"
                )
                logger.debug(f"[FILES] {self.name}: Skipped (already embedded): {skipped}")

            return new_files

        except Exception as e:
            # If there's any issue with conversation history lookup, be conservative
            # and include all files rather than risk losing access to needed files
            logger.warning(f"{self.name} tool: Error checking conversation history for {continuation_id}: {e}")
            logger.warning(f"{self.name} tool: Including all requested files as fallback")
            logger.debug(
                f"[FILES] {self.name}: Exception in filter_new_files, returning all {len(requested_files)} files as fallback"
            )
            return requested_files

    def format_conversation_turn(self, turn: ConversationTurn) -> list[str]:
        """
        Format a conversation turn for display in conversation history.

        Tools can override this to provide custom formatting for their responses
        while maintaining the standard structure for cross-tool compatibility.

        This method is called by build_conversation_history when reconstructing
        conversation context, allowing each tool to control how its responses
        appear in subsequent conversation turns.

        Args:
            turn: The conversation turn to format (from utils.conversation_memory)

        Returns:
            list[str]: Lines of formatted content for this turn

        Example:
            Default implementation returns:
            ["Files used in this turn: file1.py, file2.py", "", "Response content..."]

            Tools can override to add custom sections, formatting, or metadata display.
        """
        parts = []

        # Add files context if present
        if turn.files:
            parts.append(f"Files used in this turn: {', '.join(turn.files)}")
            parts.append("")  # Empty line for readability

        # Add the actual content
        parts.append(turn.content)

        return parts

    def handle_prompt_file(self, files: Optional[list[str]]) -> tuple[Optional[str], Optional[list[str]]]:
        """
        Check for and handle prompt.txt in the files list.

        If prompt.txt is found, reads its content and removes it from the files list.
        This file is treated specially as the main prompt, not as an embedded file.

        This mechanism allows us to work around MCP's ~25K token limit by having
        Claude save large prompts to a file, effectively using the file transfer
        mechanism to bypass token constraints while preserving response capacity.

        Args:
            files: List of file paths (will be translated for current environment)

        Returns:
            tuple: (prompt_content, updated_files_list)
        """
        if not files:
            return None, files

        prompt_content = None
        updated_files = []

        for file_path in files:

            # Check if the filename is exactly "prompt.txt"
            # This ensures we don't match files like "myprompt.txt" or "prompt.txt.bak"
            if os.path.basename(file_path) == "prompt.txt":
                try:
                    # Read prompt.txt content and extract just the text
                    content, _ = read_file_content(file_path)
                    # Extract the content between the file markers
                    if "--- BEGIN FILE:" in content and "--- END FILE:" in content:
                        lines = content.split("\n")
                        in_content = False
                        content_lines = []
                        for line in lines:
                            if line.startswith("--- BEGIN FILE:"):
                                in_content = True
                                continue
                            elif line.startswith("--- END FILE:"):
                                break
                            elif in_content:
                                content_lines.append(line)
                        prompt_content = "\n".join(content_lines)
                    else:
                        # Fallback: if it's already raw content (from tests or direct input)
                        # and doesn't have error markers, use it directly
                        if not content.startswith("\n--- ERROR"):
                            prompt_content = content
                        else:
                            prompt_content = None
                except Exception:
                    # If we can't read the file, we'll just skip it
                    # The error will be handled elsewhere
                    pass
            else:
                # Keep the original path in the files list (will be translated later by read_files)
                updated_files.append(file_path)

        return prompt_content, updated_files if updated_files else None

    def get_prompt_content_for_size_validation(self, user_content: str) -> str:
        """
        Get the content that should be validated for MCP prompt size limits.

        This hook method allows tools to specify what content should be checked
        against the MCP transport size limit. By default, it returns the user content,
        but can be overridden to exclude conversation history when needed.

        Args:
            user_content: The user content that would normally be validated

        Returns:
            The content that should actually be validated for size limits
        """
        # Default implementation: validate the full user content
        return user_content

    def check_prompt_size(self, text: str) -> Optional[dict[str, Any]]:
        """
        Check if USER INPUT text is too large for MCP transport boundary.

        IMPORTANT: This method should ONLY be used to validate user input that crosses
        the Claude CLI ↔ MCP Server transport boundary. It should NOT be used to limit
        internal MCP Server operations.

        Args:
            text: The user input text to check (NOT internal prompt content)

        Returns:
            Optional[Dict[str, Any]]: Response asking for file handling if too large, None otherwise
        """
        if text and len(text) > MCP_PROMPT_SIZE_LIMIT:
            return {
                "status": "resend_prompt",
                "content": (
                    f"MANDATORY ACTION REQUIRED: The prompt is too large for MCP's token limits (>{MCP_PROMPT_SIZE_LIMIT:,} characters). "
                    "YOU MUST IMMEDIATELY save the prompt text to a temporary file named 'prompt.txt' in the working directory. "
                    "DO NOT attempt to shorten or modify the prompt. SAVE IT AS-IS to 'prompt.txt'. "
                    "Then resend the request with the absolute file path to 'prompt.txt' in the files parameter (must be FULL absolute path - DO NOT SHORTEN), "
                    "along with any other files you wish to share as context. Leave the prompt text itself empty or very brief in the new request. "
                    "This is the ONLY way to handle large prompts - you MUST follow these exact steps."
                ),
                "content_type": "text",
                "metadata": {
                    "prompt_size": len(text),
                    "limit": MCP_PROMPT_SIZE_LIMIT,
                    "instructions": "MANDATORY: Save prompt to 'prompt.txt' in current folder and include absolute path in files parameter. DO NOT modify or shorten the prompt.",
                },
            }
        return None

    def _prepare_file_content_for_prompt(
        self,
        request_files: list[str],
        continuation_id: Optional[str],
        context_description: str = "New files",
        max_tokens: Optional[int] = None,
        reserve_tokens: int = 1_000,
        remaining_budget: Optional[int] = None,
        arguments: Optional[dict] = None,
        model_context: Optional[Any] = None,
    ) -> tuple[str, list[str]]:
        """
        Centralized file processing implementing dual prioritization strategy.

        This method is the heart of conversation-aware file processing across all tools.

        Args:
            request_files: List of files requested for current tool execution
            continuation_id: Thread continuation ID, or None for new conversations
            context_description: Description for token limit validation (e.g. "Code", "New files")
            max_tokens: Maximum tokens to use (defaults to remaining budget or model-specific content allocation)
            reserve_tokens: Tokens to reserve for additional prompt content (default 1K)
            remaining_budget: Remaining token budget after conversation history (from server.py)
            arguments: Original tool arguments (used to extract _remaining_tokens if available)
            model_context: Model context object with all model information including token allocation

        Returns:
            tuple[str, list[str]]: (formatted_file_content, actually_processed_files)
                - formatted_file_content: Formatted file content string ready for prompt inclusion
                - actually_processed_files: List of individual file paths that were actually read and embedded
                  (directories are expanded to individual files)
        """
        if not request_files:
            return "", []

        # Extract remaining budget from arguments if available
        if remaining_budget is None:
            # Use provided arguments or fall back to stored arguments from execute()
            args_to_use = arguments or getattr(self, "_current_arguments", {})
            remaining_budget = args_to_use.get("_remaining_tokens")

        # Use remaining budget if provided, otherwise fall back to max_tokens or model-specific default
        if remaining_budget is not None:
            effective_max_tokens = remaining_budget - reserve_tokens
        elif max_tokens is not None:
            effective_max_tokens = max_tokens - reserve_tokens
        else:
            # Use model_context for token allocation
            if not model_context:
                # Try to get from stored attributes as fallback
                model_context = getattr(self, "_model_context", None)
                if not model_context:
                    logger.error(
                        f"[FILES] {self.name}: _prepare_file_content_for_prompt called without model_context. "
                        "This indicates an incorrect call sequence in the tool's implementation."
                    )
                    raise RuntimeError("Model context not provided for file preparation.")

            # This is now the single source of truth for token allocation.
            try:
                token_allocation = model_context.calculate_token_allocation()
                # Standardize on `file_tokens` for consistency and correctness.
                effective_max_tokens = token_allocation.file_tokens - reserve_tokens
                logger.debug(
                    f"[FILES] {self.name}: Using model context for {model_context.model_name}: "
                    f"{token_allocation.file_tokens:,} file tokens from {token_allocation.total_tokens:,} total"
                )
            except Exception as e:
                logger.error(
                    f"[FILES] {self.name}: Failed to calculate token allocation from model context: {e}", exc_info=True
                )
                # If the context exists but calculation fails, we still need to prevent a crash.
                # A loud error is logged, and we fall back to a safe default.
                effective_max_tokens = 100_000 - reserve_tokens

        # Ensure we have a reasonable minimum budget
        effective_max_tokens = max(1000, effective_max_tokens)

        files_to_embed = self.filter_new_files(request_files, continuation_id)
        logger.debug(f"[FILES] {self.name}: Will embed {len(files_to_embed)} files after filtering")

        # Log the specific files for debugging/testing
        if files_to_embed:
            logger.info(
                f"[FILE_PROCESSING] {self.name} tool will embed new files: {', '.join([os.path.basename(f) for f in files_to_embed])}"
            )
        else:
            logger.info(
                f"[FILE_PROCESSING] {self.name} tool: No new files to embed (all files already in conversation history)"
            )

        content_parts = []
        actually_processed_files = []

        # Read content of new files only
        if files_to_embed:
            logger.debug(f"{self.name} tool embedding {len(files_to_embed)} new files: {', '.join(files_to_embed)}")
            logger.debug(
                f"[FILES] {self.name}: Starting file embedding with token budget {effective_max_tokens + reserve_tokens:,}"
            )
            try:
                # Before calling read_files, expand directories to get individual file paths
                from utils.file_utils import expand_paths

                expanded_files = expand_paths(files_to_embed)
                logger.debug(
                    f"[FILES] {self.name}: Expanded {len(files_to_embed)} paths to {len(expanded_files)} individual files"
                )

                file_content = read_files(
                    files_to_embed,
                    max_tokens=effective_max_tokens + reserve_tokens,
                    reserve_tokens=reserve_tokens,
                    include_line_numbers=self.wants_line_numbers_by_default(),
                )
                self._validate_token_limit(file_content, context_description)
                content_parts.append(file_content)

                # Track the expanded files as actually processed
                actually_processed_files.extend(expanded_files)

                # Estimate tokens for debug logging
                from utils.token_utils import estimate_tokens

                content_tokens = estimate_tokens(file_content)
                logger.debug(
                    f"{self.name} tool successfully embedded {len(files_to_embed)} files ({content_tokens:,} tokens)"
                )
                logger.debug(f"[FILES] {self.name}: Successfully embedded files - {content_tokens:,} tokens used")
                logger.debug(
                    f"[FILES] {self.name}: Actually processed {len(actually_processed_files)} individual files"
                )
            except Exception as e:
                logger.error(f"{self.name} tool failed to embed files {files_to_embed}: {type(e).__name__}: {e}")
                logger.debug(f"[FILES] {self.name}: File embedding failed - {type(e).__name__}: {e}")
                raise
        else:
            logger.debug(f"[FILES] {self.name}: No files to embed after filtering")

        # Generate note about files already in conversation history
        if continuation_id and len(files_to_embed) < len(request_files):
            embedded_files = self.get_conversation_embedded_files(continuation_id)
            skipped_files = [f for f in request_files if f in embedded_files]
            if skipped_files:
                logger.debug(
                    f"{self.name} tool skipping {len(skipped_files)} files already in conversation history: {', '.join(skipped_files)}"
                )
                logger.debug(f"[FILES] {self.name}: Adding note about {len(skipped_files)} skipped files")
                if content_parts:
                    content_parts.append("\n\n")
                note_lines = [
                    "--- NOTE: Additional files referenced in conversation history ---",
                    "The following files are already available in our conversation context:",
                    "\n".join(f"  - {f}" for f in skipped_files),
                    "--- END NOTE ---",
                ]
                content_parts.append("\n".join(note_lines))
            else:
                logger.debug(f"[FILES] {self.name}: No skipped files to note")

        result = "".join(content_parts) if content_parts else ""
        logger.debug(
            f"[FILES] {self.name}: _prepare_file_content_for_prompt returning {len(result)} chars, {len(actually_processed_files)} processed files"
        )
        return result, actually_processed_files

    def get_websearch_instruction(self, use_websearch: bool, tool_specific: Optional[str] = None) -> str:
        """
        Generate standardized web search instruction based on the use_websearch parameter.

        Args:
            use_websearch: Whether web search is enabled
            tool_specific: Optional tool-specific search guidance

        Returns:
            str: Web search instruction to append to prompt, or empty string
        """
        if not use_websearch:
            return ""

        base_instruction = """

WEB SEARCH CAPABILITY: You can request Claude to perform web searches to enhance your analysis with current information!

IMPORTANT: When you identify areas where web searches would significantly improve your response (such as checking current documentation, finding recent solutions, verifying best practices, or gathering community insights), you MUST explicitly instruct Claude to perform specific web searches and then respond back using the continuation_id from this response to continue the analysis.

Use clear, direct language based on the value of the search:

For valuable supplementary information: "Please perform a web search on '[specific topic/query]' and then continue this analysis using the continuation_id from this response if you find relevant information."

For important missing information: "Please search for '[specific topic/query]' and respond back with the findings using the continuation_id from this response - this information is needed to provide a complete analysis."

For critical/essential information: "SEARCH REQUIRED: Please immediately perform a web search on '[specific topic/query]' and respond back with the results using the continuation_id from this response. Cannot provide accurate analysis without this current information."

This ensures you get the most current and comprehensive information while maintaining conversation context through the continuation_id."""

        if tool_specific:
            return f"""{base_instruction}

{tool_specific}

When recommending searches, be specific about what information you need and why it would improve your analysis."""

        # Default instruction for all tools
        return f"""{base_instruction}

Consider requesting searches for:
- Current documentation and API references
- Recent best practices and patterns
- Known issues and community solutions
- Framework updates and compatibility
- Security advisories and patches
- Performance benchmarks and optimizations

When recommending searches, be specific about what information you need and why it would improve your analysis. Always remember to instruct Claude to use the continuation_id from this response when providing search results."""

    def get_language_instruction(self) -> str:
        """
        Generate language instruction based on LOCALE configuration.

        Returns:
            str: Language instruction to prepend to prompt, or empty string if
                 no locale set
        """
        from config import LOCALE

        if not LOCALE or not LOCALE.strip():
            return ""

        # Simple language instruction
        return f"Always respond in {LOCALE.strip()}.\n\n"

    # === ABSTRACT METHODS FOR SIMPLE TOOLS ===

    @abstractmethod
    async def prepare_prompt(self, request) -> str:
        """
        Prepare the complete prompt for the AI model.

        This method should construct the full prompt by combining:
        - System prompt from get_system_prompt()
        - File content from _prepare_file_content_for_prompt()
        - Conversation history from reconstruct_thread_context()
        - User's request and any tool-specific context

        Args:
            request: The validated request object

        Returns:
            str: Complete prompt ready for the AI model
        """
        pass

    def format_response(self, response: str, request, model_info: dict = None) -> str:
        """
        Format the AI model's response for the user.

        This method allows tools to post-process the model's response,
        adding structure, validation, or additional context.

        The default implementation returns the response unchanged.
        Tools can override this method to add custom formatting.

        Args:
            response: Raw response from the AI model
            request: The original request object
            model_info: Optional model information and metadata

        Returns:
            str: Formatted response ready for the user
        """
        return response

    # === IMPLEMENTATION METHODS ===
    # These will be provided in a full implementation but are inherited from current base.py
    # for now to maintain compatibility.

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Execute the tool - will be inherited from existing base.py for now."""
        # This will be implemented by importing from the current base.py
        # for backward compatibility during the migration
        raise NotImplementedError("Subclasses must implement execute method")

    def _should_require_model_selection(self, model_name: str) -> bool:
        """
        Check if we should require Claude to select a model at runtime.

        This is called during request execution to determine if we need
        to return an error asking Claude to provide a model parameter.

        Args:
            model_name: The model name from the request or DEFAULT_MODEL

        Returns:
            bool: True if we should require model selection
        """
        # Case 1: Model is explicitly "auto"
        if model_name.lower() == "auto":
            return True

        # Case 2: Requested model is not available
        from providers.registry import ModelProviderRegistry

        provider = ModelProviderRegistry.get_provider_for_model(model_name)
        if not provider:
            logger.warning(f"Model '{model_name}' is not available with current API keys. Requiring model selection.")
            return True

        return False

    def _get_available_models(self) -> list[str]:
        """
        Get list of models available from enabled providers.

        Only returns models from providers that have valid API keys configured.
        This fixes the namespace collision bug where models from disabled providers
        were shown to Claude, causing routing conflicts.

        Returns:
            List of model names from enabled providers only
        """
        from providers.registry import ModelProviderRegistry

        # Get models from enabled providers only (those with valid API keys)
        all_models = ModelProviderRegistry.get_available_model_names()

        # Add OpenRouter models if OpenRouter is configured
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key and openrouter_key != "your_openrouter_api_key_here":
            try:
                from config import OPENROUTER_MODELS

                all_models.extend(OPENROUTER_MODELS)
            except ImportError:
                pass

        return sorted(set(all_models))

    def _resolve_model_context(self, arguments: dict, request) -> tuple[str, Any]:
        """
        Resolve model context and name using centralized logic.

        This method extracts the model resolution logic from execute() so it can be
        reused by tools that override execute() (like debug tool) without duplicating code.

        Args:
            arguments: Dictionary of arguments from the MCP client
            request: The validated request object

        Returns:
            tuple[str, ModelContext]: (resolved_model_name, model_context)

        Raises:
            ValueError: If model resolution fails or model selection is required
        """
        # MODEL RESOLUTION NOW HAPPENS AT MCP BOUNDARY
        # Extract pre-resolved model context from server.py
        model_context = arguments.get("_model_context")
        resolved_model_name = arguments.get("_resolved_model_name")

        if model_context and resolved_model_name:
            # Model was already resolved at MCP boundary
            model_name = resolved_model_name
            logger.debug(f"Using pre-resolved model '{model_name}' from MCP boundary")
        else:
            # Fallback for direct execute calls
            model_name = getattr(request, "model", None)
            if not model_name:
                from config import DEFAULT_MODEL

                model_name = DEFAULT_MODEL
            logger.debug(f"Using fallback model resolution for '{model_name}' (test mode)")

            # For tests: Check if we should require model selection (auto mode)
            if self._should_require_model_selection(model_name):
                # Get suggested model based on tool category
                from providers.registry import ModelProviderRegistry

                tool_category = self.get_model_category()
                suggested_model = ModelProviderRegistry.get_preferred_fallback_model(tool_category)

                # Build error message based on why selection is required
                if model_name.lower() == "auto":
                    error_message = (
                        f"Model parameter is required in auto mode. "
                        f"Suggested model for {self.get_name()}: '{suggested_model}' "
                        f"(category: {tool_category.value})"
                    )
                else:
                    # Model was specified but not available
                    available_models = self._get_available_models()

                    error_message = (
                        f"Model '{model_name}' is not available with current API keys. "
                        f"Available models: {', '.join(available_models)}. "
                        f"Suggested model for {self.get_name()}: '{suggested_model}' "
                        f"(category: {tool_category.value})"
                    )
                raise ValueError(error_message)

            # Create model context for tests
            from utils.model_context import ModelContext

            model_context = ModelContext(model_name)

        return model_name, model_context

    def validate_and_correct_temperature(self, temperature: float, model_context: Any) -> tuple[float, list[str]]:
        """
        Validate and correct temperature for the specified model.

        This method ensures that the temperature value is within the valid range
        for the specific model being used. Different models have different temperature
        constraints (e.g., o1 models require temperature=1.0, GPT models support 0-2).

        Args:
            temperature: Temperature value to validate
            model_context: Model context object containing model name, provider, and capabilities

        Returns:
            Tuple of (corrected_temperature, warning_messages)
        """
        try:
            # Use model context capabilities directly - clean OOP approach
            capabilities = model_context.capabilities
            constraint = capabilities.temperature_constraint

            warnings = []
            if not constraint.validate(temperature):
                corrected = constraint.get_corrected_value(temperature)
                warning = (
                    f"Temperature {temperature} invalid for {model_context.model_name}. "
                    f"{constraint.get_description()}. Using {corrected} instead."
                )
                warnings.append(warning)
                return corrected, warnings

            return temperature, warnings

        except Exception as e:
            # If validation fails for any reason, use the original temperature
            # and log a warning (but don't fail the request)
            logger.warning(f"Temperature validation failed for {model_context.model_name}: {e}")
            return temperature, [f"Temperature validation failed: {e}"]

    def _validate_image_limits(
        self, images: Optional[list[str]], model_context: Optional[Any] = None, continuation_id: Optional[str] = None
    ) -> Optional[dict]:
        """
        Validate image size and count against model capabilities.

        This performs strict validation to ensure we don't exceed model-specific
        image limits. Uses capability-based validation with actual model
        configuration rather than hard-coded limits.

        Args:
            images: List of image paths/data URLs to validate
            model_context: Model context object containing model name, provider, and capabilities
            continuation_id: Optional continuation ID for conversation context

        Returns:
            Optional[dict]: Error response if validation fails, None if valid
        """
        if not images:
            return None

        # Import here to avoid circular imports
        import base64
        from pathlib import Path

        # Handle legacy calls (positional model_name string)
        if isinstance(model_context, str):
            # Legacy call: _validate_image_limits(images, "model-name")
            logger.warning(
                "Legacy _validate_image_limits call with model_name string. Use model_context object instead."
            )
            try:
                from utils.model_context import ModelContext

                model_context = ModelContext(model_context)
            except Exception as e:
                logger.warning(f"Failed to create model context from legacy model_name: {e}")
                # Generic error response for any unavailable model
                return {
                    "status": "error",
                    "content": f"Model '{model_context}' is not available. {str(e)}",
                    "content_type": "text",
                    "metadata": {
                        "error_type": "validation_error",
                        "model_name": model_context,
                        "supports_images": None,  # Unknown since model doesn't exist
                        "image_count": len(images) if images else 0,
                    },
                }

        if not model_context:
            # Get from tool's stored context as fallback
            model_context = getattr(self, "_model_context", None)
            if not model_context:
                logger.warning("No model context available for image validation")
                return None

        try:
            # Use model context capabilities directly - clean OOP approach
            capabilities = model_context.capabilities
            model_name = model_context.model_name
        except Exception as e:
            logger.warning(f"Failed to get capabilities from model_context for image validation: {e}")
            # Generic error response when capabilities cannot be accessed
            model_name = getattr(model_context, "model_name", "unknown")
            return {
                "status": "error",
                "content": f"Model '{model_name}' is not available. {str(e)}",
                "content_type": "text",
                "metadata": {
                    "error_type": "validation_error",
                    "model_name": model_name,
                    "supports_images": None,  # Unknown since model capabilities unavailable
                    "image_count": len(images) if images else 0,
                },
            }

        # Check if model supports images
        if not capabilities.supports_images:
            return {
                "status": "error",
                "content": (
                    f"Image support not available: Model '{model_name}' does not support image processing. "
                    f"Please use a vision-capable model such as 'gemini-2.5-flash', 'o3', "
                    f"or 'claude-3-opus' for image analysis tasks."
                ),
                "content_type": "text",
                "metadata": {
                    "error_type": "validation_error",
                    "model_name": model_name,
                    "supports_images": False,
                    "image_count": len(images),
                },
            }

        # Get model image limits from capabilities
        max_images = 5  # Default max number of images
        max_size_mb = capabilities.max_image_size_mb

        # Check image count
        if len(images) > max_images:
            return {
                "status": "error",
                "content": (
                    f"Too many images: Model '{model_name}' supports a maximum of {max_images} images, "
                    f"but {len(images)} were provided. Please reduce the number of images."
                ),
                "content_type": "text",
                "metadata": {
                    "error_type": "validation_error",
                    "model_name": model_name,
                    "image_count": len(images),
                    "max_images": max_images,
                },
            }

        # Calculate total size of all images
        total_size_mb = 0.0
        for image_path in images:
            try:
                if image_path.startswith("data:image/"):
                    # Handle data URL: data:image/png;base64,iVBORw0...
                    _, data = image_path.split(",", 1)
                    # Base64 encoding increases size by ~33%, so decode to get actual size
                    actual_size = len(base64.b64decode(data))
                    total_size_mb += actual_size / (1024 * 1024)
                else:
                    # Handle file path
                    path = Path(image_path)
                    if path.exists():
                        file_size = path.stat().st_size
                        total_size_mb += file_size / (1024 * 1024)
                    else:
                        logger.warning(f"Image file not found: {image_path}")
                        # Assume a reasonable size for missing files to avoid breaking validation
                        total_size_mb += 1.0  # 1MB assumption
            except Exception as e:
                logger.warning(f"Failed to get size for image {image_path}: {e}")
                # Assume a reasonable size for problematic files
                total_size_mb += 1.0  # 1MB assumption

        # Apply 40MB cap for custom models if needed
        effective_limit_mb = max_size_mb
        try:
            from providers.base import ProviderType

            # ModelCapabilities dataclass has provider field defined
            if capabilities.provider == ProviderType.CUSTOM:
                effective_limit_mb = min(max_size_mb, 40.0)
        except Exception:
            pass

        # Validate against size limit
        if total_size_mb > effective_limit_mb:
            return {
                "status": "error",
                "content": (
                    f"Image size limit exceeded: Model '{model_name}' supports maximum {effective_limit_mb:.1f}MB "
                    f"for all images combined, but {total_size_mb:.1f}MB was provided. "
                    f"Please reduce image sizes or count and try again."
                ),
                "content_type": "text",
                "metadata": {
                    "error_type": "validation_error",
                    "model_name": model_name,
                    "total_size_mb": round(total_size_mb, 2),
                    "limit_mb": round(effective_limit_mb, 2),
                    "image_count": len(images),
                    "supports_images": True,
                },
            }

        # All validations passed
        logger.debug(f"Image validation passed: {len(images)} images, {total_size_mb:.1f}MB total")
        return None

    def _parse_response(self, raw_text: str, request, model_info: Optional[dict] = None):
        """Parse response - will be inherited for now."""
        # Implementation inherited from current base.py
        raise NotImplementedError("Subclasses must implement _parse_response method")
