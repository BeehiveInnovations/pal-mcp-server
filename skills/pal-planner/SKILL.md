---
name: pal-planner
description: Creates detailed implementation plans with step-by-step workflow for features, refactoring, and architectural changes.
allowed-tools: Bash, Read
---

# PAL Planner

## Overview

Create detailed implementation plans for complex tasks. Breaks down features, refactoring efforts, or architectural changes into actionable steps.

## When to Use

- Planning new feature implementation
- Designing refactoring strategies
- Architectural change planning
- Breaking down complex tasks

## Workflow

Multi-step planning workflow:
1. Analyze requirements and constraints
2. Identify affected components
3. Design implementation approach
4. Create step-by-step action plan
5. Define validation criteria

## Parameters

### Required (Workflow Fields)
- `step` (string): Current planning step description
- `step_number` (integer): Current step number (starts at 1)
- `total_steps` (integer): Total planned steps
- `next_step_required` (boolean): Whether more steps needed

### Optional
- `branch_id` (string): Name for this branch (e.g., 'approach-A')
- `branch_from_step` (integer): Step number that this branch starts from
- `is_branch_point` (boolean): True when creating a new branch
- `is_step_revision` (boolean): True when replacing a previous step
- `revises_step_number` (integer): Step number being replaced
- `more_steps_needed` (boolean): True when expecting additional steps
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue previous planning
- `use_assistant_model` (boolean): Use expert model for analysis

## Output

JSON with implementation plan, dependencies, and recommended execution order.

## Invocation

```bash
# Start planning (step 1)
pal-planner --step "Analyze requirements for user auth feature" --step_number 1 --total_steps 5 --next_step_required true

# Continue planning (step 2+)
pal-planner --step "Design database schema" --step_number 2 --total_steps 5 --next_step_required true --continuation_id "abc-123"

# Create alternative branch
pal-planner --step "Alternative: OAuth approach" --step_number 3 --total_steps 5 --next_step_required true --branch_id "oauth-approach" --is_branch_point true
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
