---
name: pal-testgen
description: Generates test cases including unit tests, integration tests, and test scenarios for code coverage.
allowed-tools: Bash, Read
---

# PAL TestGen

## Overview

Generate comprehensive test cases including unit tests, integration tests, and edge case scenarios. Uses multi-step workflow for thorough test planning.

## When to Use

- Creating tests for new code
- Improving test coverage
- Generating edge case tests
- Writing integration tests

## Workflow

Multi-step test generation:
1. Analyze code functionality
2. Identify test scenarios
3. Plan edge cases and boundaries
4. Generate test code
5. Review coverage

## Parameters

### Required (Workflow Fields)
- `step` (string): Test plan and current findings
- `step_number` (integer): Current step number (starts at 1)
- `total_steps` (integer): Estimated total steps
- `next_step_required` (boolean): Whether more planning needed
- `findings` (string): Functionality, critical paths, edge cases

### Optional
- `files_checked` (string[]): Files examined (absolute paths)
- `relevant_files` (string[]): Code that needs tests (absolute paths)
- `issues_found` (object[]): Testing concerns with severity
- `hypothesis` (string): Current theory about coverage gaps
- `confidence` (string): exploring, low, medium, high, very_high
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue previous planning
- `thinking_mode` (string): Reasoning depth
- `temperature` (number): 0 = deterministic, 1 = creative
- `use_assistant_model` (boolean): Use expert model for analysis
- `images` (string[]): Diagrams clarifying test scenarios

## Output

JSON with generated test code, test scenarios, and coverage recommendations.

## Invocation

```bash
# Start test generation (step 1)
pal-testgen --step "Analyze code functionality" --step_number 1 --total_steps 4 --next_step_required true --findings ""

# Continue (step 2+)
pal-testgen --step "Identify edge cases" --step_number 2 --total_steps 4 --next_step_required true --findings "Found 5 public methods" --continuation_id "abc-123"

# With file context
pal-testgen --step "Generate unit tests" --step_number 1 --total_steps 3 --next_step_required true --findings "" --relevant_files '["./src/calculator.py"]'
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
