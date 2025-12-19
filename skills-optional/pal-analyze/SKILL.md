---
name: pal-analyze
description: Analyzes complex codebases deeply, examining architecture, patterns, dependencies, and code structure.
allowed-tools: Bash, Read
---

# PAL Analyze

## Overview

Comprehensive codebase analysis covering architecture, design patterns, and dependencies. Uses multi-step workflow for thorough investigation.

## When to Use

- Understanding unfamiliar codebases
- Analyzing architectural patterns
- Mapping dependencies between components
- Identifying code structure issues

## Workflow

Multi-step analysis process:
1. Define analysis strategy and scope
2. Examine code structure
3. Identify patterns and dependencies
4. Synthesize findings
5. Provide recommendations

## Parameters

### Required (Workflow Fields)
- `step` (string): Analysis plan and current findings
- `step_number` (integer): Current step number (starts at 1)
- `total_steps` (integer): Estimated total steps
- `next_step_required` (boolean): Whether more analysis needed
- `findings` (string): Discoveries from this step

### Optional
- `files_checked` (string[]): Files examined (absolute paths)
- `relevant_files` (string[]): Files relevant to findings (absolute paths)
- `analysis_type` (string): architecture, performance, security, dependencies, etc.
- `output_format` (string): summary, detailed, or actionable
- `issues_found` (object[]): Issues with severity levels
- `hypothesis` (string): Current theory
- `confidence` (string): exploring, low, medium, high, very_high
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue previous analysis
- `thinking_mode` (string): Reasoning depth
- `temperature` (number): 0 = deterministic, 1 = creative
- `use_assistant_model` (boolean): Use expert model for analysis
- `images` (string[]): Architecture diagrams or visuals

## Output

JSON with analysis findings, architectural insights, and recommendations.

## Invocation

```bash
# Start analysis (step 1)
pal-analyze --step "Analyze codebase architecture" --step_number 1 --total_steps 4 --next_step_required true --findings ""

# Continue analysis (step 2+)
pal-analyze --step "Examine dependencies" --step_number 2 --total_steps 4 --next_step_required true --findings "Found MVC pattern" --continuation_id "abc-123"

# With specific analysis type
pal-analyze --step "Security analysis" --step_number 1 --total_steps 3 --next_step_required true --findings "" --analysis_type security --relevant_files '["./src/auth.py"]'
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
