# Gemini CLI Setup

> **Note**: While PAL MCP Server connects successfully to Gemini CLI, tool invocation is not working
> correctly yet. We'll update this guide once the integration is fully functional.

This guide explains how to configure PAL MCP Server to work with [Gemini CLI](https://github.com/google-gemini/gemini-cli).

## Prerequisites

- PAL MCP Server installed and configured
- Gemini CLI installed
- At least one API key configured in your `.env` file

## Configuration

1. Edit `~/.gemini/settings.json` and add:

```json
{
  "mcpServers": {
    "pal": {
      "command": "/path/to/pal-mcp-server/pal-mcp-server"
    }
  }
}
```

2. Replace `/path/to/pal-mcp-server` with your actual PAL MCP installation path (the folder name may still be `pal-mcp-server`).

3. If the `pal-mcp-server` wrapper script doesn't exist, create it:

```bash
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
exec .pal_venv/bin/python server.py "$@"
```

Then make it executable: `chmod +x pal-mcp-server`

4. Restart Gemini CLI.

All 15 PAL tools are now available in your Gemini CLI session.
