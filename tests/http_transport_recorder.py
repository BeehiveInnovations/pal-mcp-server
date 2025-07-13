#!/usr/bin/env python3
"""
HTTP Transport Recorder for O3-Pro Testing

Custom httpx transport solution that replaces respx for recording/replaying
HTTP interactions. Provides full control over the recording process without
respx limitations.

Key Features:
- RecordingTransport: Wraps default transport, captures real HTTP calls
- ReplayTransport: Serves saved responses from cassettes
- TransportFactory: Auto-selects record vs replay mode
- JSON cassette format with data sanitization
"""

import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

import httpx

from .pii_sanitizer import PIISanitizer

logger = logging.getLogger(__name__)


class RecordingTransport(httpx.HTTPTransport):
    """Transport that wraps default httpx transport and records all interactions."""

    def __init__(self, cassette_path: str, capture_content: bool = True, sanitize: bool = True):
        super().__init__()
        self.cassette_path = Path(cassette_path)
        self.recorded_interactions = []
        self.capture_content = capture_content
        self.sanitizer = PIISanitizer() if sanitize else None

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle request by recording interaction and delegating to real transport."""
        logger.debug(f"🎬 RecordingTransport: Making request to {request.method} {request.url}")

        # Record request BEFORE making the call
        request_data = self._serialize_request(request)

        # Make real HTTP call using parent transport
        response = super().handle_request(request)

        logger.debug(f"🎬 RecordingTransport: Got response {response.status_code}")

        # Post-response content capture (proper approach)
        if self.capture_content:
            try:
                # Consume the response stream to capture content
                # Note: httpx automatically handles gzip decompression
                content_bytes = response.read()
                response.close()  # Close the original stream
                logger.debug(f"🎬 RecordingTransport: Captured {len(content_bytes)} bytes of decompressed content")

                # Serialize response with captured content
                response_data = self._serialize_response_with_content(response, content_bytes)

                # Create a new response with the same metadata but buffered content
                # If the original response was gzipped, we need to re-compress
                response_content = content_bytes
                if response.headers.get("content-encoding") == "gzip":
                    import gzip

                    logger.debug(f"🗜️ Re-compressing {len(content_bytes)} bytes with gzip...")
                    response_content = gzip.compress(content_bytes)
                    logger.debug(f"🗜️ Compressed to {len(response_content)} bytes")

                new_response = httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,  # Keep original headers intact
                    content=response_content,
                    request=request,
                    extensions=response.extensions,
                    history=response.history,
                )

                # Record the interaction
                self._record_interaction(request_data, response_data)

                return new_response

            except Exception as e:
                logger.warning(f"⚠️ Content capture failed: {e}, falling back to stub")
                import traceback

                logger.warning(f"⚠️ Full exception traceback:\n{traceback.format_exc()}")
                response_data = self._serialize_response(response)
                self._record_interaction(request_data, response_data)
                return response
        else:
            # Legacy mode: record with stub content
            response_data = self._serialize_response(response)
            self._record_interaction(request_data, response_data)
            return response

    def _record_interaction(self, request_data: dict[str, Any], response_data: dict[str, Any]):
        """Helper method to record interaction and save cassette."""
        interaction = {"request": request_data, "response": response_data}
        self.recorded_interactions.append(interaction)
        self._save_cassette()
        logger.debug(f"🎬 RecordingTransport: Saved cassette to {self.cassette_path}")

    def _serialize_request(self, request: httpx.Request) -> dict[str, Any]:
        """Serialize httpx.Request to JSON-compatible format."""
        # For requests, we can safely read the content since it's already been prepared
        # httpx.Request.content is safe to access multiple times
        content = request.content

        # Convert bytes to string for JSON serialization
        if isinstance(content, bytes):
            try:
                content_str = content.decode("utf-8")
            except UnicodeDecodeError:
                # Handle binary content (shouldn't happen for o3-pro API)
                content_str = content.hex()
        else:
            content_str = str(content) if content else ""

        request_data = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "headers": dict(request.headers),
            "content": self._sanitize_request_content(content_str),
        }

        # Apply PII sanitization if enabled
        if self.sanitizer:
            request_data = self.sanitizer.sanitize_request(request_data)

        return request_data

    def _serialize_response(self, response: httpx.Response) -> dict[str, Any]:
        """Serialize httpx.Response to JSON-compatible format (legacy method without content)."""
        # Legacy method for backward compatibility when content capture is disabled
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": {"note": "Response content not recorded to avoid httpx.ResponseNotRead exception"},
            "reason_phrase": response.reason_phrase,
        }

    def _serialize_response_with_content(self, response: httpx.Response, content_bytes: bytes) -> dict[str, Any]:
        """Serialize httpx.Response with captured content."""
        try:
            # Debug: check what we got
            logger.debug(f"🔍 Content type: {type(content_bytes)}, size: {len(content_bytes)}")
            logger.debug(f"🔍 First 100 chars: {content_bytes[:100]}")

            # Ensure we have bytes for base64 encoding
            if not isinstance(content_bytes, bytes):
                logger.warning(f"⚠️ Content is not bytes, converting from {type(content_bytes)}")
                if isinstance(content_bytes, str):
                    content_bytes = content_bytes.encode("utf-8")
                else:
                    content_bytes = str(content_bytes).encode("utf-8")

            # Encode content as base64 for JSON storage
            logger.debug(f"🔍 Base64 encoding {len(content_bytes)} bytes...")
            content_b64 = base64.b64encode(content_bytes).decode("utf-8")
            logger.debug(f"✅ Base64 encoded successfully, result length: {len(content_b64)}")

            response_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": {"data": content_b64, "encoding": "base64", "size": len(content_bytes)},
                "reason_phrase": response.reason_phrase,
            }

            # Apply PII sanitization if enabled
            if self.sanitizer:
                response_data = self.sanitizer.sanitize_response(response_data)

            return response_data
        except Exception as e:
            logger.error(f"🔍 Error in _serialize_response_with_content: {e}")
            import traceback

            logger.error(f"🔍 Full traceback: {traceback.format_exc()}")
            # Fall back to minimal info
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": {"error": f"Failed to serialize content: {e}"},
                "reason_phrase": response.reason_phrase,
            }

    def _sanitize_request_content(self, content: str) -> Any:
        """Sanitize request content to remove sensitive data."""
        try:
            if content.strip():
                data = json.loads(content)
                # Don't sanitize request content for now - it's user input
                return data
        except json.JSONDecodeError:
            pass
        return content

    def _save_cassette(self):
        """Save recorded interactions to cassette file."""
        # Ensure directory exists
        self.cassette_path.parent.mkdir(parents=True, exist_ok=True)

        # Save cassette
        cassette_data = {"interactions": self.recorded_interactions}

        self.cassette_path.write_text(json.dumps(cassette_data, indent=2, sort_keys=True))


class ReplayTransport(httpx.MockTransport):
    """Transport that replays saved HTTP interactions from cassettes."""

    def __init__(self, cassette_path: str):
        self.cassette_path = Path(cassette_path)
        self.interactions = self._load_cassette()
        super().__init__(self._handle_request)

    def _load_cassette(self) -> list:
        """Load interactions from cassette file."""
        if not self.cassette_path.exists():
            raise FileNotFoundError(f"Cassette file not found: {self.cassette_path}")

        try:
            cassette_data = json.loads(self.cassette_path.read_text())
            return cassette_data.get("interactions", [])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid cassette file format: {e}")

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle request by finding matching interaction and returning saved response."""
        logger.debug(f"🔍 ReplayTransport: Looking for {request.method} {request.url}")

        # Debug: show what we're trying to match
        request_signature = self._get_request_signature(request)
        logger.debug(f"🔍 Request signature: {request_signature}")

        # Debug: show actual request content
        content = request.content
        if hasattr(content, "read"):
            content = content.read()
        if isinstance(content, bytes):
            content_str = content.decode("utf-8", errors="ignore")
        else:
            content_str = str(content) if content else ""
        logger.debug(f"🔍 Actual request content: {content_str}")

        # Debug: show available signatures
        for i, interaction in enumerate(self.interactions):
            saved_signature = self._get_saved_request_signature(interaction["request"])
            saved_content = interaction["request"].get("content", {})
            logger.debug(f"🔍 Available signature {i}: {saved_signature}")
            logger.debug(f"🔍 Saved content {i}: {saved_content}")

        # Find matching interaction
        interaction = self._find_matching_interaction(request)
        if not interaction:
            logger.warning("🚨 MYSTERY SOLVED: No matching interaction found! This should fail...")
            raise ValueError(f"No matching interaction found for {request.method} {request.url}")

        logger.debug("✅ Found matching interaction from cassette!")

        # Build response from saved data
        response_data = interaction["response"]

        # Convert content back to appropriate format
        content = response_data.get("content", {})
        if isinstance(content, dict):
            # Check if this is base64-encoded content
            if content.get("encoding") == "base64" and "data" in content:
                # Decode base64 content
                try:
                    content_bytes = base64.b64decode(content["data"])
                    logger.debug(f"🎬 ReplayTransport: Decoded {len(content_bytes)} bytes from base64")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to decode base64 content: {e}")
                    content_bytes = json.dumps(content).encode("utf-8")
            else:
                # Legacy format or stub content
                content_bytes = json.dumps(content).encode("utf-8")
        else:
            content_bytes = str(content).encode("utf-8")

        # Check if response expects gzipped content
        headers = response_data.get("headers", {})
        if headers.get("content-encoding") == "gzip":
            # Re-compress the content for httpx
            import gzip

            logger.debug(f"🗜️ ReplayTransport: Re-compressing {len(content_bytes)} bytes with gzip...")
            content_bytes = gzip.compress(content_bytes)
            logger.debug(f"🗜️ ReplayTransport: Compressed to {len(content_bytes)} bytes")

        logger.debug(f"🎬 ReplayTransport: Returning cassette response with content: {content_bytes[:100]}...")

        # Create httpx.Response
        return httpx.Response(
            status_code=response_data["status_code"],
            headers=response_data.get("headers", {}),
            content=content_bytes,
            request=request,
        )

    def _find_matching_interaction(self, request: httpx.Request) -> Optional[dict[str, Any]]:
        """Find interaction that matches the request."""
        request_signature = self._get_request_signature(request)

        for interaction in self.interactions:
            saved_signature = self._get_saved_request_signature(interaction["request"])
            if request_signature == saved_signature:
                return interaction

        return None

    def _get_request_signature(self, request: httpx.Request) -> str:
        """Generate signature for request matching."""
        # Use method, path, and content hash for matching
        content = request.content
        if hasattr(content, "read"):
            content = content.read()

        if isinstance(content, bytes):
            content_str = content.decode("utf-8", errors="ignore")
        else:
            content_str = str(content) if content else ""

        # Parse JSON and re-serialize with sorted keys for consistent hashing
        try:
            if content_str.strip():
                content_dict = json.loads(content_str)
                content_str = json.dumps(content_dict, sort_keys=True)
        except json.JSONDecodeError:
            # Not JSON, use as-is
            pass

        # Create hash of content for stable matching
        content_hash = hashlib.md5(content_str.encode()).hexdigest()

        return f"{request.method}:{request.url.path}:{content_hash}"

    def _get_saved_request_signature(self, saved_request: dict[str, Any]) -> str:
        """Generate signature for saved request."""
        method = saved_request["method"]
        path = saved_request["path"]

        # Hash the saved content
        content = saved_request.get("content", "")
        if isinstance(content, dict):
            content_str = json.dumps(content, sort_keys=True)
        else:
            content_str = str(content)

        content_hash = hashlib.md5(content_str.encode()).hexdigest()

        return f"{method}:{path}:{content_hash}"


