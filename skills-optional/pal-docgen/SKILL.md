---
name: pal-docgen
description: Generates documentation including docstrings, README files, and API documentation for code.
allowed-tools: Bash, Read
---

# PAL DocGen

## Overview

Generate comprehensive documentation including docstrings, README files, and API documentation. Uses multi-step workflow to document code systematically.

## When to Use

- Adding documentation to code
- Creating README files
- Generating API docs
- Improving code documentation

## Workflow

Multi-step documentation generation:
1. Analyze code structure and purpose
2. Document functions and classes
3. Generate README or API docs
4. Add inline comments for complex logic
5. Review and finalize

## Parameters

### Required (Workflow Fields)
- `step` (string): Documentation plan and current progress
- `step_number` (integer): Current step number (starts at 1)
- `total_steps` (integer): Estimated total steps
- `next_step_required` (boolean): Whether more documentation needed
- `findings` (string): Documentation insights and progress
- `num_files_documented` (integer): Files documented so far
- `total_files_to_document` (integer): Total files to document
- `update_existing` (boolean): Polish existing docs (default: true)
- `document_flow` (boolean): Include call flow notes (default: true)
- `document_complexity` (boolean): Include Big O analysis (default: true)
- `comments_on_complex_logic` (boolean): Add inline comments (default: true)

### Optional
- `relevant_files` (string[]): Files to document (absolute paths)
- `issues_found` (object[]): Documentation issues with severity
- `continuation_id` (string): Continue previous documentation
- `use_assistant_model` (boolean): Use expert model for analysis

## Output

JSON with generated documentation content and formatting suggestions.

## Invocation

```bash
# Start documentation (step 1)
pal-docgen --step "Analyze code structure" --step_number 1 --total_steps 4 --next_step_required true --findings "" --num_files_documented 0 --total_files_to_document 5 --relevant_files '["./src/main.py"]'

# Continue documentation (step 2+)
pal-docgen --step "Document functions" --step_number 2 --total_steps 4 --next_step_required true --findings "Found 10 functions" --num_files_documented 1 --total_files_to_document 5 --continuation_id "abc-123"
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
