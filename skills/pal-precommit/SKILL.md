---
name: pal-precommit
description: Validates git changes before commit, reviewing staged modifications to catch issues early.
allowed-tools: Bash, Read
---

# PAL Precommit

## Overview

Review staged git changes before committing. Multi-step workflow to validate code quality and ensure changes are ready for commit.

## When to Use

- Before committing changes
- Validating staged modifications
- Quick sanity check on changes
- Ensuring commit readiness

## Workflow

Multi-step validation process:
1. Outline validation strategy
2. Review changes for issues
3. Expert validation (optional)
4. Final assessment

## Parameters

### Required (Workflow Fields)
- `step` (string): Current validation step description
- `step_number` (integer): Current pre-commit step number (starts at 1)
- `total_steps` (integer): Planned number of validation steps
- `next_step_required` (boolean): True to continue, False when done
- `findings` (string): Git diff insights, risks, missing tests, etc.

### Optional
- `path` (string): Absolute path to repository root (required in step 1)
- `compare_to` (string): Git ref to diff against (default: HEAD)
- `include_staged` (boolean): Inspect staged changes
- `include_unstaged` (boolean): Inspect unstaged changes
- `files_checked` (string[]): Files examined (absolute paths)
- `relevant_files` (string[]): Files involved in the change (absolute paths)
- `issues_found` (object[]): Issues with severity (critical/high/medium/low)
- `focus_on` (string): Areas to emphasize (security, performance, tests)
- `severity_filter` (string): Minimum severity to report
- `precommit_type` (string): 'external' (expert model) or 'internal'
- `hypothesis` (string): Current theory about issues
- `confidence` (string): exploring, low, medium, high, very_high
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue previous validation
- `thinking_mode` (string): Reasoning depth
- `temperature` (number): 0 = deterministic, 1 = creative
- `use_assistant_model` (boolean): Use expert model for validation
- `images` (string[]): Screenshots or diagrams

## Output

JSON with validation results, issues found, and commit readiness assessment.

## Invocation

```bash
# Start validation (step 1)
pal-precommit --step "Review staged changes" --step_number 1 --total_steps 3 --next_step_required true --findings "" --path "/path/to/repo"

# Continue validation (step 2+)
pal-precommit --step "Check for security issues" --step_number 2 --total_steps 3 --next_step_required true --findings "Found 3 modified files" --continuation_id "abc-123"

# With focus area
pal-precommit --step "Validate changes" --step_number 1 --total_steps 2 --next_step_required true --findings "" --path "/path/to/repo" --focus_on "security"
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
