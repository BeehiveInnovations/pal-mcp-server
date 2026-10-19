# Open-model `intelligence_score` calibration

How the `intelligence_score` (the 1–20 signal that orders the `DEFAULT_MODEL=auto` menu and breaks
ties) was set for the 22 open-weight OpenRouter models added to `conf/openrouter_models.json`. The
scores were derived from current benchmark data and cross-checked by three models — **Opus 4.8 +
GPT-5.4 + Gemini-3.5-Flash**; both external reviewers signed off with no remaining changes. This
document records the reasoning so the numbers aren't a black box.

## Benchmark research (method & sources)

Data gathered **2026-06-01, HuggingFace-first**: model cards (MMLU-Pro, GPQA-Diamond, LiveCodeBench,
AIME, SWE-bench Verified & Pro). For API-only models not on HuggingFace (Qwen-Max, GLM, MiniMax,
Kimi), the **Artificial Analysis Intelligence Index** and **LMArena** Elo were used as a fallback,
labeled as such. Every model ID and served context window was verified against the live OpenRouter
`/api/v1/models` response (343 models).

The scale is an integer 1–20, **anchored to existing catalog entries**: `gpt-5.5`=20,
`gpt-5.1-codex`/`gemini-3.1-pro`=19, `gpt-5.2`=18, `gpt-5-pro`=17 · `deepseek-r1-0528`=15,
`grok-4`=15 · `mistral-large-2411`=11, `llama-3-70b`=9. Bands: 17–20 frontier, 14–16 strong
near-frontier open flagship, 11–13 solid mid, 8–10 small/older. Scores reflect benchmark standing
**relative to those anchors**, not absolute benchmark numbers.

## Reasoning by model

- **Opus 4.8** (orchestration + synthesis): commissioned the benchmark research, set the anchors,
  integrated both external reviews, made the final calls, and verified the disputed capability flags
  against OpenRouter's own `supported_parameters` (source data over prior intuition).
- **GPT-5.4** (benchmark-grounded): argued the 2026 open flagships were under-scored and the
  2025-era / non-reasoning models over-scored. Strongest calls: `mistral-large-2512` is a
  non-reasoning MoE (GPQA-D 48.6, LiveCodeBench 29.3) that benchmarks **below** Llama-4-Maverick, so
  its initial 13 was ~2 points high; `llama-4-maverick` (Apr-2025, weak coding) belongs near the
  `mistral-large-2411`=11 anchor, not with the 2026 flagships. Also flagged a stale "no OpenRouter
  model supports reasoning" README note. **Round-2 verdict: ship it.**
- **Gemini-3.5-Flash** (positional / structural): pushed back on the downgrades — a flagship should
  outrank its cheap tier and reflect generational improvement (wanted mistral-large=13, maverick=13,
  scout=11, gpt-oss-120b=14, nemotron-super=13) — and flagged the awkward `mistral-large == mistral-small`
  tie. **Round-2 verdict: ship it**; confirmed family monotonicity is clean.

## Synthesis — where the final numbers landed

- **Applied all 2026-flagship upgrades** (both reviewers agreed or didn't object): qwen3.7-max /
  kimi-k2.6 / glm-5.1 → 16; minimax-m3 / mimo-v2.5-pro → 15; deepseek-v4-flash → 14; qwen3.6-flash /
  minimax-m2.5 / mimo-v2.5 → 13; glm-4.7-flash → 12.
- **Split-the-difference where the reviewers bracketed a value:** `mistral-large-2512` = **12**
  (GPT 11 / Gemini 13; also resolves the large==small tie → large 12 > small 11) and
  `llama-4-maverick` = **12** (GPT 11 / Gemini 13); `llama-4-scout` = 10.
- **Sided with GPT-5.4 / the benchmarks** over Gemini's positional argument: `gpt-oss-120b` = 13
  (Aug-2025, GPQA-D 80.1) and `nemotron-3-super` = 12 (weak LiveCodeBench 31).
- **Overrode both reviewers on capability flags** after checking the source: kept
  `supports_extended_thinking=true` for the flash/small models (gemma-4, glm-4.7-flash, qwen3.6-flash,
  mimo-v2.5, nemotron-nano) because OpenRouter reports `reasoning=true` for them; kept the uncapped
  OR-served `max_output_tokens` (repo precedent: grok-4 256K/256K).

## Changes that landed

- **15 `intelligence_score` updates** (net: 2026 open flagships up, 2025-era / non-reasoning down).
- **3 context windows** corrected to the provider-**served** value (the catalog advertised the
  architectural max): minimax-m3 `1048576→524288`, llama-4-scout `10000000→327680`, nemotron-3-super
  `1000000→262144`.
- **De-staled** the "no OpenRouter model supports extended thinking" note in the `_README` field
  descriptions of all conf files (azure/xai/openai/gemini/openrouter) — now false (gpt-5.x,
  gemini-3.x, grok-4, and the open-weight models all advertise reasoning).

## Final scores

| Score | Models |
|---|---|
| 16 | deepseek-v4-pro, qwen3.7-max, kimi-k2.6, glm-5.1 |
| 15 | minimax-m3, mimo-v2.5-pro |
| 14 | deepseek-v4-flash, kimi-k2.5 |
| 13 | qwen3.6-flash, minimax-m2.5, mimo-v2.5, gpt-oss-120b |
| 12 | glm-4.7-flash, gemma-4-31b-it, mistral-large-2512, llama-4-maverick, nemotron-3-super-120b-a12b |
| 11 | gemma-4-26b-a4b-it, mistral-small-2603, gpt-oss-20b |
| 10 | llama-4-scout, nemotron-3-nano-30b-a3b |

_Sources: huggingface.co model cards; Artificial Analysis Intelligence Index; LMArena; OpenRouter
`/api/v1/models` (served context + capability params)._

## Addendum — Ox Alpha (removed 2026-09-24)

`stealth/ox-alpha` was an anonymous stealth model on OpenRouter (free preview from 2026-08-20). It had
no Artificial Analysis coverage, so it was the only entry scored from LiveBench. The preview ended and
OpenRouter no longer lists the slug, so the entry was removed from the catalog.
