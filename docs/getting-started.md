# Getting Started with Zen MCP Server

This guide walks you through setting up the Zen MCP Server from scratch, including installation, configuration, and first usage.

## Prerequisites

- **Python 3.10+** (3.12 recommended)
- **Git**
- **[uv installed](https://docs.astral.sh/uv/getting-started/installation/)** (for uvx method)
- **Windows users**: WSL2 required for Claude Code CLI

## Step 1: Get API Keys

You need at least one API key. Choose based on your needs:

### Option A: OpenRouter (Recommended for beginners)
**One API for multiple models**
- Visit [OpenRouter](https://openrouter.ai/) and sign up
- Generate an API key
- Control spending limits in your dashboard
- Access GPT-4, Claude, Gemini, and more through one API

### Option B: Native Provider APIs

**Gemini (Google):**
- Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
- Generate an API key
- **Note**: For Gemini 2.5 Pro, use a paid API key (free tier has limited access)

**OpenAI:**
- Visit [OpenAI Platform](https://platform.openai.com/api-keys)
- Generate an API key for O3, GPT-5 access

**X.AI (Grok):**
- Visit [X.AI Console](https://console.x.ai/)
- Generate an API key for Grok models

**DIAL Platform:**
- Visit [DIAL Platform](https://dialx.ai/)
- Generate API key for vendor-agnostic model access

### Option C: Local Models (Free)

**Ollama:**
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# Pull a model (e.g., Llama 3.2)
ollama pull llama3.2
```

**Other local options:**
- **vLLM**: Self-hosted inference server
- **LM Studio**: Local model hosting with OpenAI-compatible API
- **Text Generation WebUI**: Popular local interface

👉 **[Complete custom model setup guide](custom_models.md)**

## Step 2: Installation

Choose your preferred installation method:

### Method A: Instant Setup with uvx (Recommended)

**Prerequisites**: [Install uv first](https://docs.astral.sh/uv/getting-started/installation/)

**For Claude Desktop:**
1. Open Claude Desktop → Settings → Developer → Edit Config
2. Add this configuration:

```json
{
  "mcpServers": {
    "zen": {
      "command": "sh",
      "args": [
        "-c", 
        "exec $(which uvx || echo uvx) --from git+https://github.com/BeehiveInnovations/zen-mcp-server.git zen-mcp-server"
      ],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:~/.local/bin",
        "GEMINI_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

**For Claude Code CLI:**
Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "zen": {
      "command": "sh", 
      "args": [
        "-c",
        "exec $(which uvx || echo uvx) --from git+https://github.com/BeehiveInnovations/zen-mcp-server.git zen-mcp-server"
      ],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:~/.local/bin",
        "GEMINI_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

**For Gemini CLI:**
Edit `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "zen": {
      "command": "sh",
      "args": [
        "-c",
        "exec $(which uvx || echo uvx) --from git+https://github.com/BeehiveInnovations/zen-mcp-server.git zen-mcp-server"  
      ],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:~/.local/bin",
        "GEMINI_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

**Benefits of uvx method:**
- ✅ Zero manual setup required
- ✅ Always pulls latest version
- ✅ No local dependencies to manage
- ✅ Works without Python environment setup

### Method B: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BeehiveInnovations/zen-mcp-server.git
cd zen-mcp-server

# One-command setup (handles everything)
./run-server.sh

# Or for Windows PowerShell:
./run-server.ps1

# View configuration for Claude Desktop
./run-server.sh -c

# See all options
./run-server.sh --help
```

**What the setup script does:**
- ✅ Creates Python virtual environment
- ✅ Installs all dependencies  
- ✅ Creates .env file for API keys
- ✅ Configures Claude integrations
- ✅ Provides copy-paste configuration

**After updates:** Always run `./run-server.sh` again after `git pull`.

**Windows users**: See the [WSL Setup Guide](wsl-setup.md) for detailed WSL configuration.

## Step 3: Configure API Keys

### For uvx installation:
Add your API keys directly to the MCP configuration shown above.

### For clone installation:
Edit the `.env` file:

```bash
nano .env
```

Add your API keys (at least one required):
```env
# Choose your providers (at least one required)
GEMINI_API_KEY=your-gemini-api-key-here      # For Gemini models  
OPENAI_API_KEY=your-openai-api-key-here      # For O3, GPT-5
XAI_API_KEY=your-xai-api-key-here            # For Grok models
OPENROUTER_API_KEY=your-openrouter-key       # For multiple models

# DIAL Platform (optional)
DIAL_API_KEY=your-dial-api-key-here
DIAL_API_HOST=https://core.dialx.ai          # Default host (optional)
DIAL_API_VERSION=2024-12-01-preview          # API version (optional) 
DIAL_ALLOWED_MODELS=o3,gemini-2.5-pro       # Restrict models (optional)

# Custom/Local models (Ollama, vLLM, etc.)
CUSTOM_API_URL=http://localhost:11434/v1     # Ollama example
CUSTOM_API_KEY=                              # Empty for Ollama
CUSTOM_MODEL_NAME=llama3.2                   # Default model name
```

**Important notes:**
- ⭐ **No restart needed** - Changes take effect immediately 
- ⭐ If multiple APIs configured, native APIs take priority over OpenRouter
- ⭐ Configure model aliases in [`conf/custom_models.json`](../conf/custom_models.json)

## Step 4: Test the Installation

### For Claude Desktop:
1. Restart Claude Desktop
2. Open a new conversation
3. Try: `"Use zen to list available models"`

### For Claude Code CLI:
1. Exit any existing Claude session
2. Run `claude` from your project directory  
3. Try: `"Use zen to chat about Python best practices"`

### For Gemini CLI:
**Note**: While Zen MCP connects to Gemini CLI, tool invocation isn't working correctly yet. See [Gemini CLI Setup](gemini-setup.md) for updates.

### Test Commands:
```
"Use zen to list available models"
"Chat with zen about the best approach for API design"
"Use zen thinkdeep with gemini pro about scaling strategies"  
"Debug this error with o3: [paste error]"
```

## Step 5: Start Using Zen

### Basic Usage Patterns:

**Let Claude pick the model:**
```
"Use zen to analyze this code for security issues"
"Debug this race condition with zen"
"Plan the database migration with zen"
```

**Specify the model:**
```  
"Use zen with gemini pro to review this complex algorithm"
"Debug with o3 using zen for logical analysis"
"Get flash to quickly format this code via zen"
```

**Multi-model workflows:**
```
"Use zen to get consensus from pro and o3 on this architecture"
"Code review with gemini, then precommit validation with o3"  
"Analyze with flash, then deep dive with pro if issues found"
```

### Quick Tool Reference:

**🤝 Collaboration**: `chat`, `thinkdeep`, `planner`, `consensus`
**🔍 Code Analysis**: `analyze`, `codereview`, `debug`, `precommit`  
**⚒️ Development**: `refactor`, `testgen`, `secaudit`, `docgen`
**🔧 Utilities**: `challenge`, `tracer`, `listmodels`, `version`

👉 **[Complete Tools Reference](tools/)** with detailed examples and parameters

## Common Issues and Solutions

### "zen not found" or "command not found"

**For uvx installations:**
- Ensure `uv` is installed and in PATH
- Try: `which uvx` to verify uvx is available
- Check PATH includes `/usr/local/bin` and `~/.local/bin`

**For clone installations:**
- Run `./run-server.sh` again to verify setup
- Check virtual environment: `which python` should show `.zen_venv/bin/python`

### API Key Issues

**"Invalid API key" errors:**
- Verify API keys in `.env` file or MCP configuration
- Test API keys directly with provider's API
- Check for extra spaces or quotes around keys

**"Model not available":**
- Run `"Use zen to list available models"` to see what's configured
- Check model restrictions in environment variables
- Verify API key has access to requested models

### Performance Issues

**Slow responses:**
- Use faster models: `flash` instead of `pro`  
- Lower thinking modes: `minimal` or `low` instead of `high`
- Restrict model access to prevent expensive model selection

**Token limit errors:**
- Use models with larger context windows
- Break large requests into smaller chunks
- See [Working with Large Prompts](advanced-usage.md#working-with-large-prompts)

### More Help

👉 **[Complete Troubleshooting Guide](troubleshooting.md)** with detailed solutions

👉 **[Advanced Usage Guide](advanced-usage.md)** for power-user features

👉 **[Configuration Reference](configuration.md)** for all options

## What's Next?

🎯 **Try the example workflows in the main README**

📚 **Explore the [Tools Reference](tools/)** to understand what each tool can do

⚡ **Read the [Advanced Usage Guide](advanced-usage.md)** for complex workflows

🔧 **Check out [Configuration Options](configuration.md)** to customize behavior

💡 **Join discussions and get help** in the project issues or discussions

## Quick Configuration Templates

### Development Setup (Balanced)
```env
DEFAULT_MODEL=auto
GEMINI_API_KEY=your-key
OPENAI_API_KEY=your-key
GOOGLE_ALLOWED_MODELS=flash,pro
OPENAI_ALLOWED_MODELS=o4-mini,o3-mini
```

### Cost-Optimized Setup
```env  
DEFAULT_MODEL=flash
GEMINI_API_KEY=your-key
GOOGLE_ALLOWED_MODELS=flash
```

### High-Performance Setup  
```env
DEFAULT_MODEL=auto
GEMINI_API_KEY=your-key
OPENAI_API_KEY=your-key
GOOGLE_ALLOWED_MODELS=pro
OPENAI_ALLOWED_MODELS=o3
```

### Local-First Setup
```env
DEFAULT_MODEL=auto
CUSTOM_API_URL=http://localhost:11434/v1
CUSTOM_MODEL_NAME=llama3.2
# Add cloud APIs as backup
GEMINI_API_KEY=your-key
```

Happy coding with your AI development team! 🤖✨