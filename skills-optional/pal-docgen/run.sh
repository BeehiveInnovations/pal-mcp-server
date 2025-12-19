#!/usr/bin/env bash
set -euo pipefail

# Get the directory where this script is located (resolving symlinks)
SOURCE="${BASH_SOURCE[0]}"
while [[ -L "$SOURCE" ]]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
SKILL_NAME="$(basename "${SCRIPT_DIR}")"

# Read PAL_MCP_ROOT from config file if exists (installed mode)
CONFIG_FILE="${SCRIPT_DIR}/scripts/.pal_config"
if [[ -f "$CONFIG_FILE" ]]; then
    PAL_MCP_ROOT="$(sed -n 's/^PAL_MCP_ROOT="\([^"]*\)".*/\1/p' "$CONFIG_FILE" 2>/dev/null || true)"
    if [[ -n "$PAL_MCP_ROOT" ]]; then
        export PAL_MCP_SERVER_ROOT="$PAL_MCP_ROOT"
    fi
fi

# Find the runner script
# Priority: 1) config-based path, 2) installed location, 3) development locations (up to 4 levels)
find_runner() {
    # 1) Use PAL_MCP_ROOT if available (from .pal_config or environment)
    if [[ -n "${PAL_MCP_SERVER_ROOT:-}" ]] && [[ -f "${PAL_MCP_SERVER_ROOT}/scripts/pal_skill_runner.py" ]]; then
        echo "${PAL_MCP_SERVER_ROOT}/scripts/pal_skill_runner.py"
        return 0
    fi

    # 2) Check installed location (runner copied to skill directory)
    if [[ -f "${SCRIPT_DIR}/scripts/pal_skill_runner.py" ]]; then
        echo "${SCRIPT_DIR}/scripts/pal_skill_runner.py"
        return 0
    fi

    # 3) Search upward for development locations (skills/, skills-optional/, etc.)
    local current="${SCRIPT_DIR}"
    for _ in {1..4}; do
        current="$(dirname "$current")"
        if [[ -f "$current/scripts/pal_skill_runner.py" ]]; then
            echo "$current/scripts/pal_skill_runner.py"
            return 0
        fi
    done

    return 1
}

RUNNER="$(find_runner)" || {
    echo "Error: pal_skill_runner.py not found" >&2
    echo "Searched: config path, ${SCRIPT_DIR}/scripts/, and up to 4 parent directories" >&2
    echo "Tip: Run from pal-mcp-server repo or execute ./install-skills.sh first" >&2
    exit 1
}

# Determine Python executable
if [[ -n "${PAL_MCP_SERVER_ROOT:-}" ]] && [[ -x "$PAL_MCP_SERVER_ROOT/.pal_venv/bin/python" ]]; then
    PYTHON_BIN="$PAL_MCP_SERVER_ROOT/.pal_venv/bin/python"
else
    PYTHON_BIN="$(command -v python3 || command -v python)"
fi

# Execute the runner with the skill name and pass all arguments
exec "$PYTHON_BIN" "$RUNNER" --skill "$SKILL_NAME" "$@"
