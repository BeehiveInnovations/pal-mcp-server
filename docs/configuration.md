# Configuration Guide

This guide covers all configuration options for the PAL MCP Server. The server is configured through environment variables defined in your `.env` file.

## Quick Start Configuration

**Auto Mode (Recommended):** Set `DEFAULT_MODEL=auto` and let Claude intelligently select the best model for each task:

```env
# Basic configuration
DEFAULT_MODEL=auto
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
```

## Complete Configuration Reference

### Required Configuration

**Workspace Root:**
```env

### API Keys (At least one required)

**Important:** Use EITHER OpenRouter OR native APIs, not both! Having both creates ambiguity about which provider serves each model.

**Option 1: Native APIs (Recommended for direct access)**
```env
# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key_here
# Get from: https://makersuite.google.com/app/apikey

# OpenAI API  
OPENAI_API_KEY=your_openai_api_key_here
# Get from: https://platform.openai.com/api-keys

# X.AI GROK API
XAI_API_KEY=your_xai_api_key_here
# Get from: https://console.x.ai/
```

**Option 2: OpenRouter (Access multiple models through one API)**
```env
# OpenRouter for unified model access
OPENROUTER_API_KEY=your_openrouter_api_key_here
# Get from: https://openrouter.ai/
# If using OpenRouter, comment out native API keys above
```

**Option 3: Custom API Endpoints (Local models)**
```env
# For Ollama, vLLM, LM Studio, etc.
CUSTOM_API_URL=http://localhost:11434/v1  # Ollama example
CUSTOM_API_KEY=                                      # Empty for Ollama
CUSTOM_MODEL_NAME=llama3.2                          # Default model
```

**Local Model Connection:**
- Use standard localhost URLs since the server runs natively
- Example: `http://localhost:11434/v1` for Ollama

### Model Configuration

**Default Model Selection:**
```env
# Options: 'auto', 'pro', 'flash', 'gpt5.2', 'gpt5.1-codex', 'gpt5.1-codex-mini', 'o3', 'o3-mini', 'o4-mini', etc.
DEFAULT_MODEL=auto  # Claude picks best model for each task (recommended)
```

