# Model Capability Ranking

Auto mode needs a short, trustworthy list of models to suggest. The server
computes a capability rank for every model at runtime using a simple recipe:

1. Start with the human-supplied `intelligence_score` (1–20). This is the
   anchor—multiply it by five to map onto the 0–100 scale the server uses.
2. Add a few light bonuses for hard capabilities:
   - **Context window:** up to +5 (log-scale bonus when the model exceeds ~1K tokens).
   - **Output budget:** +2 for ≥65K tokens, +1 for ≥32K.
   - **Extended thinking:** +3 when the provider supports it.
   - **Function calling / JSON / images:** +1 each when available.
   - **Custom endpoints:** −1 to nudge cloud-hosted defaults ahead unless tuned.
3. Clamp the final score to 0–100 so downstream callers can rely on the range.

In code this looks like:

```python
base = clamp(intelligence_score, 1, 20) * 5
ctx_bonus = min(5, max(0, log10(context_window) - 3))
output_bonus = 2 if max_output_tokens >= 65_000 else 1 if >= 32_000 else 0
feature_bonus = (
    (3 if supports_extended_thinking else 0)
    + (1 if supports_function_calling else 0)
    + (1 if supports_json_mode else 0)
    + (1 if supports_images else 0)
)
penalty = 1 if provider == CUSTOM else 0

effective_rank = clamp(base + ctx_bonus + output_bonus + feature_bonus - penalty, 0, 100)
```

The bonuses are intentionally small—the human intelligence score does most
of the work so you can enforce organisational preferences easily.

## Picking an intelligence score

A straightforward rubric that mirrors typical provider tiers:

| Intelligence | Guidance                                                                                  |
|--------------|-------------------------------------------------------------------------------------------|
| 18–19 | Frontier reasoning models (Gemini 3.0 Pro, Gemini 2.5 Pro, GPT‑5.1 Codex, GPT‑5.1, GPT‑5) |
| 15–17 | Strong general models with large context (O3 Pro, DeepSeek R1)                            |
| 12–14 | Balanced assistants (Claude Opus/Sonnet, Mistral Large)                                   |
| 9–11  | Fast distillations (Gemini Flash, GPT-5 Mini, Mistral medium)                             |
| 6–8   | Local or efficiency-focused models (Llama 3 70B, Claude Haiku)                            |
| ≤5    | Experimental/lightweight models                                                           |

Record the reasoning for your scores so future updates stay consistent.

## How the rank is used

The ranked list is cached per provider and consumed by:
- Tool schemas (`model` parameter descriptions) when auto mode is active.
- The `listmodels` tool’s “top models” sections.
- Fallback messaging when a requested model is unavailable.

Because the rank is computed after restriction filters, only allowed models
appear in these summaries.

## Customising further

If you need a different weighting you can:
- Override `intelligence_score` in your provider or custom model config.
- Subclass the provider and override `get_effective_capability_rank()`.
- Post-process the rank via `get_capabilities_by_rank()` before surfacing it.

Most teams find that adjusting `intelligence_score` alone is enough to keep
auto mode honest without revisiting code.
