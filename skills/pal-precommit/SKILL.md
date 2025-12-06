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

## Model Selection

- Models are detected at runtime based on your configuration
- Use `pal-listmodels` to see available models before specifying one
- Default: auto-select best available model for the task
