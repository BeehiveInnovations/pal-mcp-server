#!/usr/bin/env python3
"""Generate docs/model_catalog.md from conf/*_models.json.

Lists every model with a measured Artificial Analysis (AA) Index value, plus the explicit-only presets,
grouped by lab. One row per model: the native and OpenRouter routes are merged. Run it after any
catalog change:

    python scripts/generate_model_catalog.py
"""

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONF = ROOT / "conf"
OUT = ROOT / "docs" / "model_catalog.md"

# Native conf file -> lab; OpenRouter vendor prefix -> lab.
NATIVE_LAB = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "gemini": "Google",
    "xai": "xAI",
    "deepseek": "DeepSeek",
    "qwen": "Alibaba (Qwen)",
    "zai": "Z.ai (GLM)",
    "moonshot": "Moonshot (Kimi)",
    "minimax": "MiniMax",
    "nvidia": "NVIDIA",
    "mistral": "Mistral",
}
OR_LAB = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google",
    "x-ai": "xAI",
    "deepseek": "DeepSeek",
    "qwen": "Alibaba (Qwen)",
    "z-ai": "Z.ai (GLM)",
    "moonshotai": "Moonshot (Kimi)",
    "minimax": "MiniMax",
    "nvidia": "NVIDIA",
    "mistralai": "Mistral",
    "meta": "Meta",
    "xiaomi": "Xiaomi",
    "stepfun": "StepFun",
    "cohere": "Cohere",
}
LAB_ORDER = [
    "Anthropic",
    "OpenAI",
    "Google",
    "xAI",
    "Meta",
    "DeepSeek",
    "Alibaba (Qwen)",
    "Z.ai (GLM)",
    "Moonshot (Kimi)",
    "MiniMax",
    "Xiaomi",
    "Mistral",
    "NVIDIA",
    "StepFun",
    "Cohere",
]
EFFORT_ORDER = ["non-reasoning", "low", "medium", "high", "xhigh", "max", "default"]


def key_of(name: str) -> str:
    """Merge key for a model across routes: the last path part, normalized."""
    tail = name.split("/")[-1].lower()
    return tail.replace("claude-", "").replace(".", "-").replace("-it", "")


NAME_OVERRIDES = {"mistralai/mistral-large-4-0": "Mistral Large 4"}
SPECIAL_WORDS = {"mimo": "MiMo", "minimax": "MiniMax"}


def pretty(model_id: str) -> str:
    """Readable name for an OpenRouter-only ID, for example openai/gpt-6.1-sol-pro -> GPT-6.1 Sol Pro."""
    if model_id in NAME_OVERRIDES:
        return NAME_OVERRIDES[model_id]
    words = model_id.split("/")[-1].replace("-it", "").split("-")
    out = []
    for w in words:
        if w in ("gpt", "glm", "oss"):
            out.append(w.upper())
        elif re.fullmatch(r"\d+(\.\d+)?[bt]", w) or re.fullmatch(r"a\d+b", w):
            out.append(w.upper())  # parameter sizes: 27b -> 27B, 2.4t -> 2.4T, a95b -> A95B
        elif w in SPECIAL_WORDS:
            out.append(SPECIAL_WORDS[w])
        elif any(c.isdigit() for c in w):
            out.append(w[0].upper() + w[1:])  # k2.7 -> K2.7, v2.6 -> V2.6
        else:
            out.append(w.capitalize())
    text = " ".join(out)
    for a, b in (("GPT ", "GPT-"), ("GLM ", "GLM-")):
        text = text.replace(a, b)
    return text


def fmt_effort(values: dict) -> str:
    return ", ".join(f"{k} {values[k]}" for k in sorted(values, key=EFFORT_ORDER.index))


