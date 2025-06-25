# Gemini CLI Setup

> **Note**: While Zen MCP Server connects successfully to Gemini CLI, tool invocation is not working
> correctly yet. We'll update this guide once the integration is fully functional.

This guide explains how to configure Zen MCP Server to work with [Gemini CLI](https://github.com/google-gemini/gemini-cli).

## Prerequisites

- Zen MCP Server installed and configured
- Gemini CLI installed
- At least one API key configured in your `.env` file

## Configuration

1. Edit `~/.gemini/settings.json` and add:

```json
{
  "mcpServers": {
    "zen": {
      "command": "/path/to/zen-mcp-server/zen-mcp-server"
    }
  }
}
```

2. Replace `/path/to/zen-mcp-server` with your actual Zen installation path.

3. If the `zen-mcp-server` wrapper script doesn't exist, create it:

```bash
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
exec .zen_venv/bin/python server.py "$@"
```

Then make it executable: `chmod +x zen-mcp-server`

4. Restart Gemini CLI.

All 15 Zen tools are now available in your Gemini CLI session.