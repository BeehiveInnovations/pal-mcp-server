---
name: pal-clink
description: Bridges to external AI CLIs like Gemini CLI, enabling cross-model collaboration and specialized external capabilities.
allowed-tools: Bash, Read
---

# PAL CLink

## Overview

Connect to external AI command-line tools for cross-model collaboration. Enables leveraging specialized capabilities from other AI systems.

## When to Use

- Cross-model verification
- Accessing specialized AI capabilities
- Getting diverse AI perspectives
- Leveraging external AI tools

## Parameters

### Required
- `cli_name` (string): CLI client name from conf/cli_clients (e.g., gemini, aider)
- `prompt` (string): Query for the external AI

### Optional
- `absolute_file_paths` (string[]): Full paths to relevant code files
- `images` (string[]): Image paths or base64 for visual context
- `continuation_id` (string): Continue a previous conversation
- `role` (string): Role preset defined for the selected CLI

## Output

JSON with external AI response and integration notes.

## Invocation

```bash
# Call Gemini CLI
pal-clink --cli_name gemini --prompt "Analyze this architecture"

# Call Codex CLI
pal-clink --cli_name codex --prompt "Review this code"

# With file context
pal-clink --cli_name gemini --prompt "Explain this" --absolute_file_paths '["./src/main.py"]'

# Continue conversation
pal-clink --cli_name gemini --prompt "More details" --continuation_id "abc-123"
```

## Model Selection

CLink uses external CLI tools (Gemini CLI, aider, etc.) rather than internal PAL models.
Use `pal-listmodels` to see available internal models for other PAL skills.
