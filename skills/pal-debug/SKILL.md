---
name: pal-debug
description: Performs systematic debugging and root cause analysis, identifying and fixing bugs through structured investigation.
allowed-tools: Bash, Read
---

# PAL Debug

## Overview

Structured debugging workflow for identifying root causes. Uses systematic investigation to track down and resolve issues.

## When to Use

- Investigating unexpected behavior
- Tracking down elusive bugs
- Understanding error patterns
- Root cause analysis

## Workflow

Multi-step debugging process:
1. Reproduce and document the issue
2. Gather relevant context and logs
3. Form hypotheses
4. Test and eliminate possibilities
5. Identify root cause and solution

## Parameters

### Required (Workflow Fields)
- `step` (string): Investigation step description
- `step_number` (integer): Current step index (starts at 1)
- `total_steps` (integer): Estimated total investigation steps
- `next_step_required` (boolean): True if more investigation needed
- `findings` (string): Clues, evidence, disproven theories

### Optional
- `files_checked` (string[]): All examined files (absolute paths)
- `relevant_files` (string[]): Files directly relevant to issue (absolute paths)
- `hypothesis` (string): Concrete root cause theory from evidence
- `confidence` (string): exploring, low, medium, high, very_high, almost_certain, certain
- `issues_found` (object[]): Issues with severity levels
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue previous investigation
- `thinking_mode` (string): Reasoning depth
- `temperature` (number): 0 = deterministic, 1 = creative
- `use_assistant_model` (boolean): Use expert model for analysis
- `images` (string[]): Screenshots/visuals clarifying the issue

## Output

JSON with debugging findings, hypotheses, and recommended fixes.

## Model Selection

- Models are detected at runtime based on your configuration
- Use `pal-listmodels` to see available models before specifying one
- Default: auto-select best available model for the task
