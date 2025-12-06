---
name: pal-challenge
description: Provides critical thinking and assumption challenging, questioning decisions, surfacing blind spots, and offering counter-arguments for better solutions.
allowed-tools: Bash, Read
---

# PAL Challenge

## Overview

Devil's advocate analysis that questions assumptions and provides counter-arguments. Helps identify blind spots and strengthen decisions.

## When to Use

- Validating important decisions
- Stress-testing proposed solutions
- Identifying hidden assumptions
- Getting constructive criticism

## Parameters

### Required
- `prompt` (string): The decision or approach to challenge

### Optional
None - this is a simple single-prompt tool.

## Output

JSON with challenges, counter-arguments, identified risks, and alternative perspectives.

## Model Selection

- Models are detected at runtime based on your configuration
- Use `pal-listmodels` to see available models before specifying one
- Default: auto-select best available model for the task
