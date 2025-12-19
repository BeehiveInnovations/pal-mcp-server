---
name: pal-codereview
description: Performs systematic code review with multi-step workflow, analyzing code quality, security, performance, and best practices.
allowed-tools: Bash, Read
---

# PAL Code Review

## Overview

Multi-step systematic code review covering quality, security, performance, and maintainability. Provides actionable findings with severity levels.

## When to Use

- Before merging pull requests
- Reviewing new code additions
- Security and vulnerability assessment
- Performance optimization analysis

## Workflow

Multi-step review process:
1. Initial code structure analysis
2. Security vulnerability scan
3. Performance assessment
4. Best practices review
5. Final summary with recommendations

## Parameters

### Required (Workflow Fields)
- `step` (string): Review narrative describing current step
- `step_number` (integer): Current review step (starts at 1)
- `total_steps` (integer): Number of review steps planned
- `next_step_required` (boolean): True when another review step follows
- `findings` (string): Findings across quality, security, performance

### Optional
- `relevant_files` (string[]): Files under review (absolute paths, required in step 1)
- `files_checked` (string[]): Files reviewed, including ruled-out ones (absolute paths)
- `issues_found` (object[]): Issues with severity (critical/high/medium/low)
- `review_type` (string): full, security, performance, or quick
- `focus_on` (string): Areas to emphasize (e.g., 'threading', 'auth')
- `standards` (string[]): Coding standards or style guides to enforce
- `severity_filter` (string): Minimum severity to report
- `hypothesis` (string): Current theory about issues
- `confidence` (string): exploring, low, medium, high, very_high
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue previous review
- `thinking_mode` (string): Reasoning depth
- `temperature` (number): 0 = deterministic, 1 = creative
- `use_assistant_model` (boolean): Use expert model for validation

## Output

JSON with review findings, severity levels, and guidance for next steps.

## Invocation

```bash
# Start code review (step 1)
pal-codereview --step "Initial code structure analysis" --step_number 1 --total_steps 5 --next_step_required true --findings "" --relevant_files '["./src/api.py"]'

# Continue review (step 2+)
pal-codereview --step "Security scan" --step_number 2 --total_steps 5 --next_step_required true --findings "Found input validation" --continuation_id "abc-123"

# With specific focus
pal-codereview --step "Performance review" --step_number 1 --total_steps 3 --next_step_required true --findings "" --review_type performance --focus_on "database queries"
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
