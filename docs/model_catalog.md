# Model catalog (measured models and explicit-only presets)

Generated from `conf/*_models.json` by `scripts/generate_model_catalog.py` on 2026-10-14. Do not edit by hand; run the script after a catalog change.

- **Scope:** every model with a measured Artificial Analysis (AA) Intelligence Index value, plus the explicit-only presets. Older and unmeasured entries are in the conf files only.
- **Score:** the 1-20 `intelligence_score` that auto mode ranks by. See [model_ranking.md](model_ranking.md) for how it is anchored to the AA Index.
- **AA Index by effort:** the AA v4.3 leaderboard value at each effort level (`aa_index_by_effort`). `default` means AA lists one row for the model.
- **Routes:** `native` is the creator's own API (needs that creator's key); `openrouter` is the OpenRouter mirror (needs `OPENROUTER_API_KEY`); `chatgpt` is a ChatGPT plan through the Codex CLI (needs `CHATGPT_ENABLED=true` and `codex login`, see [chatgpt_provider.md](chatgpt_provider.md)).
- **Explicit-only:** `auto_selectable: false`. Auto mode never picks the model; call it by name.
- **Flag-only aliases:** these bare aliases point at the model only when `DYNAMIC_MODEL_SELECTION` is on; otherwise they keep the target that upstream PAL gives them.

## Anthropic

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| Claude Opus 5.5 | 20 | low 42, medium 51, high 54, xhigh 56, max 58 | native: `claude-opus-5-5`<br>openrouter: `anthropic/claude-opus-5.5` | `claude-opus`, `claude-opus-5.5`, `opus`, `opus-5.5` |  |
| Claude Fable 5.1 | 19 | low 47, medium 49, high 51, xhigh 53, max 53 | native: `claude-fable-5-1`<br>openrouter: `anthropic/claude-fable-5.1` | `claude-fable-5.1`, `fable`, `fable-5.1` |  |
| Claude Sonnet 5.5 | 18 | low 36, medium 41, high 47, xhigh 52, max 56 | native: `claude-sonnet-5-5`<br>openrouter: `anthropic/claude-sonnet-5.5` | `claude-sonnet`, `claude-sonnet-5.5`, `sonnet`, `sonnet-5.5` |  |
| Claude Haiku 5.5 | 15 | low 29, medium 34, high 38, xhigh 41, max 43 | native: `claude-haiku-5-5`<br>openrouter: `anthropic/claude-haiku-5.5` | `claude-haiku`, `claude-haiku-5.5`, `haiku`, `haiku-5.5`, `or-claude-haiku` |  |

## OpenAI

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| OpenAI (GPT-6.1 Sol) | 19 | low 42, medium 48, high 50, xhigh 51, max 52 | native: `gpt-6.1-sol`<br>openrouter: `openai/gpt-6.1-sol`<br>chatgpt: `chatgpt/gpt-6.1-sol` | `gpt6.1-sol`, `gpt6.1sol`, `or-gpt6.1-sol`, `sol` |  |
| GPT-6.1 Sol Pro | 19 | not measured | openrouter: `openai/gpt-6.1-sol-pro` | `gpt-6.1-sol-pro`, `or-gpt6.1-sol-pro` | explicit-only, provisional score |
| OpenAI (GPT-6 Astra) | 19 | low 46, medium 50, high 51, xhigh 52, max 53 | native: `gpt-6-astra`<br>openrouter: `openai/gpt-6-astra`<br>chatgpt: `chatgpt/gpt-6-astra` | `astra`, `gpt6-astra`, `gpt6astra`, `or-gpt6-astra` |  |
| GPT-6 Astra Pro | 19 | not measured | openrouter: `openai/gpt-6-astra-pro` | `astra-pro`, `gpt6-astra-pro`, `or-gpt6-astra-pro` | explicit-only, provisional score |
| OpenAI (GPT-5.6 Terra) | 13 | non-reasoning 21, low 27, medium 30, high 34, xhigh 38, max 42 | native: `gpt-5.6-terra`<br>openrouter: `openai/gpt-5.6-terra`<br>chatgpt: `chatgpt/gpt-5.6-terra` | `gpt5.6-terra`, `gpt5.6terra`, `or-gpt5.6-terra`, `terra` |  |
| OpenAI (GPT-6 Luna) | 13 | non-reasoning 18, low 22, medium 30, high 33, xhigh 35, max 38 | native: `gpt-6-luna`<br>openrouter: `openai/gpt-6-luna`<br>chatgpt: `chatgpt/gpt-6-luna` | `gpt6-luna`, `gpt6luna`, `luna`, `or-gpt6-luna` |  |
| GPT-6 Luna Pro | 13 | not measured | openrouter: `openai/gpt-6-luna-pro` | `gpt-6-luna-pro`, `or-gpt6-luna-pro` | explicit-only, provisional score |
| GPT-OSS 120B | 6 | high 12 | openrouter: `openai/gpt-oss-120b` | `gpt-oss`, `gpt-oss-120b` |  |
| GPT-OSS 20B | 5 | high 9 | openrouter: `openai/gpt-oss-20b` | `gpt-oss-20b`, `gpt-oss-mini` |  |

