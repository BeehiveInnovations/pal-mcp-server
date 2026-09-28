#!/bin/bash
# Launcher for PAL/Zen MCP under Claude Code.
# Sources .env so API keys (GEMINI_API_KEY, etc.) stay in .env only,
# never baked into ~/.claude.json.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
exec "$DIR/.pal_venv/bin/python" "$DIR/server.py" "$@"
