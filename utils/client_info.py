"""
Client Information Utility for MCP Server

This module provides utilities to extract and format client information
from the MCP protocol's clientInfo sent during initialization.

It also provides friendly name mapping and caching for consistent client
identification across the application.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Global cache for client information
_client_info_cache: Optional[dict[str, Any]] = None

# Mapping of known client names to friendly names
# This is case-insensitive and checks if the key is contained in the client name
CLIENT_NAME_MAPPINGS = {
    # Claude variants
    "claude-ai": "Claude",
    "claude": "Claude",
    "claude-desktop": "Claude",
    "claude-code": "Claude",
    "anthropic": "Claude",
    # Gemini variants
    "gemini-cli-mcp-client": "Gemini",
    "gemini-cli": "Gemini",
    "gemini": "Gemini",
    "google": "Gemini",
    # Other known clients
    "cursor": "Cursor",
    "vscode": "VS Code",
    "codeium": "Codeium",
    "copilot": "GitHub Copilot",
    # Generic MCP clients
    "mcp-client": "MCP Client",
    "test-client": "Test Client",
}

# Default friendly name when no match is found
DEFAULT_FRIENDLY_NAME = "Claude"


def get_friendly_name(client_name: str) -> str:
    """
    Map a client name to a friendly name.

    Args:
        client_name: The raw client name from clientInfo

    Returns:
        A friendly name for display (e.g., "Claude", "Gemini")
    """
    if not client_name:
        return DEFAULT_FRIENDLY_NAME

    # Convert to lowercase for case-insensitive matching
    client_name_lower = client_name.lower()

    # Check each mapping - using 'in' to handle partial matches
    for key, friendly_name in CLIENT_NAME_MAPPINGS.items():
        if key.lower() in client_name_lower:
            return friendly_name

    # If no match found, return the default
    return DEFAULT_FRIENDLY_NAME


def get_cached_client_info() -> Optional[dict[str, Any]]:
    """
    Get cached client information if available.

    Returns:
        Cached client info dictionary or None
    """
    global _client_info_cache
    return _client_info_cache


def get_client_info_from_context(server: Any) -> Optional[dict[str, Any]]:
    """
    Extract client information from the MCP server's request context.

    The MCP protocol sends clientInfo during initialization containing:
    - name: The client application name (e.g., "Claude Code", "Claude Desktop")
    - version: The client version string

    This function also adds a friendly_name field and caches the result.

    Args:
        server: The MCP server instance

    Returns:
        Dictionary with client info or None if not available:
        {
            "name": "claude-ai",
            "version": "1.0.0",
            "friendly_name": "Claude"
        }
    """
    global _client_info_cache

    # Return cached info if available
    if _client_info_cache is not None:
        return _client_info_cache

    try:
        # Try to access the request context and session
        if not server:
            return None

        # Check if server has request_context property
        request_context = None
        try:
            request_context = server.request_context
        except AttributeError:
            logger.debug("Server does not have request_context property")
            return None

        if not request_context:
            logger.debug("Request context is None")
            return None

        # Try to access session from request context
        session = None
        try:
            session = request_context.session
        except AttributeError:
            logger.debug("Request context does not have session property")
            return None

        if not session:
            logger.debug("Session is None")
            return None

        # Try to access client params from session
        client_params = None
        try:
            # The clientInfo is stored in _client_params.clientInfo
            client_params = session._client_params
        except AttributeError:
            logger.debug("Session does not have _client_params property")
            return None

        if not client_params:
            logger.debug("Client params is None")
            return None

        # Try to extract clientInfo
        client_info = None
        try:
            client_info = client_params.clientInfo
        except AttributeError:
            logger.debug("Client params does not have clientInfo property")
            return None

        if not client_info:
            logger.debug("Client info is None")
            return None

        # Extract name and version
        result = {}

        try:
            result["name"] = client_info.name
        except AttributeError:
            logger.debug("Client info does not have name property")

        try:
            result["version"] = client_info.version
        except AttributeError:
            logger.debug("Client info does not have version property")

        if not result:
            return None

        # Add friendly name
        raw_name = result.get("name", "")
        result["friendly_name"] = get_friendly_name(raw_name)

        # Cache the result
        _client_info_cache = result
        logger.debug(f"Cached client info: {result}")

        return result

    except Exception as e:
        logger.debug(f"Error extracting client info: {e}")
        return None


def format_client_info(client_info: Optional[dict[str, Any]], use_friendly_name: bool = True) -> str:
    """
    Format client information for display.

    Args:
        client_info: Dictionary with client info or None
        use_friendly_name: If True, use the friendly name instead of raw name

    Returns:
        Formatted string like "Claude v1.0.0" or "Claude"
    """
    if not client_info:
        return DEFAULT_FRIENDLY_NAME

    if use_friendly_name:
        name = client_info.get("friendly_name", client_info.get("name", DEFAULT_FRIENDLY_NAME))
    else:
        name = client_info.get("name", "Unknown")

    version = client_info.get("version", "")

    if version and not use_friendly_name:
        return f"{name} v{version}"
    else:
        # For friendly names, we just return the name without version
        return name


def get_client_friendly_name() -> str:
    """
    Get the cached client's friendly name.

    This is a convenience function that returns just the friendly name
    from the cached client info, defaulting to "Claude" if not available.

    Returns:
        The friendly name (e.g., "Claude", "Gemini")
    """
    cached_info = get_cached_client_info()
    if cached_info:
        return cached_info.get("friendly_name", DEFAULT_FRIENDLY_NAME)
    return DEFAULT_FRIENDLY_NAME


def log_client_info(server: Any, logger_instance: Optional[logging.Logger] = None) -> None:
    """
    Log client information extracted from the server.

    Args:
        server: The MCP server instance
        logger_instance: Optional logger to use (defaults to module logger)
    """
    log = logger_instance or logger

    client_info = get_client_info_from_context(server)
    if client_info:
        # Log with both raw and friendly names for debugging
        raw_name = client_info.get("name", "Unknown")
        friendly_name = client_info.get("friendly_name", DEFAULT_FRIENDLY_NAME)
        version = client_info.get("version", "")

        if raw_name != friendly_name:
            log.info(f"MCP Client Connected: {friendly_name} (raw: {raw_name} v{version})")
        else:
            log.info(f"MCP Client Connected: {friendly_name} v{version}")

        # Log to activity logger as well
        try:
            activity_logger = logging.getLogger("mcp_activity")
            activity_logger.info(f"CLIENT_IDENTIFIED: {friendly_name} (name={raw_name}, version={version})")
        except Exception:
            pass
    else:
        log.debug("Could not extract client info from MCP protocol")


# Example usage in tools:
#
# from utils.client_info import get_client_friendly_name, get_cached_client_info
#
# # In a tool's execute method:
# def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
#     # Get the friendly name of the connected client
#     client_name = get_client_friendly_name()  # Returns "Claude" or "Gemini" etc.
#
#     # Or get full cached info if needed
#     client_info = get_cached_client_info()
#     if client_info:
#         raw_name = client_info['name']        # e.g., "claude-ai"
#         version = client_info['version']      # e.g., "1.0.0"
#         friendly = client_info['friendly_name'] # e.g., "Claude"
#
#     # Customize response based on client
#     if client_name == "Claude":
#         response = f"Hello from Zen MCP Server to {client_name}!"
#     elif client_name == "Gemini":
#         response = f"Greetings {client_name}, welcome to Zen MCP Server!"
#     else:
#         response = f"Welcome {client_name}!"