## Google

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| Gemini (4 Argon) | 20 | high 53 | native: `gemini-4-argon`<br>openrouter: `google/gemini-4-argon` | `argon`, `gemini-4-argon-or`, `gemini-argon`, `or-gemini-4-argon` |  |
| Gemini 3.8 Flash | 16 | low 33, medium 40, high 41 | native: `gemini-3.8-flash`<br>openrouter: `google/gemini-3.8-flash` | `flash3.8`, `gemini-3.8-flash`, `gemini-flash-latest`; flag-only: `flash` |  |
| Gemini 3.1 Pro Preview | 12 | default 30 | native: `gemini-3.1-pro-preview`<br>openrouter: `google/gemini-3.1-pro-preview` | `gemini-3.1-pro`, `gemini-pro-latest`, `or-gemini-pro`; flag-only: `gemini-pro`, `gemini3`, `pro` |  |
| Gemini 3.5 Flash-Lite | 9 | default 22 | native: `gemini-3.5-flash-lite` | `flashlite3.5`, `gemini-flash-lite-latest`; flag-only: `flash-lite`, `flashlite` |  |
| Gemma 4 31B | 7 | default 15 | openrouter: `google/gemma-4-31b-it` | `gemma`, `gemma-4`, `gemma-4-31b` |  |

## xAI

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| X.AI (Grok 4.7) | 18 | low 42, high 46, xhigh 46 | native: `grok-4.7`<br>openrouter: `x-ai/grok-4.7` | `grok-4.7`, `grok4.7`; flag-only: `grok` |  |

## Meta

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| Muse Wonder | 18 | max 52 | openrouter: `meta/muse-wonder` | `muse-wonder`, `wonder` |  |
| Muse Spark 1.3 | 17 | xhigh 45, max 48 | openrouter: `meta/muse-spark-1.3` | `muse`, `muse-spark`, `muse-spark-1.3` |  |

## DeepSeek

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| DeepSeek V4.1 Flash | 13 | non-reasoning 25, max 39 | native: `deepseek-v4.1-flash`<br>openrouter: `deepseek/deepseek-v4.1-flash` | `deepseek`, `deepseek-flash`, `deepseek-v4.1-flash`, `v4.1-flash` |  |
| DeepSeek V4 Pro | 12 | non-reasoning 20, max 36 | native: `deepseek-v4-pro`<br>openrouter: `deepseek/deepseek-v4-pro` | `deepseek-v4`, `deepseek-v4-pro` |  |

## Alibaba (Qwen)

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| Qwen3.8 Max 0902 | 17 | default 45 | native: `qwen3.8-max-0902`<br>openrouter: `qwen/qwen3.8-max-0902` | `qwen-max`, `qwen3-max`, `qwen3.8-max-0902`, `qwen3.8-max-2026-09-02` |  |
| Qwen3.8 2.4T A95B | 15 | default 40 | openrouter: `qwen/qwen3.8-2.4t-a95b` | `qwen3.8-2.4t`, `qwen3.8-2.4t-a95b` |  |
| Qwen3.8 Flash | 15 | default 40 | native: `qwen3.8-flash`<br>openrouter: `qwen/qwen3.8-flash` | `qwen-flash`, `qwen3-flash`, `qwen3.8-flash` |  |
| Qwen3.8 27B | 12 | non-reasoning 20, low 26, medium 28, xhigh 34 | openrouter: `qwen/qwen3.8-27b` | `qwen3.8-27b` |  |

## Z.ai (GLM)

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| GLM-5.3 Flash | 16 | default 42 | native: `glm-5.3-flash`<br>openrouter: `z-ai/glm-5.3-flash` | `glm-5.3-flash`, `glm-flash` |  |
| GLM-5.3 | 15 | low 34, max 45 | native: `glm-5.3`<br>openrouter: `z-ai/glm-5.3` | `glm`, `glm-5.3`, `glm5` |  |

## Moonshot (Kimi)

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| Kimi K3 | 14 | low 30, max 44 | native: `kimi-k3`<br>openrouter: `moonshotai/kimi-k3` | `kimi`, `kimi-k3` |  |
| Kimi K2.7 Code | 10 | default 26 | openrouter: `moonshotai/kimi-k2.7-code` | `kimi-k2.7-code` |  |

## MiniMax

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| MiniMax M3 | 11 | default 29 | native: `MiniMax-M3`<br>openrouter: `minimax/minimax-m3` | `minimax`, `minimax-m3` |  |

## Xiaomi

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| MiMo V2.6 Pro | 18 | default 46 | openrouter: `xiaomi/mimo-v2.6-pro` | `mimo`, `mimo-pro`, `mimo-v2.6-pro` |  |
| MiMo V2.6 Flash | 15 | default 38 | openrouter: `xiaomi/mimo-v2.6-flash` | `mimo-flash`, `mimo-v2.6-flash` | provisional score |

## Mistral

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| Mistral Large 4 | 15 | default 38 | openrouter: `mistralai/mistral-large-4-0` | `mistral-large-4`, `mistral-large-4-0` |  |

## NVIDIA

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| Nemotron 3 Ultra 550B A55B | 9 | default 23 | openrouter: `nvidia/nemotron-3-ultra-550b-a55b` | `nemotron-3-ultra` |  |
| Nemotron 3 Super | 6 | default 13 | native: `nvidia/nemotron-3-super-120b-a12b`<br>openrouter: `nvidia/nemotron-3-super-120b-a12b` | `nemotron`, `nemotron-super` |  |
| Nemotron 3 Nano | 5 | default 9 | native: `nvidia/nemotron-3-nano-30b-a3b`<br>openrouter: `nvidia/nemotron-3-nano-30b-a3b` | `nemotron-nano` |  |

## StepFun

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| Step 5 Preview | 17 | default 44 | openrouter: `stepfun/step-5-preview` | `step-5`, `step-5-preview` |  |

## Cohere

| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |
|---|---|---|---|---|---|
| Command A Plus | 6 | default 13 | openrouter: `cohere/command-a-plus` | `command-a+`, `command-a-plus` |  |
