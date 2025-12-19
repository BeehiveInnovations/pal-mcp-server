---
name: pal-refactor
description: Identifies refactoring opportunities and code smells, suggesting improvements for cleaner, more maintainable code.
allowed-tools: Bash, Read
---

# PAL Refactor

## Overview

Identify code smells and refactoring opportunities. Uses multi-step workflow to analyze code and provide actionable improvement suggestions.

## When to Use

- Improving code quality
- Reducing technical debt
- Identifying code smells
- Planning refactoring efforts

## Workflow

Multi-step refactoring analysis:
1. Define refactoring strategy
2. Identify code smells
3. Analyze impact and dependencies
4. Generate refactoring suggestions
5. Prioritize recommendations

## Parameters

### Required (Workflow Fields)
- `step` (string): Refactoring plan and current findings
- `step_number` (integer): Current step number (starts at 1)
- `total_steps` (integer): Estimated total steps
- `next_step_required` (boolean): Whether more analysis needed
- `findings` (string): Code smells and opportunities found

### Optional
- `files_checked` (string[]): Files examined (absolute paths)
- `relevant_files` (string[]): Files needing refactoring (absolute paths)
- `refactor_type` (string): codesmells, decompose, extract, rename, simplify
- `focus_areas` (string[]): performance, readability, maintainability, etc.
- `style_guide_examples` (string[]): Files to use as style reference
- `issues_found` (object[]): Opportunities with severity and suggestions
- `hypothesis` (string): Current theory
- `confidence` (string): exploring, low, medium, high, very_high
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue previous analysis
- `thinking_mode` (string): Reasoning depth
- `temperature` (number): 0 = deterministic, 1 = creative
- `use_assistant_model` (boolean): Use expert model for analysis
- `images` (string[]): Architecture diagrams or visuals

## Output

JSON with identified code smells, refactoring suggestions, and priority recommendations.

## Invocation

```bash
# Start refactoring analysis (step 1)
pal-refactor --step "Identify code smells" --step_number 1 --total_steps 4 --next_step_required true --findings ""

# Continue analysis (step 2+)
pal-refactor --step "Analyze impact" --step_number 2 --total_steps 4 --next_step_required true --findings "Found duplicate code" --continuation_id "abc-123"

# With specific refactor type
pal-refactor --step "Find extraction opportunities" --step_number 1 --total_steps 3 --next_step_required true --findings "" --refactor_type extract --relevant_files '["./src/utils.py"]'
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
