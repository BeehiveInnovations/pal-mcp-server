"""
Version Tool - Display Zen MCP Server version and system information

This tool provides version information about the Zen MCP Server including
version number, last update date, author, and basic system information.
It also checks for updates from the GitHub repository.
"""

import logging
import platform
import re
import sys
from pathlib import Path
from typing import Any, Optional

try:
    from urllib.error import HTTPError, URLError
    from urllib.request import urlopen

    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False

from mcp.types import TextContent

from config import __author__, __updated__, __version__
from tools.models import ToolModelCategory, ToolOutput
from tools.shared.base_models import ToolRequest
from tools.shared.base_tool import BaseTool

logger = logging.getLogger(__name__)


def parse_version(version_str: str) -> tuple[int, int, int]:
    """
    Parse version string to tuple of integers for comparison.

    Args:
        version_str: Version string like "5.5.5"

    Returns:
        Tuple of (major, minor, patch) as integers
    """
    try:
        parts = version_str.strip().split(".")
        if len(parts) >= 3:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        elif len(parts) == 2:
            return (int(parts[0]), int(parts[1]), 0)
        elif len(parts) == 1:
            return (int(parts[0]), 0, 0)
        else:
            return (0, 0, 0)
    except (ValueError, IndexError):
        return (0, 0, 0)


def compare_versions(current: str, remote: str) -> int:
    """
    Compare two version strings.

    Args:
        current: Current version string
        remote: Remote version string

    Returns:
        -1 if current < remote (update available)
         0 if current == remote (up to date)
         1 if current > remote (ahead of remote)
    """
    current_tuple = parse_version(current)
    remote_tuple = parse_version(remote)

    if current_tuple < remote_tuple:
        return -1
    elif current_tuple > remote_tuple:
        return 1
    else:
        return 0


def fetch_github_version() -> Optional[tuple[str, str]]:
    """
    Fetch the latest version information from GitHub repository.

    Returns:
        Tuple of (version, last_updated) if successful, None if failed
    """
    if not HAS_URLLIB:
        logger.warning("urllib not available, cannot check for updates")
        return None

    github_url = "https://raw.githubusercontent.com/BeehiveInnovations/zen-mcp-server/main/config.py"

    try:
        # Set a 10-second timeout
        with urlopen(github_url, timeout=10) as response:
            if response.status != 200:
                logger.warning(f"HTTP error while checking GitHub: {response.status}")
                return None

            content = response.read().decode("utf-8")

            # Extract version using regex
            version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            updated_match = re.search(r'__updated__\s*=\s*["\']([^"\']+)["\']', content)

            if version_match:
                remote_version = version_match.group(1)
                remote_updated = updated_match.group(1) if updated_match else "Unknown"
                return (remote_version, remote_updated)
            else:
                logger.warning("Could not parse version from GitHub config.py")
                return None

    except HTTPError as e:
        logger.warning(f"HTTP error while checking GitHub: {e.code}")
        return None
    except URLError as e:
        logger.warning(f"URL error while checking GitHub: {e.reason}")
        return None
    except Exception as e:
        logger.warning(f"Error checking GitHub for updates: {e}")
        return None


