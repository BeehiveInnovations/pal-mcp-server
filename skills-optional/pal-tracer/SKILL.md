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

## Invocation

```bash
# Start tracing (step 1)
pal-tracer --step "Map call structure" --step_number 1 --total_steps 4 --next_step_required true --findings "" --target_description "Trace user login flow" --trace_mode static

# Continue tracing (step 2+)
pal-tracer --step "Trace data flow" --step_number 2 --total_steps 4 --next_step_required true --findings "Entry point: login()" --target_description "Trace user login flow" --trace_mode static --continuation_id "abc-123"

# With file context
pal-tracer --step "Analyze execution path" --step_number 1 --total_steps 3 --next_step_required true --findings "" --target_description "Order processing" --trace_mode data_flow --relevant_files '["./src/order.py"]'
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
