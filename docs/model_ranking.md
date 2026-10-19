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

The scores in this catalog come from the
[Artificial Analysis (AA) Intelligence Index](https://artificialanalysis.ai/leaderboards/models)
(v4.3), **at `high` reasoning effort** (since 2026-10-13). A model that AA measures gets its score
from its `high` value through this ladder:

| AA Index | Score | | AA Index | Score | | AA Index | Score |
|---|---|---|---|---|---|---|---|
| 52+ | 20 | | 36-37 | 14 | | 18-20 | 8 |
| 50-51 | 19 | | 33-35 | 13 | | 15-17 | 7 |
| 46-49 | 18 | | 30-32 | 12 | | 12-14 | 6 |
| 43-45 | 17 | | 27-29 | 11 | | 9-11 | 5 |
| 41-42 | 16 | | 24-26 | 10 | | 7-8 | 4 |
| 38-40 | 15 | | 21-23 | 9 | | 0-6 | 3 |

- **Effort anchor:** the score describes the model at `high` effort. PAL tools default to
  `thinking_mode: medium`, so a typical call runs one level below the anchor and can score a few Index
  points lower (Claude Sonnet 5.5: 47 at high, 41 at medium). Ask for `thinking_mode: high` to get the
  scored behavior. For models that declare `effort_levels`, PAL sends the effort explicitly.
- **No `high` row:** when AA lists one row only (no effort variants), that row is the anchor. When AA
  has rows below and above `high` but not `high` itself, the anchor is a linear interpolation between
  them. When AA has only rows above `high`, the anchor is an **estimate**: the nearest row above, minus
  the median gap between that level and `high` across the models that AA measured at both levels. Each
  interpolated or estimated entry says so in its description, with the rows it used and a range.
- **Measured and estimated scores:** a model that AA does not list keeps an **estimated** score. The
  re-score to the `high` anchor lowered each such score of 12 or more by 1, the median change across
  the measured models with several effort levels; lower scores did not change. When AA publishes a
  value, the estimate is replaced.
- **Provisional scores:** a description that says PROVISIONAL marks a score that waits for an AA value,
  for example a "pro" reasoning-mode preset that AA has not measured.
- **Record the source:** each conf description cites the AA value and the effort level behind the
  score, so later updates stay consistent.

The [model catalog](model_catalog.md) lists every measured model with its per-effort Index values.
Generate it again with `python scripts/generate_model_catalog.py` after you change a conf file.

### Fields that support the score

| Field | Meaning |
|---|---|
| `aa_index` | The AA Index value at the `high` anchor behind the score (interpolated or estimated where AA has no `high` row). When two models share a score, the Anthropic provider uses it as the second sort key, so the model with the higher AA value wins the tie instead of the model whose name sorts last. |
| `aa_index_by_effort` | The AA value at each effort level, for example `{"low": 42, "medium": 48, "high": 50, "xhigh": 51, "max": 52}`. `default` means AA lists a single row. Values that AA marks as incomplete (`*`) are left out. |
| `effort_levels` | The reasoning-effort levels the route accepts. PAL sends the tool's `thinking_mode` as an explicit effort for these models (see [advanced usage](advanced-usage.md#thinking-modes-as-reasoning-effort)). |
| `auto_selectable` | `false` keeps a model out of auto mode. Use it for presets that cost much more per request, such as the OpenRouter `-pro` reasoning-mode presets and the Fusion meta-routers. |
| `dynamic_aliases` | Aliases that point at the model only when `DYNAMIC_MODEL_SELECTION` is on. They let a bare alias such as `haiku` follow the newest model without changing upstream defaults. |

### Known gaps

- Scores for models that AA does not list are estimates. Older models (for example Claude Opus 5, GPT-5.6
  Sol, Gemini 3.7 Flash) are no longer on the default AA leaderboard view, so their scores stay estimates.
- AA's per-effort rows can change. Read them again before a catalog refresh, and run
  `scripts/generate_model_catalog.py` after you change a conf file.

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