class VersionTool(BaseTool):
    """
    Tool for displaying Zen MCP Server version and system information.

    This tool provides:
    - Current server version
    - Last update date
    - Author information
    - Python version
    - Platform information
    """

    def get_name(self) -> str:
        return "version"

    def get_description(self) -> str:
        return (
            "VERSION & CONFIGURATION - Get server version, configuration details, and list of available tools. "
            "Useful for debugging and understanding capabilities."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Return the JSON schema for the tool's input"""
        return {
            "type": "object",
            "properties": {"model": {"type": "string", "description": "Model to use (ignored by version tool)"}},
            "required": [],
        }

    def get_annotations(self) -> Optional[dict[str, Any]]:
        """Return tool annotations indicating this is a read-only tool"""
        return {"readOnlyHint": True}

    def get_system_prompt(self) -> str:
        """No AI model needed for this tool"""
        return ""

    def get_request_model(self):
        """Return the Pydantic model for request validation."""
        return ToolRequest

    def requires_model(self) -> bool:
        return False

    async def prepare_prompt(self, request: ToolRequest) -> str:
        """Not used for this utility tool"""
        return ""

    def format_response(self, response: str, request: ToolRequest, model_info: dict = None) -> str:
        """Not used for this utility tool"""
        return response

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        """
        Display Zen MCP Server version and system information.

        This overrides the base class execute to provide direct output without AI model calls.

        Args:
            arguments: Standard tool arguments (none required)

        Returns:
            Formatted version and system information
        """
        output_lines = ["# Zen MCP Server Version\n"]

        # Server version information
        output_lines.append("## Server Information")
        output_lines.append(f"**Current Version**: {__version__}")
        output_lines.append(f"**Last Updated**: {__updated__}")
        output_lines.append(f"**Author**: {__author__}")

        # Try to get client information
        try:
            # We need access to the server instance
            # This is a bit hacky but works for now
            import server as server_module
            from utils.client_info import format_client_info, get_client_info_from_context

            client_info = get_client_info_from_context(server_module.server)
            if client_info:
                formatted = format_client_info(client_info)
                output_lines.append(f"**Connected Client**: {formatted}")
        except Exception as e:
            logger.debug(f"Could not get client info: {e}")

        # Get the current working directory (MCP server location)
        current_path = Path.cwd()
        output_lines.append(f"**Installation Path**: `{current_path}`")
        output_lines.append("")

        # Check for updates from GitHub
        output_lines.append("## Update Status")

        try:
            github_info = fetch_github_version()

            if github_info:
                remote_version, remote_updated = github_info
                comparison = compare_versions(__version__, remote_version)

                output_lines.append(f"**Latest Version (GitHub)**: {remote_version}")
                output_lines.append(f"**Latest Updated**: {remote_updated}")

                if comparison < 0:
                    # Update available
                    output_lines.append("")
                    output_lines.append("🚀 **UPDATE AVAILABLE!**")
                    output_lines.append(
                        f"Your version `{__version__}` is older than the latest version `{remote_version}`"
                    )
                    output_lines.append("")
                    output_lines.append("**To update:**")
                    output_lines.append("```bash")
                    output_lines.append(f"cd {current_path}")
                    output_lines.append("git pull")
                    output_lines.append("```")
                    output_lines.append("")
                    output_lines.append("*Note: Restart your session after updating to use the new version.*")
                elif comparison == 0:
                    # Up to date
                    output_lines.append("")
                    output_lines.append("✅ **UP TO DATE**")
                    output_lines.append("You are running the latest version.")
                else:
                    # Ahead of remote (development version)
                    output_lines.append("")
                    output_lines.append("🔬 **DEVELOPMENT VERSION**")
                    output_lines.append(
                        f"Your version `{__version__}` is ahead of the published version `{remote_version}`"
                    )
                    output_lines.append("You may be running a development or custom build.")
            else:
                output_lines.append("❌ **Could not check for updates**")
                output_lines.append("Unable to connect to GitHub or parse version information.")
                output_lines.append("Check your internet connection or try again later.")

        except Exception as e:
            logger.error(f"Error during version check: {e}")
            output_lines.append("❌ **Error checking for updates**")
            output_lines.append(f"Error: {str(e)}")

        output_lines.append("")

        # Configuration information
        output_lines.append("## Configuration")

        # Check for configured providers
        try:
            from providers.base import ProviderType
            from providers.registry import ModelProviderRegistry

            provider_status = []

            # Check each provider type
            provider_types = [
                ProviderType.GOOGLE,
                ProviderType.OPENAI,
                ProviderType.XAI,
                ProviderType.DIAL,
                ProviderType.OPENROUTER,
                ProviderType.CUSTOM,
            ]
            provider_names = ["Google Gemini", "OpenAI", "X.AI", "DIAL", "OpenRouter", "Custom/Local"]

            for provider_type, provider_name in zip(provider_types, provider_names):
                provider = ModelProviderRegistry.get_provider(provider_type)
                status = "✅ Configured" if provider is not None else "❌ Not configured"
                provider_status.append(f"- **{provider_name}**: {status}")

            output_lines.append("**Providers**:")
            output_lines.extend(provider_status)

            # Get total available models
            try:
                available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)
                output_lines.append(f"\n\n**Available Models**: {len(available_models)}")
            except Exception:
                output_lines.append("\n\n**Available Models**: Unknown")

        except Exception as e:
            logger.warning(f"Error checking provider configuration: {e}")
            output_lines.append("\n\n**Providers**: Error checking configuration")

        output_lines.append("")

        # Format output
        content = "\n".join(output_lines)

        tool_output = ToolOutput(
            status="success",
            content=content,
            content_type="text",
            metadata={
                "tool_name": self.name,
                "server_version": __version__,
                "last_updated": __updated__,
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "platform": f"{platform.system()} {platform.release()}",
            },
        )

        return [TextContent(type="text", text=tool_output.model_dump_json())]

    def get_model_category(self) -> ToolModelCategory:
        """Return the model category for this tool."""
        return ToolModelCategory.FAST_RESPONSE  # Simple version info, no AI needed
