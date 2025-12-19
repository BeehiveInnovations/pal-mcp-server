---
name: pal-thinkdeep
description: Provides deep analysis and extended reasoning for thorough exploration, multi-step reasoning, and comprehensive analysis of complex problems.
allowed-tools: Bash, Read
---

# PAL ThinkDeep

## Overview

Extended reasoning for complex problems requiring deep analysis. Uses a multi-step workflow with forced pauses between steps for thorough investigation.

## When to Use

- Complex architectural decisions
- Debugging difficult or mysterious issues
- Analyzing trade-offs between approaches
- Understanding intricate system behaviors

## Workflow

Multi-step deep thinking process:
1. Define the problem and analysis approach
2. Gather and analyze relevant context
3. Form and test hypotheses
4. Synthesize findings
5. Draw conclusions with evidence

## Parameters

### Required (Workflow Fields)
- `step` (string): Current work step content and findings
- `step_number` (integer): Current step number (starts at 1)
- `total_steps` (integer): Estimated total steps needed
- `next_step_required` (boolean): Whether another step is needed
- `findings` (string): Discoveries, insights, and evidence from this step

### Optional
- `files_checked` (string[]): Files examined during this step (absolute paths)
- `relevant_files` (string[]): Files directly relevant to analysis (absolute paths)
- `focus_areas` (string[]): Aspects to focus on (architecture, performance, security, etc.)
- `hypothesis` (string): Current theory based on work
- `confidence` (string): exploring, low, medium, high, very_high, almost_certain, certain
- `issues_found` (object[]): Issues with severity levels
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue previous analysis
- `thinking_mode` (string): Reasoning depth (default: high for thinkdeep)
- `temperature` (number): 0 = deterministic, 1 = creative
- `use_assistant_model` (boolean): Use assistant model for expert analysis

## Output

JSON response with deep analysis results, findings, and workflow continuation guidance.

## Invocation

```bash
# Start deep analysis (step 1)
pal-thinkdeep --step "Analyze the authentication flow" --step_number 1 --total_steps 4 --next_step_required true --findings ""

# Continue analysis (step 2+)
pal-thinkdeep --step "Examine token validation" --step_number 2 --total_steps 4 --next_step_required true --findings "Found JWT implementation" --continuation_id "abc-123"

# With file context
pal-thinkdeep --step "Review architecture" --step_number 1 --total_steps 3 --next_step_required true --findings "" --relevant_files '["./src/auth.py"]'
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