rows = defaultdict(dict)
for path in sorted(CONF.glob("*_models.json")):
    conf = path.stem.replace("_models", "")
    if conf == "chatgpt":
        continue  # an extra route for OpenAI models already listed; added below
    for m in json.loads(path.read_text()).get("models", []):
        measured = bool(m.get("aa_index_by_effort"))
        explicit_only = m.get("auto_selectable") is False and "fusion" not in m["model_name"]
        if not (measured or explicit_only):
            continue
        if conf == "openrouter":
            lab = OR_LAB.get(m["model_name"].split("/")[0])
            route = "openrouter"
        else:
            lab = NATIVE_LAB.get(conf)
            route = "native"
        if lab is None:
            continue
        row = rows[(lab, key_of(m["model_name"]))]
        row.setdefault("names", {})[route] = m["model_name"]
        row["score"] = m["intelligence_score"]
        row["effort"] = m.get("aa_index_by_effort") or row.get("effort")
        row["explicit_only"] = row.get("explicit_only", False) or explicit_only
        row["provisional"] = row.get("provisional", False) or "PROVISIONAL" in m.get("description", "")
        row["aliases"] = sorted(set(row.get("aliases", [])) | set(m.get("aliases", [])))
        row["dynamic"] = sorted(set(row.get("dynamic", [])) | set(m.get("dynamic_aliases", [])))
        if m.get("friendly_name"):
            row["friendly"] = m["friendly_name"]

# ChatGPT-plan route (Codex CLI): attach it to the OpenAI rows it serves. It adds no rows of its own.
for m in json.loads((CONF / "chatgpt_models.json").read_text()).get("models", []):
    row = rows.get(("OpenAI", key_of(m["model_name"])))
    if row is not None:
        row["names"]["chatgpt"] = m["model_name"]

lines = [
    "# Model catalog (measured models and explicit-only presets)",
    "",
    f"Generated from `conf/*_models.json` by `scripts/generate_model_catalog.py` on {date.today().isoformat()}. "
    "Do not edit by hand; run the script after a catalog change.",
    "",
    "- **Scope:** every model with a measured Artificial Analysis (AA) Intelligence Index value, plus the "
    "explicit-only presets. Older and unmeasured entries are in the conf files only.",
    "- **Score:** the 1-20 `intelligence_score` that auto mode ranks by. See [model_ranking.md](model_ranking.md) "
    "for how it is anchored to the AA Index.",
    "- **AA Index by effort:** the AA v4.3 leaderboard value at each effort level (`aa_index_by_effort`). "
    "`default` means AA lists one row for the model.",
    "- **Routes:** `native` is the creator's own API (needs that creator's key); `openrouter` is the "
    "OpenRouter mirror (needs `OPENROUTER_API_KEY`); `chatgpt` is a ChatGPT plan through the Codex CLI (needs "
    "`CHATGPT_ENABLED=true` and `codex login`, see [chatgpt_provider.md](chatgpt_provider.md)).",
    "- **Explicit-only:** `auto_selectable: false`. Auto mode never picks the model; call it by name.",
    "- **Flag-only aliases:** these bare aliases point at the model only when `DYNAMIC_MODEL_SELECTION` is on; "
    "otherwise they keep the target that upstream PAL gives them.",
    "",
]
for lab in LAB_ORDER:
    lab_rows = [(k, r) for (lb, k), r in rows.items() if lb == lab]
    if not lab_rows:
        continue
    lines += [
        f"## {lab}",
        "",
        "| Model | Score | AA Index by effort | Routes (model ID) | Aliases | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in sorted(lab_rows, key=lambda kr: (-kr[1]["score"], kr[0])):
        names = r["names"]
        title = r.get("friendly") or pretty(names.get("native") or names.get("openrouter"))
        routes = "<br>".join(
            f"{route}: `{names[route]}`" for route in ("native", "openrouter", "chatgpt") if route in names
        )
        aliases = ", ".join(f"`{a}`" for a in r["aliases"][:6])
        flag_only = [a for a in r["dynamic"] if a not in r["aliases"]]
        if flag_only:
            aliases += ("; " if aliases else "") + "flag-only: " + ", ".join(f"`{a}`" for a in flag_only)
        notes = []
        if r["explicit_only"]:
            notes.append("explicit-only")
        if r["provisional"]:
            notes.append("provisional score")
        effort = fmt_effort(r["effort"]) if r["effort"] else "not measured"
        lines.append(f"| {title} | {r['score']} | {effort} | {routes} | {aliases} | {', '.join(notes)} |")
    lines.append("")

OUT.write_text("\n".join(lines))
print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} models")
