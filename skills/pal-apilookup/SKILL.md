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

## Model Selection

- Models are detected at runtime based on your configuration
- Use `pal-listmodels` to see available models before specifying one
- Default: auto-select best available model for the task
