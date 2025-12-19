---
name: pal-chat
description: Provides multi-model collaborative chat for brainstorming, development discussions, getting second opinions, and exploring ideas with AI assistance.
allowed-tools: Bash, Read
---

# PAL Chat

## Overview

Collaborative thinking and development discussions with PAL's multi-model AI support. Maintains conversation context across multiple exchanges.

## When to Use

- Brainstorming ideas or approaches
- Getting a second opinion on technical decisions
- Discussing code architecture or design patterns
- Exploring solutions to complex problems

## Parameters

### Required
- `prompt` (string): Your question or topic for discussion

### Optional
- `absolute_file_paths` (string[]): Full absolute paths to code files for context
- `images` (string[]): Image paths (absolute) or base64 strings for visual context
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue a previous conversation
- `thinking_mode` (string): Reasoning depth - minimal, low, medium, high, or max
- `temperature` (number): 0 = deterministic, 1 = creative
- `working_directory_absolute_path` (string): Working directory (auto-filled if omitted)

## Output

JSON response with AI analysis and optional `continuation_id` for follow-up conversations.

## Invocation

```bash
# Basic usage
pal-chat --prompt "How should I structure this API?"

# With file context
pal-chat --prompt "Review this code" --absolute_file_paths '["./src/main.py"]'

# Continue conversation
pal-chat --prompt "Tell me more" --continuation_id "abc-123"
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
