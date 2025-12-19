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

## Invocation

```bash
# Challenge a decision
pal-challenge --prompt "We decided to use microservices. What could go wrong?"

# Stress-test an approach
pal-challenge --prompt "Is using MongoDB for this use case a good idea?"
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
