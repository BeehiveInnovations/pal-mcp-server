# ListModels Tool - List Available Models

**Display all available AI models organized by provider**

The `listmodels` tool shows which providers are configured, available models, their aliases, context windows, and capabilities. This is useful for understanding what models can be used and their characteristics.

## Usage

```
"Use zen to list available models"
```

## Key Features

- **Provider organization**: Shows all configured providers and their status
- **Model capabilities**: Context windows, thinking mode support, and special features
- **Alias mapping**: Shows shorthand names and their full model mappings
- **Configuration status**: Indicates which providers are available based on API keys
- **Context window information**: Helps you choose models based on your content size needs
- **Capability overview**: Understanding which models support extended thinking, vision, etc.

## Output Information

The tool displays:

**Provider Status:**
- Which providers are configured and available
- API key status (without revealing the actual keys)
- Provider priority order

**Model Details:**
- Full model names and their aliases
- Context window sizes (tokens)
- Special capabilities (thinking modes, vision support, etc.)
- Provider-specific features

**Capability Summary:**
- Which models support extended thinking
- Vision-capable models for image analysis
- Models with largest context windows
- Fastest models for quick tasks

## Example Output

```
📋 Available Models by Provider

🔹 Google (Gemini) - ✅ Configured
  • pro (gemini-2.5-pro-preview-06-05) - 1M context, thinking modes
  • flash (gemini-2.0-flash-experimental) - 1M context, ultra-fast

🔹 OpenAI - ✅ Configured  
  • o3 (o3) - 200K context, strong reasoning
  • o3-mini (o3-mini) - 200K context, balanced
  • o4-mini (o4-mini) - 200K context, latest reasoning

🔹 Custom/Local - ✅ Configured
  • local-llama (llama3.2) - 128K context, local inference
  • Available at: http://host.docker.internal:11434/v1

🔹 OpenRouter - ❌ Not configured
  Set OPENROUTER_API_KEY to enable access to Claude, GPT-4, and more models
```

## When to Use ListModels

- **Model selection**: When you're unsure which models are available
- **Capability checking**: To verify what features each model supports
- **Configuration validation**: To confirm your API keys are working
- **Context planning**: To choose models based on content size requirements
- **Performance optimization**: To select the right model for speed vs quality trade-offs

## Configuration Dependencies

The available models depend on your configuration:

**API Keys Required:**
- `GEMINI_API_KEY` - Enables Gemini Pro and Flash models
- `OPENAI_API_KEY` - Enables OpenAI O3, O4-mini, and GPT models
- `OPENROUTER_API_KEY` - Enables access to multiple providers through OpenRouter
- `CUSTOM_API_URL` - Enables local/custom models (Ollama, vLLM, etc.)

**Model Restrictions:**
If you've set model usage restrictions via environment variables, the tool will show:
- Which models are allowed vs restricted
- Active restriction policies
- How to modify restrictions

## Tool Parameters

This tool requires no parameters - it simply queries the server configuration and displays all available information.

## Best Practices

- **Check before planning**: Use this tool to understand your options before starting complex tasks
- **Verify configuration**: Confirm your API keys are working as expected
- **Choose appropriate models**: Match model capabilities to your specific needs
- **Understand limits**: Be aware of context windows when working with large files

## When to Use ListModels vs Other Tools

- **Use `listmodels`** for: Understanding available options and model capabilities
- **Use `chat`** for: General discussions about which model to use for specific tasks
- **Use `version`** for: Server configuration and version information
- **Use other tools** for: Actual analysis, debugging, or development work