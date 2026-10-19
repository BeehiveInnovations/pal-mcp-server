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

# Anthropic (Claude) direct API - native provider (dormant unless set)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
# Or Claude on Azure AI Foundry with your Entra ID login (no key) - see docs/entra_auth.md
# ANTHROPIC_USE_ENTRA=true
# ANTHROPIC_FOUNDRY_BASE_URL=https://your-resource.services.ai.azure.com/anthropic

# ChatGPT-plan models through the Codex CLI login (no key; chatgpt/<model>) - see docs/chatgpt_provider.md
# CHATGPT_ENABLED=true
# CHATGPT_ALLOWED_MODELS=chatgpt/gpt-6.1-sol,chatgpt/gpt-6-luna
# CHATGPT_TIMEOUT_SECONDS=600                # per call
# CHATGPT_CODEX_COMMAND=/opt/homebrew/bin/codex  # full path when the MCP client's PATH lacks codex

# Azure OpenAI with your Entra ID login instead of AZURE_OPENAI_API_KEY - see docs/entra_auth.md
# AZURE_OPENAI_USE_ENTRA=true
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Native direct-API providers for open-model creators (all OpenAI-compatible; each dormant unless
# set, and ranks ahead of OpenRouter when its key is present).
DEEPSEEK_API_KEY=your_deepseek_api_key_here        # DeepSeek - api.deepseek.com
DASHSCOPE_API_KEY=your_dashscope_api_key_here      # Alibaba Qwen - dashscope-intl.aliyuncs.com
ZAI_API_KEY=your_zai_api_key_here                  # Zhipu GLM - api.z.ai
MOONSHOT_API_KEY=your_moonshot_api_key_here        # Moonshot Kimi - api.moonshot.ai
MINIMAX_API_KEY=your_minimax_api_key_here          # MiniMax - api.minimax.io
MISTRAL_API_KEY=your_mistral_api_key_here          # Mistral - api.mistral.ai
NVIDIA_API_KEY=your_nvidia_api_key_here            # NVIDIA Nemotron - integrate.api.nvidia.com
PERPLEXITY_API_KEY=your_perplexity_api_key_here    # Perplexity Sonar - api.perplexity.ai
# Each also honors <PROVIDER>_ALLOWED_MODELS / _DISALLOWED_MODELS / _MODELS_CONFIG_PATH.
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

**Dynamic Model Selection (opt-in):**
```env
# Default (unset): upstream auto-selection algorithm + upstream alias targets.
# Enabled: OpenAI auto-mode prefers the newest flagships; bare aliases (flash/pro/flash-lite) remap to newest.
DYNAMIC_MODEL_SELECTION=1
```

With `DYNAMIC_MODEL_SELECTION` unset, auto-mode uses upstream's selection *algorithm* and bare aliases keep their upstream targets (`flash`→`gemini-2.5-flash`, `pro`→`gemini-3-pro-preview`). For OpenAI this means the established per-category preference lists, unchanged. For Gemini, upstream selection is reverse-alphabetical over the available models, so the newest-numbered model in the catalogue is naturally selected — adding newer Gemini models (`gemini-3.8-flash`, `gemini-3.1-pro-preview`) advances the default Gemini auto-pick accordingly, exactly as upstream's own algorithm would when models are added. Enabling the flag additionally makes OpenAI auto-selection lead with the newest flagship and remaps the bare aliases to the newest models (`flash`→`gemini-3.8-flash`, `pro`→`gemini-3.1-pro-preview`, and on OpenRouter `sonnet`, `haiku` and `grok`→the newest Claude Sonnet, Claude Haiku and Grok). With the flag on, Gemini's extended-reasoning pick is ranked by score across all thinking models, so `gemini-4-argon` wins even though its name does not contain "pro". The bare-alias remap applies wherever a conf entry lists the alias under `dynamic_aliases`: today that is Gemini direct (`flash`, `pro`), X.AI (`grok`), and on OpenRouter `sonnet`, `haiku` and `grok`. Other OpenRouter bare aliases keep their existing targets, so reach those models by their explicit `or-*` names. **Caveat:** with the flag on (and, for Gemini, by default once newer models are in the catalogue), auto-mode may pick a newer model your API key cannot access yet — selection falls back only on restriction policy, not on an API model-not-found at call time. Pair it with `*_ALLOWED_MODELS` / `*_DISALLOWED_MODELS` to constrain the pool.

> The `intelligence_score`s that drive this ordering for the open-weight OpenRouter models are calibrated from current benchmarks and peer-reviewed — see [open_model_scoring.md](open_model_scoring.md) for the methodology and per-model reasoning.

- **Available Models:** The canonical capability data for native providers lives in JSON manifests under `conf/`:
  - `conf/openai_models.json` – OpenAI catalogue (can be overridden with `OPENAI_MODELS_CONFIG_PATH`)
  - `conf/gemini_models.json` – Gemini catalogue (`GEMINI_MODELS_CONFIG_PATH`)
  - `conf/xai_models.json` – X.AI / GROK catalogue (`XAI_MODELS_CONFIG_PATH`)
  - `conf/anthropic_models.json` – Anthropic (Claude) catalogue (`ANTHROPIC_MODELS_CONFIG_PATH`)
  - `conf/deepseek_models.json`, `conf/qwen_models.json`, `conf/zai_models.json`, `conf/moonshot_models.json`,
    `conf/minimax_models.json`, `conf/mistral_models.json`, `conf/nvidia_models.json`,
    `conf/perplexity_models.json` – native open-model creator APIs (`DEEPSEEK_MODELS_CONFIG_PATH`,
    `QWEN_MODELS_CONFIG_PATH`, `ZAI_MODELS_CONFIG_PATH`, `MOONSHOT_MODELS_CONFIG_PATH`,
    `MINIMAX_MODELS_CONFIG_PATH`, `MISTRAL_MODELS_CONFIG_PATH`, `NVIDIA_MODELS_CONFIG_PATH`,
    `PERPLEXITY_MODELS_CONFIG_PATH`)
  - `conf/openrouter_models.json` – OpenRouter catalogue (`OPENROUTER_MODELS_CONFIG_PATH`)
  - `conf/dial_models.json` – DIAL aggregation catalogue (`DIAL_MODELS_CONFIG_PATH`)
  - `conf/custom_models.json` – Custom/OpenAI-compatible endpoints (`CUSTOM_MODELS_CONFIG_PATH`)

  Each JSON file documents the allowed fields via its `_README` block and controls model aliases, capability limits, and feature flags (including `allow_code_generation`). Edit these files (or point the matching `*_MODELS_CONFIG_PATH` variable to your own copy) when you want to adjust context windows, enable JSON mode, enable structured code generation, or expose additional aliases without touching Python code.

  The shipped defaults cover these current flagships (October 2026). The [model catalog](model_catalog.md)
  lists every measured model with its score, per-effort AA Index values, routes, and aliases.

  | Provider | Current flagships | Notable aliases |
  |----------|-------------------|-----------------|
  | Anthropic | `claude-opus-5-5`, `claude-fable-5-1`, `claude-sonnet-5-5`, `claude-haiku-5-5` | `opus`, `fable`, `sonnet`, `haiku` |
  | OpenAI | `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6-luna`, plus the GPT-5.x family | `astra`, `sol`, `luna` |
  | Gemini | `gemini-4-argon`, `gemini-3.8-flash`, `gemini-3.1-pro-preview` | `argon`, `flash3.8`, `gemini-flash-latest` |
  | X.AI | `grok-4.7`, `grok-4` | `grok-4.7`, `grok` |
  | Native open-model APIs | DeepSeek, Qwen, GLM, Kimi, MiniMax, Mistral, NVIDIA, Perplexity | per conf file |
  | OpenRouter | Mirrors of the above, plus Meta Muse, Xiaomi MiMo, StepFun, Cohere and more | `or-*` names; see `conf/openrouter_models.json` |
  | Custom | User-managed entries such as `llama3.2` | Define your own aliases per entry |

  Optional conf fields that this fork adds (`aa_index`, `aa_index_by_effort`, `effort_levels`,
  `auto_selectable`, `dynamic_aliases`) are described in [model_ranking.md](model_ranking.md#fields-that-support-the-score).

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

**Block-lists (`*_DISALLOWED_MODELS`):** the complement of the allow-lists — reject specific models while leaving the provider otherwise open. A block-list match always wins, so a model is usable iff it is **not** blocked **and** (no allow-list is set **or** it is on the allow-list). Use this to exclude a few models (e.g. costly `*-pro` tiers) without enumerating every model you want to keep. Available for `OPENAI_`, `GOOGLE_`, `XAI_`, `OPENROUTER_`, and `DIAL_`.

```env
# Block specific models; everything else stays available
OPENAI_DISALLOWED_MODELS=gpt-5.5-pro
OPENROUTER_DISALLOWED_MODELS=openai/gpt-5.5-pro,openai/gpt-5.4-pro
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
AZURE_MODELS_CONFIG_PATH=/path/to/azure_models.json
ANTHROPIC_MODELS_CONFIG_PATH=/path/to/anthropic_models.json
CHATGPT_MODELS_CONFIG_PATH=/path/to/chatgpt_models.json
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

- **[Entra ID Authentication](entra_auth.md)** - Azure OpenAI and Claude on Azure AI Foundry with `az login` instead of API keys
- **[ChatGPT Models via Codex CLI](chatgpt_provider.md)** - ChatGPT-plan models through `codex login`, with every `CHATGPT_*` setting

- **[Advanced Usage Guide](advanced-usage.md)** - Advanced model usage patterns, thinking modes, and power user workflows
- **[Context Revival Guide](context-revival.md)** - Conversation persistence and context revival across sessions
- **[AI-to-AI Collaboration Guide](ai-collaboration.md)** - Multi-model coordination and conversation threading
