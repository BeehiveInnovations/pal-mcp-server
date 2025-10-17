"""
Custom exceptions for Zen MCP tools.

These exceptions allow tools to signal protocol-level errors that should be surfaced
to MCP clients using the `isError` flag on `CallToolResult`. Raising one of these
exceptions ensures the low-level server adapter marks the result as an error while
preserving the structured payload we pass through the exception message.
"""


class ToolExecutionError(RuntimeError):
    """Raised to indicate a tool-level failure that must set `isError=True`."""

    def __init__(self, payload: str):
        """
        Args:
            payload: Serialized error payload (typically JSON) to return to the client.
        """
        super().__init__(payload)
        self.payload = payload
