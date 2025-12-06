---
name: pal-tracer
description: Traces code execution and analyzes flow, mapping function calls, data transformations, and execution paths.
allowed-tools: Bash, Read
---

# PAL Tracer

## Overview

Trace code execution paths, function calls, and data flow. Uses multi-step workflow to map how code executes and data transforms.

## When to Use

- Understanding execution flow
- Tracing data transformations
- Debugging complex call chains
- Mapping function dependencies

## Workflow

Multi-step tracing process:
1. Define tracing target and mode
2. Map initial call structure
3. Trace data flow
4. Identify transformations
5. Synthesize execution path

## Parameters

### Required (Workflow Fields)
- `step` (string): Tracing plan and current findings
- `step_number` (integer): Current step number (starts at 1)
- `total_steps` (integer): Estimated total steps
- `next_step_required` (boolean): Whether more tracing needed
- `findings` (string): Call chains, data flow, execution paths
- `target_description` (string): What to trace and WHY
- `trace_mode` (string): ask (prompts user), static, dynamic, hybrid, data_flow

### Optional
- `files_checked` (string[]): Files examined (absolute paths)
- `relevant_files` (string[]): Files in the execution path (absolute paths)
- `hypothesis` (string): Current theory about flow
- `confidence` (string): exploring, low, medium, high, very_high
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue previous tracing
- `thinking_mode` (string): Reasoning depth
- `temperature` (number): 0 = deterministic, 1 = creative
- `use_assistant_model` (boolean): Use expert model for analysis
- `images` (string[]): Flow charts or architecture diagrams

## Output

JSON with execution trace, call graph, and data flow analysis.

## Model Selection

- Models are detected at runtime based on your configuration
- Use `pal-listmodels` to see available models before specifying one
- Default: auto-select best available model for the task
