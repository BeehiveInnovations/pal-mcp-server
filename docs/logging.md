# Logging

## Quick Start - Follow Logs

The easiest way to monitor logs is to use the `-f` flag when starting the server:

```bash
# Start server and automatically follow MCP logs
./run-server.sh -f
```

This will start the server and immediately begin tailing the MCP server logs.

## Log Files

Logs are stored in the `logs/` directory within your project folder:

- **`mcp_server.log`** - Main server operations, API calls, and errors
- **`mcp_activity.log`** - Tool calls and conversation tracking

Log files rotate automatically when they reach 20MB, keeping up to 10 rotated files.

## Viewing Logs

To monitor MCP server activity:

```bash
# Follow logs in real-time
tail -f logs/mcp_server.log

# View last 100 lines
tail -n 100 logs/mcp_server.log

# View activity logs (tool calls only)
tail -f logs/mcp_activity.log

# Search for specific patterns
grep "ERROR" logs/mcp_server.log
grep "tool_name" logs/mcp_activity.log
```

## Log Level

Set verbosity with `LOG_LEVEL` in your `.env` file:

```env
# Options: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
```

- **DEBUG**: Detailed information for debugging
- **INFO**: General operational messages (default)
- **WARNING**: Warning messages
- **ERROR**: Only error messages

## Log Format

Logs use a standardized format with timestamps:

```
2024-06-14 10:30:45,123 - module.name - INFO - Message here
```

## Tips

- Use `./run-server.sh -f` for the easiest log monitoring experience
- Activity logs show only tool-related events for cleaner output
- Main server logs include all operational details
- Logs persist across server restarts