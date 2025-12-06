"""OpenAI Responses API provider (/v1/responses endpoint).

This provider handles OpenAI's Responses API which is used for reasoning models
like o3, o3-pro, and GPT-5-Pro. It's separate from the Chat Completions API.
"""

import base64
import logging
import os
from typing import Optional

from openai import OpenAI

from utils.env import get_env

from .base import ModelProvider
from .shared import ModelCapabilities, ModelResponse, ProviderType


class OpenAIResponsesProvider(ModelProvider):
    """Provider for OpenAI's Responses API (/v1/responses endpoint).

    This is a completely different API from Chat Completions, designed for
    reasoning models that support extended thinking and stateful context.
    """

    PROVIDER_TYPE = ProviderType.OPENAI
    FRIENDLY_NAME = "OpenAI Responses API"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpenAI Responses API provider.

        Args:
            api_key: OpenAI API key. If not provided, reads from environment.
        """
        api_key = api_key or get_env("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key required for Responses API")

        super().__init__(api_key=api_key)
        self._client = None  # Lazy initialization via property

    @property
    def client(self):
        """Lazy initialization of OpenAI client with test transport support.

        Follows the same pattern as OpenAICompatibleProvider to support
        HTTP transport injection for cassette recording/replay in tests.
        """
        if self._client is None:
            import httpx

            # Check for test transport injection (for cassette recording/replay)
            if hasattr(self, "_test_transport"):
                # Use custom transport for testing
                http_client = httpx.Client(
                    transport=self._test_transport,
                    timeout=httpx.Timeout(30.0),
                    follow_redirects=True,
                )
            else:
                # Normal production client
                http_client = httpx.Client(
                    timeout=httpx.Timeout(30.0),
                    follow_redirects=True,
                )

            # Create OpenAI client with custom httpx client
            self._client = OpenAI(
                api_key=self.api_key,
                http_client=http_client,
            )

        return self._client

    def close(self):
        """Close the OpenAI client and release resources."""
        try:
            if hasattr(self, "_client") and self._client is not None:
                self._client.close()
        except Exception:
            # Suppress errors during cleanup
            pass

    def __del__(self):
        """Ensure client is closed when provider is garbage collected."""
        try:
            self.close()
        except Exception:
            # Suppress all errors during garbage collection
            pass

    def get_provider_type(self) -> ProviderType:
        """Return the provider type."""
        return self.PROVIDER_TYPE

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
        images: Optional[list[str]] = None,
        files: Optional[list[str]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using the Responses API.

        Args:
            prompt: User prompt
            model_name: Model name (e.g., "o3", "gpt-5-pro")
            system_prompt: System instructions
            temperature: Not used for reasoning models
            max_output_tokens: Maximum tokens to generate
            images: Images to include (if model supports vision)
            files: Document files to include (PDF, docs, etc.)
                   Files are Base64-encoded and embedded in the request (zero persistence).
                   No Files API upload or file_search tool required.
            **kwargs: Additional parameters

        Returns:
            ModelResponse with generated content
        """
        # Prepare input messages for responses endpoint
        input_messages = []

        # Add user prompt with optional images and files
        user_content = [{"type": "input_text", "text": prompt}]

        # Add images if provided and model supports them
        if images:
            for image_path in images:
                try:
                    # Process image (base64 encode or URL)
                    image_content = self._process_image(image_path)
                    if image_content:
                        user_content.append(image_content)
                except Exception as e:
                    logging.warning(f"Failed to process image {image_path}: {e}")

        # Handle file attachments via Base64 File Inputs (zero persistence)
        if files:
            logging.info(f"Attaching {len(files)} file(s) via Base64 File Inputs (zero persistence)")
            try:
                file_items = self._prepare_input_files(files)
                user_content.extend(file_items)
            except Exception as e:
                logging.error(f"Failed to prepare file inputs: {e}")
                raise ValueError(f"Failed to prepare file inputs: {e}")

        # Add user message with all content (text, images, files)
        input_messages.append({"role": "user", "content": user_content})

        # Get reasoning effort level with defensive mapping
        # This provides fallback in case upstream didn't map thinking_mode → reasoning_effort
        from utils.reasoning import resolve_reasoning_effort

        reasoning_effort = resolve_reasoning_effort(
            reasoning_effort=kwargs.get("reasoning_effort"),
            thinking_mode=kwargs.get("thinking_mode"),
            default_reasoning_effort=None,  # Default handled by fallback below
        )

        # Final fallback to medium
        if not reasoning_effort or reasoning_effort not in ["low", "medium", "high"]:
            reasoning_effort = "medium"

        # Prepare request parameters
        request_params = {
            "model": model_name,
            "input": input_messages,
            "reasoning": {"effort": reasoning_effort},
            "store": kwargs.get("store", False),  # Zero persistence: conversations not saved on server
        }

        # Add system prompt as instructions if provided
        if system_prompt:
            request_params["instructions"] = system_prompt

        # Merge tools from kwargs if provided
        existing_tools = kwargs.get("tools", [])
        if existing_tools:
            request_params["tools"] = list(existing_tools)  # Copy to avoid mutation

        # Note: File Inputs do not require file_search tool
        # Files are directly embedded in the request context via Base64

        # Pass through tool_resources if provided
        if "tool_resources" in kwargs:
            request_params["tool_resources"] = kwargs["tool_resources"]

        if max_output_tokens:
            request_params["max_output_tokens"] = max_output_tokens

        # Log sanitized request
        logging.info(f"Responses API request to {model_name} with effort={reasoning_effort}")

        try:
            # Call the Responses API
            response = self.client.responses.create(**request_params)

            # Extract content from response
            content = self._extract_content(response)

            # Extract usage information
            usage = self._extract_usage(response)

            return ModelResponse(
                content=content,
                usage=usage,
                model_name=model_name,
                friendly_name=self.FRIENDLY_NAME,
                provider=self.PROVIDER_TYPE,
                metadata={
                    "model": getattr(response, "model", model_name),
                    "id": getattr(response, "id", ""),
                    "created": getattr(response, "created_at", 0),
                    "endpoint": "responses",
                    "reasoning_effort": reasoning_effort,
                },
            )

        except Exception as exc:
            error_msg = f"Responses API error for {model_name}: {exc}"
            logging.error(error_msg)
            raise RuntimeError(error_msg) from exc

    def _prepare_input_files(self, files: list[str]) -> list[dict]:
        """Prepare file inputs via Base64 encoding (zero persistence).

        This method implements File Inputs for single-conversation document analysis.
        Files are Base64-encoded and embedded directly in the request context.

        Advantages:
        - Zero persistence: No Files API upload, no storage quota usage
        - No cleanup required: Files disposed after request completes
        - Direct document reading: Model processes both text and page images
        - Lower cost: Only token fees, no vector storage fees (no file_search)

        Limitations and Constraints:
        - Primary limit: Model context window capacity (token count, not bytes)
        - Base64 expansion: Files grow by ~4/3 (e.g., 37.5MB → 50MB encoded)
        - Large files: May be rejected by API if they exceed token capacity
        - Consider splitting pages or extracting key sections for very large files
        - Not suitable for: Large-scale RAG or persistent cross-session reuse

        Note on size limits:
        OpenAI does not publish a hard byte limit for Base64 file inputs.
        The real constraint is the model's context window. Very large files may
        be rejected if they exceed token capacity after PDF parsing (text + images).
        This implementation does not enforce size limits - the API will return an
        error if files are too large for the model's context.

        Args:
            files: List of file paths (local files or HTTP(S) URLs)

        Returns:
            List of input_file content items for Responses API

        Raises:
            FileNotFoundError: If local file doesn't exist

        Reference:
            https://platform.openai.com/docs/guides/pdf-files
        """
        items = []
        total_bytes = 0

        for file_path in files:
            # Handle HTTP(S) URLs - pass through directly
            if isinstance(file_path, str) and file_path.startswith(("http://", "https://")):
                items.append({"type": "input_file", "file_url": file_path})
                logging.info(f"Using file URL: {file_path}")
                continue

            # Handle local files - Base64 encode
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            original_size = os.path.getsize(file_path)

            # Read and Base64 encode
            with open(file_path, "rb") as f:
                file_data = base64.b64encode(f.read()).decode("utf-8")

            # Track encoded size for logging (Base64 expands by ~4/3)
            encoded_size = len(file_data)

            items.append(
                {
                    "type": "input_file",
                    "filename": os.path.basename(file_path),
                    "file_data": file_data,
                }
            )

            total_bytes += encoded_size
            logging.info(
                f"Encoded file '{os.path.basename(file_path)}' as Base64 "
                f"(original: {original_size} bytes, encoded: {encoded_size} bytes, total: {total_bytes} bytes)"
            )

        logging.info(
            f"Prepared {len(items)} file(s) for Base64 File Inputs; total size: {total_bytes} bytes "
            f"({total_bytes / 1024 / 1024:.2f} MB)"
        )
        return items

    def _process_image(self, image_path: str) -> Optional[dict]:
        """Process image for Responses API.

        Responses API requires input_image type with image_url as string.
        Supports: HTTP(S) URLs, data URIs, and local files (converted to Base64).

        Args:
            image_path: Path to image, HTTP URL, or data URI

        Returns:
            Image content dict for API request in format:
            {"type": "input_image", "image_url": "<url_or_data_uri>"}

        Note:
            - HTTP/HTTPS URLs: passed through directly
            - Data URIs: validated and passed through
            - Local files: read and converted to Base64 data URI
        """
        import base64

        from utils.image_utils import validate_image

        try:
            # Data URL - validate and pass through
            if image_path.startswith("data:"):
                validate_image(image_path)
                return {"type": "input_image", "image_url": image_path}

            # HTTP/HTTPS URL - pass through directly
            if image_path.startswith(("http://", "https://")):
                return {"type": "input_image", "image_url": image_path}

            # Local file - read and encode to Base64 data URI
            image_bytes, mime_type = validate_image(image_path)
            encoded_data = base64.b64encode(image_bytes).decode("utf-8")
            data_uri = f"data:{mime_type};base64,{encoded_data}"

            logging.debug(f"Encoded local image '{image_path}' as {mime_type} data URI ({len(encoded_data)} chars)")
            return {"type": "input_image", "image_url": data_uri}

        except Exception as e:
            logging.warning(f"Failed to process image '{image_path}': {e}")
            return None

    def _extract_content(self, response) -> str:
        """Extract content from Responses API response.

        Args:
            response: API response object

        Returns:
            Extracted text content (always a string)
        """
        import json

        # Try different response formats
        content = None
        if hasattr(response, "output_text"):
            content = response.output_text
        elif hasattr(response, "output") and hasattr(response.output, "text"):
            content = response.output.text
        elif hasattr(response, "content"):
            content = response.content
        else:
            # Fallback to string representation
            content = str(response)

        # Ensure we always return a string
        if isinstance(content, str):
            return content
        elif isinstance(content, (list, dict)):
            # Convert structured content to JSON string
            return json.dumps(content, ensure_ascii=False, indent=2)
        else:
            # Convert any other type to string
            return str(content)

    def _extract_usage(self, response) -> Optional[dict]:
        """Extract usage information from response.

        Args:
            response: API response object

        Returns:
            Usage dict with token counts
        """

        def _safe_int(value) -> Optional[int]:
            """Safely extract integer value, returning None for Mock objects or invalid types."""
            if value is None:
                return None
            # Check if it's a real number (not a Mock)
            if isinstance(value, (int, float)):
                return int(value)
            # Try to convert string to int
            if isinstance(value, str):
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
            # If it's a Mock or other object, return None
            return None

        usage = {}

        # Try to extract from response.usage
        if hasattr(response, "usage") and response.usage is not None:
            usage_obj = response.usage

            # Handle Pydantic models (real API responses) - check for model_dump method
            if hasattr(usage_obj, "model_dump"):
                try:
                    usage_dict = usage_obj.model_dump()
                    input_val = _safe_int(usage_dict.get("input_tokens"))
                    output_val = _safe_int(usage_dict.get("output_tokens"))
                    if input_val is not None:
                        usage["input_tokens"] = input_val
                    if output_val is not None:
                        usage["output_tokens"] = output_val
                except Exception:
                    pass  # Fall through to other methods

            # Handle dict objects (mock tests)
            elif isinstance(usage_obj, dict):
                input_val = _safe_int(usage_obj.get("input_tokens"))
                output_val = _safe_int(usage_obj.get("output_tokens"))
                if input_val is not None:
                    usage["input_tokens"] = input_val
                if output_val is not None:
                    usage["output_tokens"] = output_val

        # Try to extract from top-level attributes (Responses API style)
        # Only if not already extracted from usage object
        if "input_tokens" not in usage and hasattr(response, "input_tokens"):
            input_val = _safe_int(response.input_tokens)
            if input_val is not None:
                usage["input_tokens"] = input_val

        if "output_tokens" not in usage and hasattr(response, "output_tokens"):
            output_val = _safe_int(response.output_tokens)
            if output_val is not None:
                usage["output_tokens"] = output_val

        # Calculate total only if both values are valid integers
        if "input_tokens" in usage and "output_tokens" in usage:
            usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]

        return usage if usage else None

    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a model.

        All Responses API models have similar capabilities focused on reasoning.

        Args:
            model_name: Model name

        Returns:
            ModelCapabilities for the model
        """
        # Base capabilities for all reasoning models
        return ModelCapabilities(
            model_name=model_name,
            friendly_name=f"OpenAI {model_name} (Responses API)",
            context_window=200000,  # Most reasoning models have large context
            max_output_tokens=32000,
            supports_extended_thinking=True,
            supports_system_prompts=True,
            supports_streaming=False,  # Responses API doesn't stream
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images="vision" in model_name.lower() or "o" in model_name.lower(),
            supports_temperature=False,  # Reasoning models use effort instead
            use_openai_response_api=True,  # Always true for this provider
            default_reasoning_effort="medium",
        )

    def validate_model_name(self, model_name: str) -> bool:
        """Check if model is supported by Responses API.

        Args:
            model_name: Model name to validate

        Returns:
            True if model is supported
        """
        # Models that require Responses API
        responses_models = {
            "o3",
            "o3-mini",
            "o3-pro",
            "o4",
            "o4-mini",
            "gpt-5-pro",
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
        }

        # Check if model is in the list (case-insensitive)
        model_lower = model_name.lower()
        return any(m in model_lower for m in responses_models)

    def test_connection(self) -> bool:
        """Test if the API connection works.

        Returns:
            True if connection successful
        """
        try:
            # Try a minimal request
            response = self.client.responses.create(
                model="o3-mini",
                input=[{"role": "user", "content": [{"type": "input_text", "text": "Hi"}]}],
                reasoning={"effort": "low"},
                max_output_tokens=10,
            )
            return bool(response)
        except Exception as e:
            logging.error(f"Responses API connection test failed: {e}")
            return False
