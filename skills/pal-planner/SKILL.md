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

## Model Selection

- Models are detected at runtime based on your configuration
- Use `pal-listmodels` to see available models before specifying one
- Default: auto-select best available model for the task
