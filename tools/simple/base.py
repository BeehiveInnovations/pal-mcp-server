"""
Base class for simple MCP tools.

Simple tools follow a straightforward pattern:
1. Receive request
2. Prepare prompt (with absolute file paths, context, etc.)
3. Call AI model
4. Format and return response

They use the shared SchemaBuilder for consistent schema generation
and inherit all the conversation, file processing, and model handling
capabilities from BaseTool.
"""

from abc import abstractmethod
from typing import Any, Optional

from tools.shared.base_models import ToolRequest
from tools.shared.base_tool import BaseTool
from tools.shared.exceptions import ToolExecutionError
from tools.shared.schema_builders import SchemaBuilder


class SimpleTool(BaseTool):
    """
    Base class for simple (non-workflow) tools.

    Simple tools are request/response tools that don't require multi-step workflows.
    They benefit from:
    - Automatic schema generation using SchemaBuilder
    - Inherited conversation handling and file processing
    - Standardized model integration
    - Consistent error handling and response formatting

    To create a simple tool:
    1. Inherit from SimpleTool
    2. Implement get_tool_fields() to define tool-specific fields
    3. Implement prepare_prompt() for prompt preparation
    4. Optionally override format_response() for custom formatting
    5. Optionally override get_required_fields() for custom requirements

    Example:
        class ChatTool(SimpleTool):
            def get_name(self) -> str:
                return "chat"

            def get_tool_fields(self) -> Dict[str, Dict[str, Any]]:
                return {
                    "prompt": {
                        "type": "string",
                        "description": "Your question or idea...",
                    },
                    "absolute_file_paths": SimpleTool.FILES_FIELD,
                }

            def get_required_fields(self) -> List[str]:
                return ["prompt"]
    """

    # Common field definitions that simple tools can reuse
    FILES_FIELD = SchemaBuilder.SIMPLE_FIELD_SCHEMAS["absolute_file_paths"]
    IMAGES_FIELD = SchemaBuilder.COMMON_FIELD_SCHEMAS["images"]

    @abstractmethod
    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        """
        Return tool-specific field definitions.

        This method should return a dictionary mapping field names to their
        JSON schema definitions. Common fields (model, temperature, etc.)
        are added automatically by the base class.

        Returns:
            Dict mapping field names to JSON schema objects

        Example:
            return {
                "prompt": {
                    "type": "string",
                    "description": "The user's question or request",
                },
                "absolute_file_paths": SimpleTool.FILES_FIELD,  # Reuse common field
                "max_tokens": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Maximum tokens for response",
                }
            }
        """
        pass

    def get_required_fields(self) -> list[str]:
        """
        Return list of required field names.

        Override this to specify which fields are required for your tool.
        The model field is automatically added if in auto mode.

        Returns:
            List of required field names
        """
        return []

    def get_annotations(self) -> Optional[dict[str, Any]]:
        """
        Return tool annotations. Simple tools are read-only by default.

        All simple tools perform operations without modifying the environment.
        They may call external AI models for analysis or conversation, but they
        don't write files or make system changes.

        Override this method if your simple tool needs different annotations.

        Returns:
            Dictionary with readOnlyHint set to True
        """
        return {"readOnlyHint": True}

    def format_response(self, response: str, request, model_info: Optional[dict] = None) -> str:
        """
        Format the AI response before returning to the client.

        This is a hook method that subclasses can override to customize
        response formatting. The default implementation returns the response as-is.

        Args:
            response: The raw response from the AI model
            request: The validated request object
            model_info: Optional model information dictionary

        Returns:
            Formatted response string
        """
        return response

    def get_input_schema(self) -> dict[str, Any]:
        """
        Generate the complete input schema using SchemaBuilder.

        This method automatically combines:
        - Tool-specific fields from get_tool_fields()
        - Common fields (temperature, thinking_mode, etc.)
        - Model field with proper auto-mode handling
        - Required fields from get_required_fields()

        Tools can override this method for custom schema generation while
        still benefiting from SimpleTool's convenience methods.

        Returns:
            Complete JSON schema for the tool
        """
        required_fields = list(self.get_required_fields())
        return SchemaBuilder.build_schema(
            tool_specific_fields=self.get_tool_fields(),
            required_fields=required_fields,
            model_field_schema=self.get_model_field_schema(),
            auto_mode=self.is_effective_auto_mode(),
        )

    def get_request_model(self):
        """
        Return the request model class.

        Simple tools use the base ToolRequest by default.
        Override this if your tool needs a custom request model.
        """
        return ToolRequest

    # Hook methods for safe attribute access without hasattr/getattr

    def get_request_model_name(self, request) -> Optional[str]:
        """Get model name from request. Override for custom model name handling."""
        try:
            return request.model
        except AttributeError:
            return None

    def get_request_images(self, request) -> list:
        """Get images from request. Override for custom image handling."""
        try:
            return request.images if request.images is not None else []
        except AttributeError:
            return []

    def get_request_continuation_id(self, request) -> Optional[str]:
        """Get continuation_id from request. Override for custom continuation handling."""
        try:
            return request.continuation_id
        except AttributeError:
            return None

    def get_request_prompt(self, request) -> str:
        """Get prompt from request. Override for custom prompt handling."""
        try:
            return request.prompt
        except AttributeError:
            return ""

    def get_request_temperature(self, request) -> Optional[float]:
        """Get temperature from request. Override for custom temperature handling."""
        try:
            return request.temperature
        except AttributeError:
            return None

    def get_validated_temperature(self, request, model_context: Any) -> tuple[float, list[str]]:
        """
        Get temperature from request and validate it against model constraints.

        This is a convenience method that combines temperature extraction and validation
        for simple tools. It ensures temperature is within valid range for the model.

        Args:
            request: The request object containing temperature
            model_context: Model context object containing model info

        Returns:
            Tuple of (validated_temperature, warning_messages)
        """
        temperature = self.get_request_temperature(request)
        if temperature is None:
            temperature = self.get_default_temperature()
        return self.validate_and_correct_temperature(temperature, model_context)

    def get_request_thinking_mode(self, request) -> Optional[str]:
        """Get thinking_mode from request. Override for custom thinking mode handling."""
        try:
            return request.thinking_mode
        except AttributeError:
            return None

    def get_request_files(self, request) -> list:
        """Get absolute file paths from request. Override for custom file handling."""
        try:
            files = request.absolute_file_paths
        except AttributeError:
            files = None
        if files is None:
            return []
        return files

    def get_request_as_dict(self, request) -> dict:
        """Convert request to dictionary. Override for custom serialization."""
        try:
            # Try Pydantic v2 method first
            return request.model_dump()
        except AttributeError:
            try:
                # Fall back to Pydantic v1 method
                return request.dict()
            except AttributeError:
                # Last resort - convert to dict manually
                return {"prompt": self.get_request_prompt(request)}

    def set_request_files(self, request, files: list) -> None:
        """Set absolute file paths on request. Override for custom file setting."""
        try:
            request.absolute_file_paths = files
        except AttributeError:
            pass

    def get_actually_processed_files(self) -> list:
        """Get actually processed files. Override for custom file tracking."""
        try:
            return self._actually_processed_files
        except AttributeError:
            return []

    async def execute(self, arguments: dict[str, Any]) -> list:
        """
        Execute the simple tool using the comprehensive flow from old base.py.

        This method replicates the proven execution pattern while using SimpleTool hooks.
        """
        import logging

        from mcp.types import TextContent

        from tools.models import ToolOutput

        logger = logging.getLogger(f"tools.{self.get_name()}")

        try:
            # Store arguments for access by helper methods
            self._current_arguments = arguments

            logger.info(f"🔧 {self.get_name()} tool called with arguments: {list(arguments.keys())}")

            # Validate request using the tool's Pydantic model
            request_model = self.get_request_model()
            request = request_model(**arguments)
            logger.debug(f"Request validation successful for {self.get_name()}")

            # Validate file paths for security
            # This prevents path traversal attacks and ensures proper access control
            path_error = self._validate_file_paths(request)
            if path_error:
                error_output = ToolOutput(
                    status="error",
                    content=path_error,
                    content_type="text",
                )
                logger.error("Path validation failed for %s: %s", self.get_name(), path_error)
                raise ToolExecutionError(error_output.model_dump_json())

            # Handle model resolution like old base.py
            model_name = self.get_request_model_name(request)
            if not model_name:
                from config import DEFAULT_MODEL

                model_name = DEFAULT_MODEL

            # Store the current model name for later use
            self._current_model_name = model_name

            # Handle model context from arguments (for in-process testing)
            if "_model_context" in arguments:
                self._model_context = arguments["_model_context"]
                logger.debug(f"{self.get_name()}: Using model context from arguments")
            else:
                # Create model context if not provided
                from utils.model_context import ModelContext

                self._model_context = ModelContext(model_name)
                logger.debug(f"{self.get_name()}: Created model context for {model_name}")

            # Get images if present
            images = self.get_request_images(request)
            continuation_id = self.get_request_continuation_id(request)

            # Handle conversation history and prompt preparation
            if continuation_id:
                # Check if conversation history is already embedded
                field_value = self.get_request_prompt(request)
                if "=== CONVERSATION HISTORY ===" in field_value:
                    # Use pre-embedded history
                    prompt = field_value
                    logger.debug(f"{self.get_name()}: Using pre-embedded conversation history")
                else:
                    # No embedded history - reconstruct it (for in-process calls)
                    logger.debug(f"{self.get_name()}: No embedded history found, reconstructing conversation")

                    # Get thread context
                    from utils.conversation_memory import add_turn, build_conversation_history, get_thread

                    thread_context = get_thread(continuation_id)

                    if thread_context:
                        # Add user's new input to conversation
                        user_prompt = self.get_request_prompt(request)
                        user_files = self.get_request_files(request)
                        if user_prompt:
                            add_turn(continuation_id, "user", user_prompt, files=user_files)

                            # Get updated thread context after adding the turn
                            thread_context = get_thread(continuation_id)
                            logger.debug(
                                f"{self.get_name()}: Retrieved updated thread with {len(thread_context.turns)} turns"
                            )

                        # Build conversation history with updated thread context
                        conversation_history, conversation_tokens = build_conversation_history(
                            thread_context, self._model_context
                        )

                        # Get the base prompt from the tool
                        base_prompt = await self.prepare_prompt(request)

                        # Combine with conversation history
                        if conversation_history:
                            prompt = f"{conversation_history}\n\n=== NEW USER INPUT ===\n{base_prompt}"
                        else:
                            prompt = base_prompt
                    else:
                        # Thread not found, prepare normally
                        logger.warning(f"Thread {continuation_id} not found, preparing prompt normally")
                        prompt = await self.prepare_prompt(request)
            else:
                # New conversation, prepare prompt normally
                prompt = await self.prepare_prompt(request)

                # Add follow-up instructions for new conversations
                from server import get_follow_up_instructions

                follow_up_instructions = get_follow_up_instructions(0)
                prompt = f"{prompt}\n\n{follow_up_instructions}"
                logger.debug(
                    f"Added follow-up instructions for new {self.get_name()} conversation"
                )  # Validate images if any were provided
            if images:
                image_validation_error = self._validate_image_limits(
                    images, model_context=self._model_context, continuation_id=continuation_id
                )
                if image_validation_error:
                    error_output = ToolOutput(
                        status=image_validation_error.get("status", "error"),
                        content=image_validation_error.get("content"),
                        content_type=image_validation_error.get("content_type", "text"),
                        metadata=image_validation_error.get("metadata"),
                    )
                    payload = error_output.model_dump_json()
                    logger.error("Image validation failed for %s: %s", self.get_name(), payload)
                    raise ToolExecutionError(payload)

            # Get and validate temperature against model constraints
            temperature, temp_warnings = self.get_validated_temperature(request, self._model_context)

            # Log any temperature corrections
            for warning in temp_warnings:
                # Get thinking mode with defaults
                logger.warning(warning)
            thinking_mode = self.get_request_thinking_mode(request)
            if thinking_mode is None:
                thinking_mode = self.get_default_thinking_mode()

            # Get the provider from model context (clean OOP - no re-fetching)
            provider = self._model_context.provider
            capabilities = self._model_context.capabilities

            # Get system prompt for this tool
            base_system_prompt = self.get_system_prompt()
            capability_augmented_prompt = self._augment_system_prompt_with_capabilities(
                base_system_prompt, capabilities
            )
            language_instruction = self.get_language_instruction()
            system_prompt = language_instruction + capability_augmented_prompt

            # Generate AI response using the provider
            logger.info(f"Sending request to {provider.get_provider_type().value} API for {self.get_name()}")
            logger.info(
                f"Using model: {self._model_context.model_name} via {provider.get_provider_type().value} provider"
            )

            # Estimate tokens for logging
            from utils.token_utils import estimate_tokens

            estimated_tokens = estimate_tokens(prompt)
            logger.debug(f"Prompt length: {len(prompt)} characters (~{estimated_tokens:,} tokens)")

            # Resolve model capabilities for feature gating
            supports_thinking = capabilities.supports_extended_thinking

            # Generate content with provider abstraction
            model_response = provider.generate_content(
                prompt=prompt,
                model_name=self._current_model_name,
                system_prompt=system_prompt,
                temperature=temperature,
                thinking_mode=thinking_mode if supports_thinking else None,
                images=images if images else None,
            )

            logger.info(f"Received response from {provider.get_provider_type().value} API for {self.get_name()}")

            # Process the model's response
            if model_response.content:
                raw_text = model_response.content

                # Create model info for conversation tracking
                model_info = {
                    "provider": provider,
                    "model_name": self._current_model_name,
                    "model_response": model_response,
                }

                # Parse response using the same logic as old base.py
                tool_output = self._parse_response(raw_text, request, model_info)
                logger.info(f"✅ {self.get_name()} tool completed successfully")

            else:
                # Handle cases where the model couldn't generate a response
                metadata = model_response.metadata or {}
                finish_reason = metadata.get("finish_reason", "Unknown")

                if metadata.get("is_blocked_by_safety"):
                    # Specific handling for content safety blocks
                    safety_details = metadata.get("safety_feedback") or "details not provided"
                    logger.warning(
                        f"Response blocked by content safety policy for {self.get_name()}. "
                        f"Reason: {finish_reason}, Details: {safety_details}"
                    )
                    tool_output = ToolOutput(
                        status="error",
                        content="Your request was blocked by the content safety policy. "
                        "Please try modifying your prompt.",
                        content_type="text",
                    )
                else:
                    # Handle other empty responses - could be legitimate completion or unclear blocking
                    if finish_reason == "STOP":
                        # Model completed normally but returned empty content - retry with clarification
                        logger.info(
                            f"Model completed with empty response for {self.get_name()}, retrying with clarification"
                        )

                        # Retry the same request with modified prompt asking for explicit response
                        original_prompt = prompt
                        retry_prompt = f"{original_prompt}\n\nIMPORTANT: Please provide a substantive response. If you cannot respond to the above request, please explain why and suggest alternatives."

                        try:
                            retry_response = provider.generate_content(
                                prompt=retry_prompt,
                                model_name=self._current_model_name,
                                system_prompt=system_prompt,
                                temperature=temperature,
                                thinking_mode=thinking_mode if supports_thinking else None,
                                images=images if images else None,
                            )

                            if retry_response.content:
                                # Successful retry - use the retry response
                                logger.info(f"Retry successful for {self.get_name()}")
                                raw_text = retry_response.content

                                # Update model info for the successful retry
                                model_info = {
                                    "provider": provider,
                                    "model_name": self._current_model_name,
                                    "model_response": retry_response,
                                }

                                # Parse the retry response
                                tool_output = self._parse_response(raw_text, request, model_info)
                                logger.info(f"✅ {self.get_name()} tool completed successfully after retry")
                            else:
                                # Retry also failed - inspect metadata to find out why
                                retry_metadata = retry_response.metadata or {}
                                if retry_metadata.get("is_blocked_by_safety"):
                                    # The retry was blocked by safety filters
                                    safety_details = retry_metadata.get("safety_feedback") or "details not provided"
                                    logger.warning(
                                        f"Retry for {self.get_name()} was blocked by content safety policy. "
                                        f"Details: {safety_details}"
                                    )
                                    tool_output = ToolOutput(
                                        status="error",
                                        content="Your request was also blocked by the content safety policy after a retry. "
                                        "Please try rephrasing your prompt significantly.",
                                        content_type="text",
                                    )
                                else:
                                    # Retry failed for other reasons (e.g., another STOP)
                                    tool_output = ToolOutput(
                                        status="error",
                                        content="The model repeatedly returned empty responses. This may indicate content filtering or a model issue.",
                                        content_type="text",
                                    )
                        except Exception as retry_error:
                            logger.warning(f"Retry failed for {self.get_name()}: {retry_error}")
                            tool_output = ToolOutput(
                                status="error",
                                content=f"Model returned empty response and retry failed: {str(retry_error)}",
                                content_type="text",
                            )
                    else:
                        # Non-STOP finish reasons are likely actual errors
                        logger.warning(
                            f"Response blocked or incomplete for {self.get_name()}. Finish reason: {finish_reason}"
                        )
                        tool_output = ToolOutput(
                            status="error",
                            content=f"Response blocked or incomplete. Finish reason: {finish_reason}",
                            content_type="text",
                        )

            # Return the tool output as TextContent, marking protocol errors appropriately
            payload = tool_output.model_dump_json()
            if tool_output.status == "error":
                logger.error("%s reported error status - raising ToolExecutionError", self.get_name())
                raise ToolExecutionError(payload)
            return [TextContent(type="text", text=payload)]

        except ToolExecutionError:
            raise
        except Exception as e:
            # Special handling for MCP size check errors
            if str(e).startswith("MCP_SIZE_CHECK:"):
                # Extract the JSON content after the prefix
                json_content = str(e)[len("MCP_SIZE_CHECK:") :]
                raise ToolExecutionError(json_content)

            logger.error(f"Error in {self.get_name()}: {str(e)}")
            error_output = ToolOutput(
                status="error",
                content=f"Error in {self.get_name()}: {str(e)}",
                content_type="text",
            )
            raise ToolExecutionError(error_output.model_dump_json()) from e

    def _parse_response(self, raw_text: str, request, model_info: Optional[dict] = None):
        """
        Parse the raw response and format it using the hook method.

        This simplified version focuses on the SimpleTool pattern: format the response
        using the format_response hook, then handle conversation continuation.
        """
        from tools.models import ToolOutput

        # Format the response using the hook method
        formatted_response = self.format_response(raw_text, request, model_info)

        # Handle conversation continuation like old base.py
        continuation_id = self.get_request_continuation_id(request)
        if continuation_id:
            self._record_assistant_turn(continuation_id, raw_text, request, model_info)

        # Create continuation offer like old base.py
        continuation_data = self._create_continuation_offer(request, model_info)
        if continuation_data:
            return self._create_continuation_offer_response(formatted_response, continuation_data, request, model_info)
        else:
            # Build metadata with model and provider info for success response
            metadata = {}
            if model_info:
                model_name = model_info.get("model_name")
                if model_name:
                    metadata["model_used"] = model_name
                provider = model_info.get("provider")
                if provider:
                    # Handle both provider objects and string values
                    if isinstance(provider, str):
                        metadata["provider_used"] = provider
                    else:
                        try:
                            metadata["provider_used"] = provider.get_provider_type().value
                        except AttributeError:
                            # Fallback if provider doesn't have get_provider_type method
                            metadata["provider_used"] = str(provider)

            return ToolOutput(
                status="success",
                content=formatted_response,
                content_type="text",
                metadata=metadata if metadata else None,
            )

    def _create_continuation_offer(self, request, model_info: Optional[dict] = None):
        """Create continuation offer following old base.py pattern"""
        continuation_id = self.get_request_continuation_id(request)

        try:
            from utils.conversation_memory import create_thread, get_thread

            if continuation_id:
                # Existing conversation
                thread_context = get_thread(continuation_id)
                if thread_context and thread_context.turns:
                    turn_count = len(thread_context.turns)
                    from utils.conversation_memory import MAX_CONVERSATION_TURNS

                    if turn_count >= MAX_CONVERSATION_TURNS - 1:
                        return None  # No more turns allowed

                    remaining_turns = MAX_CONVERSATION_TURNS - turn_count - 1
                    return {
                        "continuation_id": continuation_id,
                        "remaining_turns": remaining_turns,
                        "note": f"You can continue this conversation for {remaining_turns} more exchanges.",
                    }
            else:
                # New conversation - create thread and offer continuation
                # Convert request to dict for initial_context
                initial_request_dict = self.get_request_as_dict(request)

                new_thread_id = create_thread(tool_name=self.get_name(), initial_request=initial_request_dict)

                # Add the initial user turn to the new thread
                from utils.conversation_memory import MAX_CONVERSATION_TURNS, add_turn

                user_prompt = self.get_request_prompt(request)
                user_files = self.get_request_files(request)
                user_images = self.get_request_images(request)

                # Add user's initial turn
                add_turn(
                    new_thread_id, "user", user_prompt, files=user_files, images=user_images, tool_name=self.get_name()
                )

                return {
                    "continuation_id": new_thread_id,
                    "remaining_turns": MAX_CONVERSATION_TURNS - 1,
                    "note": f"You can continue this conversation for {MAX_CONVERSATION_TURNS - 1} more exchanges.",
                }
        except Exception:
            return None

    def _create_continuation_offer_response(
        self, content: str, continuation_data: dict, request, model_info: Optional[dict] = None
    ):
        """Create response with continuation offer following old base.py pattern"""
        from tools.models import ContinuationOffer, ToolOutput

        try:
            if not self.get_request_continuation_id(request):
                self._record_assistant_turn(
                    continuation_data["continuation_id"],
                    content,
                    request,
                    model_info,
                )

            continuation_offer = ContinuationOffer(
                continuation_id=continuation_data["continuation_id"],
                note=continuation_data["note"],
                remaining_turns=continuation_data["remaining_turns"],
            )

            # Build metadata with model and provider info
            metadata = {"tool_name": self.get_name(), "conversation_ready": True}
            if model_info:
                model_name = model_info.get("model_name")
                if model_name:
                    metadata["model_used"] = model_name
                provider = model_info.get("provider")
                if provider:
                    # Handle both provider objects and string values
                    if isinstance(provider, str):
                        metadata["provider_used"] = provider
                    else:
                        try:
                            metadata["provider_used"] = provider.get_provider_type().value
                        except AttributeError:
                            # Fallback if provider doesn't have get_provider_type method
                            metadata["provider_used"] = str(provider)

            return ToolOutput(
                status="continuation_available",
                content=content,
                content_type="text",
                continuation_offer=continuation_offer,
                metadata=metadata,
            )
        except Exception:
            # Fallback to simple success if continuation offer fails
            return ToolOutput(status="success", content=content, content_type="text")

    def _record_assistant_turn(
        self, continuation_id: str, response_text: str, request, model_info: Optional[dict]
    ) -> None:
        """Persist an assistant response in conversation memory."""

        if not continuation_id:
            return

        from utils.conversation_memory import add_turn

        model_provider = None
        model_name = None
        model_metadata = None

        if model_info:
            provider = model_info.get("provider")
            if provider:
                if isinstance(provider, str):
                    model_provider = provider
                else:
                    try:
                        model_provider = provider.get_provider_type().value
                    except AttributeError:
                        model_provider = str(provider)
            model_name = model_info.get("model_name")
            model_response = model_info.get("model_response")
            if model_response:
                model_metadata = {"usage": model_response.usage, "metadata": model_response.metadata}

        add_turn(
            continuation_id,
            "assistant",
            response_text,
            files=self.get_request_files(request),
            images=self.get_request_images(request),
            tool_name=self.get_name(),
            model_provider=model_provider,
            model_name=model_name,
            model_metadata=model_metadata,
        )

    # Convenience methods for common tool patterns

    def build_standard_prompt(
        self, system_prompt: str, user_content: str, request, file_context_title: str = "CONTEXT FILES"
    ) -> str:
        """
        Build a standard prompt with system prompt, user content, and optional files.

        This is a convenience method that handles the common pattern of:
        1. Adding file content if present
        2. Checking token limits
        3. Adding web search instructions
        4. Combining everything into a well-formatted prompt

        Args:
            system_prompt: The system prompt for the tool
            user_content: The main user request/content
            request: The validated request object
            file_context_title: Title for the file context section

        Returns:
            Complete formatted prompt ready for the AI model
        """
        # Check size limits against raw user input before enriching with internal context
        content_to_validate = self.get_prompt_content_for_size_validation(user_content)
        self._validate_token_limit(content_to_validate, "Content")

        # Add context files if provided (does not affect MCP boundary enforcement)
        files = self.get_request_files(request)
        if files:
            file_content, processed_files = self._prepare_file_content_for_prompt(
                files,
                self.get_request_continuation_id(request),
                "Context files",
                model_context=getattr(self, "_model_context", None),
            )
            self._actually_processed_files = processed_files
            if file_content:
                user_content = f"{user_content}\n\n=== {file_context_title} ===\n{file_content}\n=== END CONTEXT ===="

        # Add standardized web search guidance
        websearch_instruction = self.get_websearch_instruction(self.get_websearch_guidance())

        # Combine system prompt with user content
        full_prompt = f"""{system_prompt}{websearch_instruction}

=== USER REQUEST ===
{user_content}
=== END REQUEST ===

Please provide a thoughtful, comprehensive response:"""

        return full_prompt

    def get_prompt_content_for_size_validation(self, user_content: str) -> str:
        """
        Override to use original user prompt for size validation when conversation history is embedded.

        When server.py embeds conversation history into the prompt field, it also stores
        the original user prompt in _original_user_prompt. We use that for size validation
        to avoid incorrectly triggering size limits due to conversation history.

        Args:
            user_content: The user content (may include conversation history)

        Returns:
            The original user prompt if available, otherwise the full user content
        """
        # Check if we have the current arguments from execute() method
        current_args = getattr(self, "_current_arguments", None)
        if current_args:
            # If server.py embedded conversation history, it stores original prompt separately
            original_user_prompt = current_args.get("_original_user_prompt")
            if original_user_prompt is not None:
                # Use original user prompt for size validation (excludes conversation history)
                return original_user_prompt

        # Fallback to default behavior (validate full user content)
        return user_content

    def get_websearch_guidance(self) -> Optional[str]:
        """
        Return tool-specific web search guidance.

        Override this to provide tool-specific guidance for when web searches
        would be helpful. Return None to use the default guidance.

        Returns:
            Tool-specific web search guidance or None for default
        """
        return None

    def handle_prompt_file_with_fallback(self, request) -> str:
        """
        Handle prompt.txt files with fallback to request field.

        This is a convenience method for tools that accept prompts either
        as a field or as a prompt.txt file. It handles the extraction
        and validation automatically.

        Args:
            request: The validated request object

        Returns:
            The effective prompt content

        Raises:
            ValueError: If prompt is too large for MCP transport
        """
        # Check for prompt.txt in provided absolute file paths
        files = self.get_request_files(request)
        if files:
            prompt_content, updated_files = self.handle_prompt_file(files)

            # Update request files list if needed
            if updated_files is not None:
                self.set_request_files(request, updated_files)
        else:
            prompt_content = None

        # Use prompt.txt content if available, otherwise use the prompt field
        user_content = prompt_content if prompt_content else self.get_request_prompt(request)

        # Check user input size at MCP transport boundary (excluding conversation history)
        validation_content = self.get_prompt_content_for_size_validation(user_content)
        size_check = self.check_prompt_size(validation_content)
        if size_check:
            from tools.models import ToolOutput

            raise ValueError(f"MCP_SIZE_CHECK:{ToolOutput(**size_check).model_dump_json()}")

        return user_content

    def get_chat_style_websearch_guidance(self) -> str:
        """
        Get Chat tool-style web search guidance.

        Returns web search guidance that matches the original Chat tool pattern.
        This is useful for tools that want to maintain the same search behavior.

        Returns:
            Web search guidance text
        """
        return """When discussing topics, consider if searches for these would help:
- Documentation for any technologies or concepts mentioned
- Current best practices and patterns
- Recent developments or updates
- Community discussions and solutions"""

    def supports_custom_request_model(self) -> bool:
        """
        Indicate whether this tool supports custom request models.

        Simple tools support custom request models by default. Tools that override
        get_request_model() to return something other than ToolRequest should
        return True here.

        Returns:
            True if the tool uses a custom request model
        """
        return self.get_request_model() != ToolRequest

    def _validate_file_paths(self, request) -> Optional[str]:
        """
        Validate that all file paths in the request are absolute paths.

        This is a security measure to prevent path traversal attacks and ensure
        proper access control. All file paths must be absolute (starting with '/').

        Args:
            request: The validated request object

        Returns:
            Optional[str]: Error message if validation fails, None if all paths are valid
        """
        import os

        # Check if request has absolute file paths attribute (legacy tools may still provide 'files')
        files = self.get_request_files(request)
        if files:
            for file_path in files:
                if not os.path.isabs(file_path):
                    return (
                        f"Error: All file paths must be FULL absolute paths to real files / folders - DO NOT SHORTEN. "
                        f"Received relative path: {file_path}\n"
                        f"Please provide the full absolute path starting with '/' (must be FULL absolute paths to real files / folders - DO NOT SHORTEN)"
                    )

        return None

    def prepare_chat_style_prompt(self, request, system_prompt: str = None) -> str:
        """
        Prepare a prompt using Chat tool-style patterns.

        This convenience method replicates the Chat tool's prompt preparation logic:
        1. Handle prompt.txt file if present
        2. Add file context with specific formatting
        3. Add web search guidance
        4. Format with system prompt

        Args:
            request: The validated request object
            system_prompt: System prompt to use (uses get_system_prompt() if None)

        Returns:
            Complete formatted prompt
        """
        # Use provided system prompt or get from tool
        if system_prompt is None:
            system_prompt = self.get_system_prompt()

        # Get user content (handles prompt.txt files)
        user_content = self.handle_prompt_file_with_fallback(request)

        # Build standard prompt with Chat-style web search guidance
        websearch_guidance = self.get_chat_style_websearch_guidance()

        # Override the websearch guidance temporarily
        original_guidance = self.get_websearch_guidance
        self.get_websearch_guidance = lambda: websearch_guidance

        try:
            full_prompt = self.build_standard_prompt(system_prompt, user_content, request, "CONTEXT FILES")
        finally:
            # Restore original guidance method
            self.get_websearch_guidance = original_guidance

        if system_prompt:
            marker = "\n\n=== USER REQUEST ===\n"
            if marker in full_prompt:
                _, user_section = full_prompt.split(marker, 1)
                return f"=== USER REQUEST ===\n{user_section}"

        return full_prompt
