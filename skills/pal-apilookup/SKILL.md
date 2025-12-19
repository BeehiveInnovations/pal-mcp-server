---
name: pal-apilookup
description: Searches API and SDK documentation for current references, usage examples, and best practices.
allowed-tools: Bash, Read
---

# PAL API Lookup

## Overview

Search and retrieve API documentation, SDK usage examples, and best practices. Gets up-to-date information from official sources.

## When to Use

- Looking up API usage patterns
- Finding SDK documentation
- Checking library best practices
- Understanding API changes

## Parameters

### Required
- `prompt` (string): What API/SDK information you need

### Optional
None - this is a simple single-prompt tool.

## Output

JSON with documentation excerpts, usage examples, and relevant links.

## Invocation

```bash
# Basic usage
pal-apilookup --prompt "How to use React useEffect hook?"

# SDK documentation
pal-apilookup --prompt "Python requests library POST with JSON body"
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
