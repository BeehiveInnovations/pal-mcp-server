---
name: pal-listmodels
description: Lists all available AI models configured for PAL tools, showing providers, model names, aliases, and capabilities.
allowed-tools: Bash, Read
---

# PAL List Models

## Overview

Query available AI models for PAL tools. Shows which providers are configured (Google Gemini, OpenAI, OpenRouter, etc.) and what models can be used.

## When to Use

- Before using other PAL tools, to see what models are available
- To check if a specific model or provider is configured
- To understand model capabilities (context window, thinking support)
- To troubleshoot model selection issues

## Parameters

This skill takes no parameters - it automatically detects configured providers.

## Output

JSON response with:
- List of configured providers and their status
- Available models organized by provider
- Model aliases and their canonical names
- Context window sizes and capabilities
- Total count of available models

## Example Output

```json
{
  "status": "success",
  "content": "# Available AI Models\n\n## Google Gemini ✅\n...",
  "metadata": {
    "configured_providers": 3
  }
}
```

## Invocation

```bash
# List all available models (no parameters needed)
pal-listmodels
```

## Notes

- Models are detected at runtime based on your `.env` configuration
- Use `pal-listmodels` before other skills to verify model availability
- Model restrictions (if configured) are reflected in the output
