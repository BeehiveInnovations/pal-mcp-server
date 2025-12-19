---
name: pal-consensus
description: Builds consensus using multiple AI models for important decisions, providing diverse perspectives to reach balanced conclusions.
allowed-tools: Bash, Read
---

# PAL Consensus

## Overview

Get perspectives from multiple AI models to build consensus on important decisions. Uses a workflow to consult each model and synthesize findings.

## When to Use

- Critical architectural decisions
- Evaluating competing approaches
- Risk assessment for major changes
- When diverse perspectives are valuable

## Workflow

Multi-step consensus process:
1. Your independent analysis
2. Consult model 1
3. Consult model 2
4. ... (continue for each model)
5. Final synthesis

## Parameters

### Required (Workflow Fields)
- `step` (string): Step 1 is your analysis; later steps consult models
- `step_number` (integer): Current step index (starts at 1)
- `total_steps` (integer): Number of models plus final synthesis
- `next_step_required` (boolean): True if more consultations remain
- `findings` (string): Step 1 is your analysis for later synthesis

### Optional
- `models` (string[]): Models to consult (provide at least 2)
- `relevant_files` (string[]): Supporting files (absolute paths)
- `images` (string[]): Visual context (absolute paths or base64)
- `current_model_index` (integer): Internal tracking
- `model_responses` (object[]): Internal log of responses
- `continuation_id` (string): Continue previous consensus
- `use_assistant_model` (boolean): Use expert model for synthesis

## Output

JSON with multi-model analysis, areas of agreement, disagreements, and synthesized recommendation.

## Invocation

```bash
# Start consensus (step 1 - your analysis)
pal-consensus --step "Evaluate REST vs GraphQL for our API" --step_number 1 --total_steps 4 --next_step_required true --findings "Initial analysis: REST is simpler but GraphQL offers flexibility" --models '["gemini-2.5-pro", "gpt-4o"]'

# Continue (step 2+ - consult models)
pal-consensus --step "Consulting model 1" --step_number 2 --total_steps 4 --next_step_required true --findings "" --continuation_id "abc-123"
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Provide `models` array to specify which models to consult for consensus
- Use `pal-listmodels` to see available model names first
