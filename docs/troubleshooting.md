# Troubleshooting Guide

## Quick Debugging Steps

If you're experiencing issues with the PAL MCP Server, follow these steps:

### 1. Check MCP Connection

Open Claude Desktop and type `/mcp` to see if pal is connected:
- ✅ If pal appears in the list, the connection is working
- ❌ If not listed or shows an error, continue to step 2

### 2. Launch Claude with Debug Mode

Close Claude Desktop and restart with debug logging:

```bash
# macOS/Linux
claude --debug

# Windows (in WSL2)
claude.exe --debug
```

Look for error messages in the console output, especially:
- API key errors
- Python/environment issues
- File permission errors

### 3. Verify API Keys

Check that your API keys are properly set:

```bash
# Check your .env file
cat .env

# Ensure at least one key is set:
# GEMINI_API_KEY=your-key-here
# OPENAI_API_KEY=your-key-here
```

If you need to update your API keys, edit the `.env` file and then restart Claude for changes to take effect.

### 4. Check Server Logs

View the server logs for detailed error information:

```bash
# View recent logs
tail -n 100 logs/mcp_server.log

# Follow logs in real-time
tail -f logs/mcp_server.log

# Or use the -f flag when starting to automatically follow logs
./run-server.sh -f

# Search for errors
grep "ERROR" logs/mcp_server.log
```

See [Logging Documentation](logging.md) for more details on accessing logs.

### 5. Common Issues

**"Connection failed" in Claude Desktop**
- Ensure the server path is correct in your Claude config
- Run `./run-server.sh` to verify setup and see configuration
- Check that Python is installed: `python3 --version`

**"API key environment variable is required"**
- Add your API key to the `.env` file
- Restart Claude Desktop after updating `.env`

**Claude Code CLI: API keys not passed to MCP server** (Known Bug)

When using Claude Code CLI with `env` blocks in MCP configuration, environment variables may not be passed correctly to the server. This is due to a [known issue](https://github.com/anthropics/claude-code/issues/1254) where Claude Code replaces `process.env` entirely instead of merging it.

**Symptoms:**
- Server logs show `OPENAI_API_KEY: [MISSING]` even though keys are defined in config
- Server crashes with "At least one API configuration is required"

**Workaround - Use a wrapper script:**

1. Create `/usr/local/bin/pal-mcp-wrapper`:
   ```bash
   #!/bin/bash
   # Source API keys from secure env file
   if [ -f /etc/pal-mcp/env ]; then
       source /etc/pal-mcp/env
   fi
   # Find uvx in common locations
   for p in /usr/local/bin/uvx "$HOME/.local/bin/uvx" $(which uvx 2>/dev/null); do
       if [ -x "$p" ]; then
           exec "$p" --from git+https://github.com/BeehiveInnovations/pal-mcp-server.git pal-mcp-server "$@"
       fi
   done
   echo "uvx not found" >&2
   exit 1
   ```

2. Create `/etc/pal-mcp/env` with your API keys:
   ```bash
   export OPENAI_API_KEY="your-key-here"
   export GEMINI_API_KEY="your-key-here"
   ```

3. Make executable and secure:
   ```bash
   sudo chmod +x /usr/local/bin/pal-mcp-wrapper
   sudo chmod 600 /etc/pal-mcp/env
   ```

4. Configure Claude Code (removes broken env block):
   ```bash
   claude mcp remove pal -s local 2>/dev/null
   claude mcp add pal /usr/local/bin/pal-mcp-wrapper -s user
   ```

5. If using `uvx`, ensure `uv` is in a system-wide path:
   ```bash
   sudo cp ~/.local/bin/uv /usr/local/bin/uv
   ```

**File path errors**
- Always use absolute paths: `/Users/you/project/file.py`
- Never use relative paths: `./file.py`

**Python module not found**
- Run `./run-server.sh` to reinstall dependencies
- Check virtual environment is activated: should see `.pal_venv` in the Python path

### 6. Environment Issues

**Virtual Environment Problems**
```bash
# Reset environment completely
rm -rf .pal_venv
./run-server.sh
```

**Permission Issues**
```bash
# Ensure script is executable
chmod +x run-server.sh
```

### 7. Still Having Issues?

If the problem persists after trying these steps:

1. **Reproduce the issue** - Note the exact steps that cause the problem
2. **Collect logs** - Save relevant error messages from Claude debug mode and server logs
3. **Open a GitHub issue** with:
   - Your operating system
   - Python version: `python3 --version`
   - Error messages from logs
   - Steps to reproduce
   - What you've already tried

## Windows Users

**Important**: Windows users must use WSL2. Install it with:

```powershell
wsl --install -d Ubuntu
```

Then follow the standard setup inside WSL2.