- **Available Models:** The canonical capability data for native providers lives in JSON manifests under `conf/`:
  - `conf/openai_models.json` – OpenAI catalogue (can be overridden with `OPENAI_MODELS_CONFIG_PATH`)
  - `conf/gemini_models.json` – Gemini catalogue (`GEMINI_MODELS_CONFIG_PATH`)
  - `conf/xai_models.json` – X.AI / GROK catalogue (`XAI_MODELS_CONFIG_PATH`)
  - `conf/openrouter_models.json` – OpenRouter catalogue (`OPENROUTER_MODELS_CONFIG_PATH`)
  - `conf/dial_models.json` – DIAL aggregation catalogue (`DIAL_MODELS_CONFIG_PATH`)
  - `conf/custom_models.json` – Custom/OpenAI-compatible endpoints (`CUSTOM_MODELS_CONFIG_PATH`)

  Each JSON file documents the allowed fields via its `_README` block and controls model aliases, capability limits, and feature flags (including `allow_code_generation`). Edit these files (or point the matching `*_MODELS_CONFIG_PATH` variable to your own copy) when you want to adjust context windows, enable JSON mode, enable structured code generation, or expose additional aliases without touching Python code.

  The shipped defaults cover:

  | Provider | Canonical Models | Notable Aliases |
  |----------|-----------------|-----------------|
  | OpenAI | `gpt-5.2`, `gpt-5.1-codex`, `gpt-5.1-codex-mini`, `gpt-5`, `gpt-5.2-pro`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-codex`, `gpt-4.1`, `o3`, `o3-mini`, `o3-pro`, `o4-mini` | `gpt5.2`, `gpt-5.2`, `5.2`, `gpt5.1-codex`, `codex-5.1`, `codex-mini`, `gpt5`, `gpt5pro`, `mini`, `nano`, `codex`, `o3mini`, `o3pro`, `o4mini` |
  | Gemini | `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-2.0-flash-lite` | `pro`, `gemini-pro`, `flash`, `flash-2.0`, `flashlite` |
  | X.AI | `grok-4`, `grok-4.1-fast` | `grok`, `grok4`, `grok-4.1-fast-reasoning` |
  | OpenRouter | See `conf/openrouter_models.json` for the continually evolving catalogue | e.g., `opus`, `sonnet`, `flash`, `pro`, `mistral` |
  | Custom | User-managed entries such as `llama3.2` | Define your own aliases per entry |

  Latest OpenAI entries (`gpt-5.2`, `gpt-5.1-codex`, `gpt-5.1-codex-mini`, `gpt-5.2-pro`) expose 400K-token contexts with large outputs, reasoning-token support, and multimodal inputs. `gpt-5.1-codex` and `gpt-5.2-pro` are Responses-only with streaming disabled, while the base `gpt-5.2` and Codex mini support streaming along with full code-generation flags. Update your manifests if you run custom deployments so these capability bits stay accurate.

  > **Tip:** Copy the JSON file you need, customise it, and point the corresponding `*_MODELS_CONFIG_PATH` environment variable to your version. This lets you enable or disable capabilities (JSON mode, function calling, temperature support, code generation) without editing Python.

### Code Generation Capability

**`allow_code_generation` Flag:**

The `allow_code_generation` capability enables models to generate complete, production-ready implementations in a structured format. When enabled, the `chat` tool will inject special instructions for substantial code generation tasks.

```json
{
  "model_name": "gpt-5",
  "allow_code_generation": true,
  ...
}
```

**When to Enable:**

- **Enable for**: Models MORE capable than your primary CLI's model (e.g., GPT-5.1 Codex, GPT-5.2 Pro, GPT-5.2 when using Claude Code with Sonnet 4.5)
- **Purpose**: Get complete implementations from a more powerful reasoning model that your primary CLI can then review and apply
- **Use case**: Large-scale implementations, major refactoring, complete module creation

**Important Guidelines:**

1. Only enable for models significantly more capable than your primary CLI to ensure high-quality generated code
2. The capability triggers structured code output (`<GENERATED-CODE>` blocks) for substantial implementation requests
3. Minor code changes still use inline code blocks regardless of this setting
4. Generated code is saved to `pal_generated.code` in the user's working directory
5. Your CLI receives instructions to review and apply the generated code systematically

**Example Configuration:**

```json
// OpenAI models configuration (conf/openai_models.json)
{
  "models": [
    {
      "model_name": "gpt-5",
      "allow_code_generation": true,
      "intelligence_score": 18,
      ...
    },
    {
      "model_name": "gpt-5.2-pro",
      "allow_code_generation": true,
      "intelligence_score": 19,
      ...
    }
  ]
}
```

**Typical Workflow:**
1. You ask your AI agent to implement a complex new feature using `chat` with a higher-reasoning model such as **gpt-5.2-pro**
2. GPT-5.2-Pro generates structured implementation and shares the complete implementation with PAL
3. PAL saves the code to `pal_generated.code` and asks AI agent to implement the plan
4. AI agent continues from the previous context, reads the file, applies the implementation

### Thinking Mode Configuration

**Default Thinking Mode for ThinkDeep:**
```env
# Only applies to models supporting extended thinking (e.g., Gemini 3.0 Pro)
# Starting with Gemini 3.0 Pro, `thinking level` should stick to `high`

DEFAULT_THINKING_MODE_THINKDEEP=high

# Available modes and token consumption:
#   minimal: 128 tokens   - Quick analysis, fastest response
#   low:     2,048 tokens - Light reasoning tasks  
#   medium:  8,192 tokens - Balanced reasoning
#   high:    16,384 tokens - Complex analysis (recommended for thinkdeep)
#   max:     32,768 tokens - Maximum reasoning depth
```

### Model Usage Restrictions

Control which models can be used from each provider for cost control, compliance, or standardization:

```env
# Format: Comma-separated list (case-insensitive, whitespace tolerant)
# Empty or unset = all models allowed (default)

# OpenAI model restrictions
OPENAI_ALLOWED_MODELS=gpt-5.1-codex-mini,gpt-5-mini,o3-mini,o4-mini,mini

# Gemini model restrictions  
GOOGLE_ALLOWED_MODELS=flash,pro

# X.AI GROK model restrictions
XAI_ALLOWED_MODELS=grok-4,grok-4.1-fast-reasoning