class TransportFactory:
    """Factory for creating appropriate transport based on cassette availability."""

    @staticmethod
    def create_transport(cassette_path: str) -> httpx.HTTPTransport:
        """Create transport based on cassette existence and API key availability."""
        cassette_file = Path(cassette_path)

        # Check if we should record or replay
        if cassette_file.exists():
            # Cassette exists - use replay mode
            return ReplayTransport(cassette_path)
        else:
            # No cassette - use recording mode
            # Note: We'll check for API key in the test itself
            return RecordingTransport(cassette_path)

    @staticmethod
    def should_record(cassette_path: str, api_key: Optional[str] = None) -> bool:
        """Determine if we should record based on cassette and API key availability."""
        cassette_file = Path(cassette_path)

        # Record if cassette doesn't exist AND we have API key
        return not cassette_file.exists() and bool(api_key)

    @staticmethod
    def should_replay(cassette_path: str) -> bool:
        """Determine if we should replay based on cassette availability."""
        cassette_file = Path(cassette_path)
        return cassette_file.exists()


# Example usage:
#
# # In test setup:
# cassette_path = "tests/cassettes/o3_pro_basic_math.json"
# transport = TransportFactory.create_transport(cassette_path)
#
# # Inject into OpenAI client:
# provider._test_transport = transport
#
# # The provider's client property will detect _test_transport and use it
