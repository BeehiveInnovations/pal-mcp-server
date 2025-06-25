# WSL (Windows Subsystem for Linux) Setup Guide

This guide provides detailed instructions for setting up Zen MCP Server on Windows using WSL.

## Prerequisites for WSL

```bash
# Update WSL and ensure you have a recent Ubuntu distribution
sudo apt update && sudo apt upgrade -y

# Install required system dependencies
sudo apt install -y python3-venv python3-pip curl git

# Install Node.js and npm (required for Claude Code CLI)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs

# Install Claude Code CLI globally
npm install -g @anthropic-ai/claude-code
```

## WSL-Specific Installation Steps

1. **Clone the repository in your WSL environment** (not in Windows filesystem):
   ```bash
   # Navigate to your home directory or preferred location in WSL
   cd ~
   
   # Clone the repository
   git clone https://github.com/BeehiveInnovations/zen-mcp-server.git
   cd zen-mcp-server
   ```

2. **Run the setup script**:
   ```bash
   # Make the script executable and run it
   chmod +x run-server.sh
   ./run-server.sh
   ```

3. **Verify Claude Code can find the MCP server**:
   ```bash
   # List configured MCP servers
   claude mcp list
   
   # You should see 'zen' listed in the output
   # If not, the setup script will provide the correct configuration
   ```

## Troubleshooting WSL Issues

### Python Environment Issues

```bash
# If you encounter Python virtual environment issues
sudo apt install -y python3.12-venv python3.12-dev

# Ensure pip is up to date
python3 -m pip install --upgrade pip
```

### Path Issues

- Always use the full WSL path for MCP configuration (e.g., `/home/YourName/zen-mcp-server/`)
- The setup script automatically detects WSL and configures the correct paths

### Claude Code Connection Issues

```bash
# If Claude Code can't connect to the MCP server, check the configuration
cat ~/.claude.json | grep -A 10 "zen"

# The configuration should show the correct WSL path to the Python executable
# Example: "/home/YourName/zen-mcp-server/.zen_venv/bin/python"
```

### Performance Tip

For best performance, keep your zen-mcp-server directory in the WSL filesystem (e.g., `~/zen-mcp-server`) rather than in the Windows filesystem (`/mnt/c/...`).