# OpenRouter model restrictions (affects models via custom provider)
OPENROUTER_ALLOWED_MODELS=opus,sonnet,mistral
```

**Supported Model Names:** The names/aliases listed in the JSON manifests above are the authoritative source. Keep in mind:

- Aliases are case-insensitive and defined per entry (for example, `mini` maps to `gpt-5-mini` by default, while `flash` maps to `gemini-2.5-flash`).
- When you override the manifest files you can add or remove aliases as needed; restriction policies (`*_ALLOWED_MODELS`) automatically pick up those changes.
- Models omitted from a manifest fall back to generic capability detection (where supported) and may have limited feature metadata.

**Example Configurations:**
```env
# Cost control - only cheap models
OPENAI_ALLOWED_MODELS=o4-mini
GOOGLE_ALLOWED_MODELS=flash

# High-performance setup
OPENAI_ALLOWED_MODELS=gpt-5.1-codex,gpt-5.2
GOOGLE_ALLOWED_MODELS=pro

# Single model standardization
OPENAI_ALLOWED_MODELS=o4-mini
GOOGLE_ALLOWED_MODELS=pro

# Balanced selection
GOOGLE_ALLOWED_MODELS=flash,pro
OPENAI_ALLOWED_MODELS=gpt-5.1-codex-mini,gpt-5-mini,o4-mini
XAI_ALLOWED_MODELS=grok,grok-4.1-fast-reasoning
```

### Advanced Configuration

**Custom Model Configuration & Manifest Overrides:**
```env
# Override default location of built-in catalogues
OPENAI_MODELS_CONFIG_PATH=/path/to/openai_models.json
GEMINI_MODELS_CONFIG_PATH=/path/to/gemini_models.json
XAI_MODELS_CONFIG_PATH=/path/to/xai_models.json
OPENROUTER_MODELS_CONFIG_PATH=/path/to/openrouter_models.json
DIAL_MODELS_CONFIG_PATH=/path/to/dial_models.json
CUSTOM_MODELS_CONFIG_PATH=/path/to/custom_models.json
```

**Conversation Settings:**
```env
# How long AI-to-AI conversation threads persist in memory (hours)
# Conversations are auto-purged when claude closes its MCP connection or 
# when a session is quit / re-launched 
CONVERSATION_TIMEOUT_HOURS=5

# Maximum conversation turns (each exchange = 2 turns)
MAX_CONVERSATION_TURNS=20
```

**Logging Configuration:**
```env
# Logging level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=DEBUG  # Default: shows detailed operational messages
```

## Configuration Examples

### Development Setup
```env
# Development with multiple providers
DEFAULT_MODEL=auto
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
GOOGLE_ALLOWED_MODELS=flash,pro
OPENAI_ALLOWED_MODELS=gpt-5.1-codex-mini,gpt-5-mini,o4-mini
XAI_API_KEY=your-xai-key
LOG_LEVEL=DEBUG
CONVERSATION_TIMEOUT_HOURS=1
```

### Production Setup
```env
# Production with cost controls
DEFAULT_MODEL=auto
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
GOOGLE_ALLOWED_MODELS=flash
OPENAI_ALLOWED_MODELS=gpt-5.1-codex-mini,o4-mini
LOG_LEVEL=INFO
CONVERSATION_TIMEOUT_HOURS=3
```

### Local Development
```env
# Local models only
DEFAULT_MODEL=llama3.2
CUSTOM_API_URL=http://localhost:11434/v1
CUSTOM_API_KEY=
CUSTOM_MODEL_NAME=llama3.2
LOG_LEVEL=DEBUG
```

### OpenRouter Only
```env
# Single API for multiple models
DEFAULT_MODEL=auto
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_ALLOWED_MODELS=opus,sonnet,gpt-4
LOG_LEVEL=INFO
```

## Important Notes

**Local Networking:**
- Use standard localhost URLs for local models
- The server runs as a native Python process

**API Key Priority:**
- Native APIs take priority over OpenRouter when both are configured
- Avoid configuring both native and OpenRouter for the same models

**Model Restrictions:**
- Apply to all usage including auto mode
- Empty/unset = all models allowed
- Invalid model names are warned about at startup

**Configuration Changes:**
- Restart the server with `./run-server.sh` after changing `.env`
- Configuration is loaded once at startup

## Related Documentation

- **[Advanced Usage Guide](advanced-usage.md)** - Advanced model usage patterns, thinking modes, and power user workflows
- **[Context Revival Guide](context-revival.md)** - Conversation persistence and context revival across sessions
- **[AI-to-AI Collaboration Guide](ai-collaboration.md)** - Multi-model coordination and conversation threading
