#!/bin/bash
# Wrapper script for Gemini CLI compatibility

# Get the directory of this script
DIR="$(cd "$(dirname "$0")" && pwd)"

# Change to the zen-mcp-server directory
cd "$DIR"

# Execute the Python server with all arguments passed through
exec .zen_venv/bin/python server.py "$@"