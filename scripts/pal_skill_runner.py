#!/usr/bin/env python3
"""
PAL Skill Runner - Lightweight CLI entry point for calling PAL tools directly.

This runner executes tools without starting the MCP server, making it suitable
for Skills mode where tools are called directly from the command line.

Usage:
    python pal_skill_runner.py --skill pal-chat --input '{"prompt": "...", ...}'
    echo '{"prompt": "..."}' | python pal_skill_runner.py --skill pal-chat
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# =============================================================================
# Skill Registry - Maps skill names to tool module paths
# =============================================================================

SKILL_REGISTRY = {
    # Core skills
    "pal-chat": "tools.chat:ChatTool",
    "pal-thinkdeep": "tools.thinkdeep:ThinkDeepTool",
    "pal-codereview": "tools.codereview:CodeReviewTool",
    "pal-planner": "tools.planner:PlannerTool",
    "pal-consensus": "tools.consensus:ConsensusTool",
    "pal-debug": "tools.debug:DebugIssueTool",
    "pal-precommit": "tools.precommit:PrecommitTool",
    "pal-challenge": "tools.challenge:ChallengeTool",
    "pal-apilookup": "tools.apilookup:LookupTool",
    "pal-clink": "tools.clink:CLinkTool",
    "pal-listmodels": "tools.listmodels:ListModelsTool",
    # Optional skills
    "pal-analyze": "tools.analyze:AnalyzeTool",
    "pal-refactor": "tools.refactor:RefactorTool",
    "pal-testgen": "tools.testgen:TestGenTool",
    "pal-secaudit": "tools.secaudit:SecauditTool",
    "pal-docgen": "tools.docgen:DocgenTool",
    "pal-tracer": "tools.tracer:TracerTool",
}

# =============================================================================
# Path Resolution
# =============================================================================


def resolve_pal_root() -> Path:
    """
    Resolve the PAL MCP Server root directory.

    Priority:
    1. PAL_MCP_SERVER_ROOT environment variable
    2. .pal_config file in scripts directory (written during installation)
    3. Parent of this script's directory (development mode)
    """
    # 1. Environment variable
    env_root = os.getenv("PAL_MCP_SERVER_ROOT")
    if env_root:
        root = Path(env_root).expanduser().resolve()
        if root.exists():
            return root

    # 2. Config file (written during installation)
    script_dir = Path(__file__).resolve().parent
    config_file = script_dir / ".pal_config"
    if config_file.exists():
        try:
            content = config_file.read_text().strip()
            # Parse PAL_MCP_ROOT="..." format
            for line in content.split("\n"):
                if line.startswith("PAL_MCP_ROOT="):
                    root_path = line.split("=", 1)[1].strip().strip('"')
                    root = Path(root_path).expanduser().resolve()
                    if root.exists():
                        return root
        except Exception:
            pass

    # 3. Development mode: parent of scripts directory
    dev_root = script_dir.parent
    if (dev_root / "server.py").exists():
        return dev_root

    raise RuntimeError(
        "Cannot find PAL MCP Server root. "
        "Set PAL_MCP_SERVER_ROOT environment variable or run from project directory."
    )


# =============================================================================
# Environment Setup
# =============================================================================


def setup_environment(root: Path) -> None:
    """
    Set up the Python environment for tool execution.

    This includes:
    1. Adding the project root to sys.path
    2. Loading .env file
    3. Configuring AI providers (without importing server.py to avoid MCP init)
    4. Disabling verbose logging for clean output
    """
    # Add root to path
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    # Change to project root for relative path resolution
    os.chdir(root)

    # Force .env to override system environment variables for Skills mode
    # This ensures Skills use the project's .env configuration, not system env
    os.environ["PAL_MCP_FORCE_ENV_OVERRIDE"] = "true"

    # Enable SQLite storage for Skills mode (cross-process session persistence)
    # This allows continuation_id to work across separate skill invocations
    #
    # NOTE: Storage backend difference between modes:
    # - MCP Server mode: Uses in-memory storage (fast, single-process)
    # - Skills mode: Uses SQLite storage (cross-process persistence required)
    #
    # Sessions are isolated by default - continuation_id from one mode won't work in the other.
    # Database location: ~/.pal_mcp/sessions.db (or set PAL_SKILL_STORAGE_PATH to override)
    os.environ["PAL_SKILL_STORAGE"] = "sqlite"

    # Configure logging level for Skills mode
    # Use PAL_SKILL_LOG_LEVEL environment variable to control verbosity
    # Default: WARNING (suppress INFO/DEBUG messages for clean JSON output)
    # Options: DEBUG, INFO, WARNING, ERROR
    import logging

    log_level = os.environ.get("PAL_SKILL_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, log_level, logging.WARNING)
    logging.getLogger().setLevel(level)

    # Also apply same level to specific noisy loggers
    for logger_name in ["httpx", "httpcore", "openai", "utils", "tools", "providers"]:
        logging.getLogger(logger_name).setLevel(level)

    # Load environment variables from .env
    from utils.env import get_env, reload_env

    reload_env()

    # Configure AI providers using shared configuration
    # This ensures provider registration is consistent with MCP server mode
    # NOTE: require_at_least_one=True matches MCP server behavior (server.py:544-554)
    from providers.configuration import register_providers

    # Enable verbose logging for provider restrictions when log level is DEBUG or INFO
    verbose = level <= logging.INFO
    logger = logging.getLogger("pal_skill_runner") if verbose else None

    register_providers(get_env, verbose=verbose, logger=logger, require_at_least_one=True)


# =============================================================================
# Payload Handling
# =============================================================================


def load_payload(input_arg: str | None) -> dict:
    """
    Load the input payload from argument or stdin.

    Args:
        input_arg: JSON string or file path from --input argument

    Returns:
        Parsed dictionary payload
    """
    if input_arg:
        input_arg = input_arg.strip()

        # First, check if it looks like JSON (starts with { or [)
        # This avoids OSError "File name too long" when passing long JSON strings
        if input_arg.startswith("{") or input_arg.startswith("["):
            return json.loads(input_arg)

        # Check if it's a file path (only for non-JSON-looking strings)
        try:
            if Path(input_arg).exists():
                return json.loads(Path(input_arg).read_text())
        except OSError:
            # Path too long or other OS error - not a valid file path
            pass

        # Try parsing as JSON string anyway (handles edge cases)
        return json.loads(input_arg)

    # Try reading from stdin
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        if data:
            return json.loads(data)

    raise ValueError("No input provided. Use --input '{...}' or pipe JSON to stdin.")


def auto_fill_common_fields(payload: dict, skill_name: str) -> dict:
    """
    Auto-fill common required fields that can be inferred from context.

    This improves usability by automatically providing values that Claude Code
    knows (like current working directory) but may forget to include.

    Args:
        payload: Input parameters dictionary
        skill_name: The skill being executed

    Returns:
        Updated payload with auto-filled fields
    """
    original_cwd = os.environ.get("SKILL_ORIGINAL_CWD") or str(Path.home())

    # Auto-fill working_directory_absolute_path for tools that need it
    SKILLS_NEEDING_WORKING_DIR = {"pal-chat"}
    if skill_name in SKILLS_NEEDING_WORKING_DIR:
        if "working_directory_absolute_path" not in payload:
            payload["working_directory_absolute_path"] = original_cwd

    # Normalize file path fields - convert relative paths to absolute paths
    # based on the original working directory (not the pal-mcp-server directory)
    # _normalize_path handles URIs (http://, data:, etc.) and ~ expansion
    PATH_FIELDS = [
        "absolute_file_paths",
        "files_checked",
        "relevant_files",
        "images",
        "style_guide_examples",
        "path",  # for precommit
        "working_directory_absolute_path",  # also normalize if provided
    ]

    for field in PATH_FIELDS:
        if field in payload:
            value = payload[field]
            if isinstance(value, list):
                # Normalize each path in the list
                normalized = []
                for p in value:
                    if isinstance(p, str) and p:
                        normalized.append(_normalize_path(p, original_cwd))
                    else:
                        normalized.append(p)
                payload[field] = normalized
            elif isinstance(value, str) and value:
                payload[field] = _normalize_path(value, original_cwd)

    return payload


def _normalize_path(path: str, base_dir: str) -> str:
    """
    Normalize a file path to absolute path.

    If the path is relative, resolve it relative to base_dir.
    If already absolute, return as-is.
    Handles special cases: URIs, ~ expansion, etc.

    Args:
        path: File path (may be relative or absolute)
        base_dir: Base directory for resolving relative paths

    Returns:
        Absolute path (or original if URI)
    """
    if not path:
        return path

    # Skip URIs (http://, https://, file://, data:, etc.)
    import re

    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", path):
        return path

    # Expand ~ to user home directory
    path_obj = Path(path).expanduser()

    # Already absolute after expansion
    if path_obj.is_absolute():
        return str(path_obj)

    # Resolve relative path against base_dir
    return str((Path(base_dir) / path_obj).resolve())


# =============================================================================
# Tool Execution
# =============================================================================


def get_tool_instance(skill_name: str):
    """
    Get a tool instance by skill name.

    Args:
        skill_name: The skill name (e.g., "pal-chat")

    Returns:
        Instantiated tool object
    """
    if skill_name not in SKILL_REGISTRY:
        available = ", ".join(sorted(SKILL_REGISTRY.keys()))
        raise ValueError(f"Unknown skill: {skill_name}. Available: {available}")

    module_path, class_name = SKILL_REGISTRY[skill_name].split(":")

    # Dynamic import
    from importlib import import_module

    module = import_module(module_path)
    tool_cls = getattr(module, class_name)

    return tool_cls()


async def execute_tool(tool, payload: dict, skill_name: str) -> tuple[str, bool]:
    """
    Execute a tool with the given payload.

    This function uses shared entry point logic to ensure consistency with MCP server mode:
    1. continuation_id handling (thread context reconstruction)
    2. model:option parsing (e.g., model:for, model:against)
    3. Model resolution (handles 'auto' mode)
    4. ModelContext creation
    5. File size validation

    Args:
        tool: The tool instance
        payload: Input parameters dictionary
        skill_name: Name of the skill being executed

    Returns:
        Tuple of (JSON string result, success boolean)
        - success=True: Tool executed successfully
        - success=False: Error occurred (caller should use non-zero exit code)
    """
    from utils.model_resolution import ModelResolutionError
    from utils.tool_entry import FileSizeExceededError, prepare_tool_arguments

    try:
        # Use shared entry point logic (same as MCP server mode)
        payload = await prepare_tool_arguments(tool, payload, skill_name)
    except ModelResolutionError as e:
        # Enhance error message with pal-listmodels hint
        error_msg = str(e)
        error_msg += "\n\nTip: Use `pal-listmodels` skill to see all available models."
        return (
            json.dumps(
                {
                    "status": "error",
                    "content": error_msg,
                    "content_type": "text",
                    "metadata": {
                        "available_models": e.available_models,
                        "suggested_model": e.suggested_model,
                        "hint": "Use pal-listmodels skill to see all available models",
                    },
                }
            ),
            False,
        )
    except FileSizeExceededError as e:
        return json.dumps(e.error_response), False
    except ValueError as e:
        # Handle continuation_id errors
        return (
            json.dumps(
                {
                    "status": "error",
                    "content": str(e),
                    "content_type": "text",
                }
            ),
            False,
        )

    result = await tool.execute(payload)

    # Handle result and determine success status
    # MCP mode returns list[TextContent] directly; Skills mode serializes to JSON
    #
    # Output format matches MCP mode behavior:
    # - MCP mode: returns list[TextContent] via protocol
    # - Skills mode: returns the .text content from TextContent (already JSON)
    #
    # All tools return list[TextContent] where .text contains the full JSON response.
    # We extract .text directly to match what MCP clients receive after deserialization.

    if not result:
        return json.dumps({"status": "error", "content": "No response from tool"}), False

    # Standard MCP return format: list[TextContent]
    if isinstance(result, list) and len(result) > 0:
        first_item = result[0]

        # TextContent object with .text attribute
        if hasattr(first_item, "text"):
            text = first_item.text
            success = not _is_error_response(text)
            return text, success

        # List of strings (rare case)
        if isinstance(first_item, str):
            success = not _is_error_response(first_item)
            return first_item, success

        # List of dicts (rare case)
        if isinstance(first_item, dict):
            success = first_item.get("status") != "error"
            return json.dumps(first_item, ensure_ascii=False), success

    # Direct string return (rare case)
    if isinstance(result, str):
        success = not _is_error_response(result)
        return result, success

    # Direct dict return (rare case)
    if isinstance(result, dict):
        success = result.get("status") != "error"
        return json.dumps(result, ensure_ascii=False), success

    # Other types - attempt JSON serialization
    try:
        return json.dumps(result, ensure_ascii=False), True
    except (TypeError, ValueError):
        return str(result), True


def _is_error_response(text: str) -> bool:
    """
    Check if a text response indicates an error.

    This is used to determine the exit code for Skills mode.
    """
    if not text:
        return False
    # Try to parse as JSON and check status
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("status") == "error":
            return True
    except (json.JSONDecodeError, TypeError):
        pass
    return False


# =============================================================================
# Main Entry Point
# =============================================================================


def parse_dynamic_args(unknown_args: list) -> dict:
    """
    Parse unknown arguments into a dictionary.

    Supports formats:
    - --key value
    - --key=value
    - --flag (boolean True)

    Args:
        unknown_args: List of unparsed arguments

    Returns:
        Dictionary of parsed key-value pairs
    """
    result = {}
    i = 0
    while i < len(unknown_args):
        arg = unknown_args[i]
        if arg.startswith("--"):
            key = arg[2:]  # Remove '--' prefix

            # Handle --key=value format
            if "=" in key:
                key, value = key.split("=", 1)
                result[key] = _parse_value(value)
            # Handle --key value format
            elif i + 1 < len(unknown_args) and not unknown_args[i + 1].startswith("--"):
                result[key] = _parse_value(unknown_args[i + 1])
                i += 1
            # Handle --flag (boolean)
            else:
                result[key] = True
        i += 1
    return result


def _parse_value(value: str):
    """
    Parse a string value into appropriate type.

    Attempts to parse as JSON first (for arrays, objects, numbers, booleans),
    falls back to string.
    """
    # Try parsing as JSON (handles arrays, objects, numbers, booleans)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    # Return as string
    return value


def main():
    parser = argparse.ArgumentParser(
        description="PAL Skill Runner - Execute PAL tools directly",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --skill pal-chat --input '{"prompt": "Hello"}'
  %(prog)s --skill pal-chat --prompt "Hello" --thinking_mode medium
  echo '{"prompt": "Hello"}' | %(prog)s --skill pal-chat
  %(prog)s --list
        """,
    )
    parser.add_argument(
        "--skill",
        help="Skill name to execute (e.g., pal-chat, pal-codereview)",
    )
    parser.add_argument(
        "--input",
        help="JSON input string or path to JSON file",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available skills",
    )

    # Use parse_known_args to capture dynamic parameters
    args, unknown_args = parser.parse_known_args()

    # List skills mode
    if args.list:
        print("Available skills:")
        for skill in sorted(SKILL_REGISTRY.keys()):
            print(f"  - {skill}")
        return

    # Validate arguments
    if not args.skill:
        parser.error("--skill is required (or use --list to see available skills)")

    try:
        # Save original working directory before setup changes it
        original_cwd = os.getcwd()
        os.environ["SKILL_ORIGINAL_CWD"] = original_cwd

        # Resolve project root
        root = resolve_pal_root()

        # Setup environment (load .env, configure providers)
        setup_environment(root)

        # Load input payload - supports multiple formats:
        # 1. --input JSON (explicit JSON input)
        # 2. Dynamic args (--prompt "..." --model "...")
        # 3. stdin (piped JSON)
        if args.input:
            payload = load_payload(args.input)
        elif unknown_args:
            # Parse dynamic arguments into payload
            payload = parse_dynamic_args(unknown_args)
        else:
            # Try stdin
            payload = load_payload(None)

        # Auto-fill common fields (e.g., working_directory_absolute_path)
        payload = auto_fill_common_fields(payload, args.skill)

        # Get tool instance
        tool = get_tool_instance(args.skill)

        # Execute and print result
        result, success = asyncio.run(execute_tool(tool, payload, args.skill))
        print(result)

        # Exit with non-zero code on error (CLI best practice)
        if not success:
            sys.exit(1)

    except json.JSONDecodeError as e:
        error = {"status": "error", "content": f"Invalid JSON input: {e}"}
        print(json.dumps(error))
        sys.exit(1)
    except ValueError as e:
        error = {"status": "error", "content": str(e)}
        print(json.dumps(error))
        sys.exit(1)
    except Exception as e:
        error = {"status": "error", "content": f"Execution error: {e}"}
        print(json.dumps(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
