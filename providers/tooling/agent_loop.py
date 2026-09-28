"""ReAct-style agentic tool-calling loop for providers without native function-calling.

When the toolbelt is enabled (env ``PAL_TOOLBELT``), the model is handed a text
schema describing available local tools and is expected to emit exactly one
``<tool_call>{"name": "...", "args": {...}}</tool_call>`` block per turn. This loop
parses that block, executes the tool via the toolbelt, appends a ``<tool_result>``
block, and re-prompts until the model answers without a tool call or ``max_iters``
is hit. When disabled it is a zero-overhead passthrough to ``generate_content``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from providers.shared.model_response import ModelResponse
from providers.tooling.toolbelt import get_toolbelt, is_enabled

logger = logging.getLogger(__name__)

# Capture the inner payload of the FIRST tool_call block. Non-greedy on the tags,
# but we grab everything between them (not a brace pattern) so nested braces in the
# JSON args survive; json.loads does the real validation.
_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)
_STRAY_TAG_RE = re.compile(r"</?tool_(?:call|result)>", re.DOTALL)


def _accumulate_usage(base: dict[str, Any] | None, add: dict[str, Any] | None) -> dict[str, Any]:
    """Merge usage dicts by summing numeric fields; latest wins for non-numeric."""
    merged: dict[str, Any] = dict(base or {})
    for key, value in (add or {}).items():
        if isinstance(value, (int, float)) and isinstance(merged.get(key), (int, float)):
            merged[key] = merged[key] + value
        elif isinstance(value, (int, float)):
            merged[key] = merged.get(key, 0) + value
        else:
            merged[key] = value
    return merged


def _strip_stray_tags(text: str) -> str:
    return _STRAY_TAG_RE.sub("", text or "").strip()


def _run_native_fc(
    provider: Any,
    *,
    prompt: str,
    model_name: str,
    system_prompt: str | None,
    temperature: float,
    tools: list,
    max_iters: int,
    max_tool_output: int,
) -> ModelResponse:
    """Native function-calling loop using provider.chat_with_tools (OpenAI-style)."""
    from providers.shared.provider_type import ProviderType

    toolbelt = get_toolbelt()
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    total_usage: dict[str, Any] = {}
    tool_calls_made = 0
    last_content = ""
    provider_type = getattr(provider, "get_provider_type", lambda: ProviderType.OPENAI)()
    friendly = getattr(provider, "FRIENDLY_NAME", "")

    for _iter in range(1, max_iters + 1):
        turn = provider.chat_with_tools(
            messages=messages,
            tools=tools,
            model_name=model_name,
            temperature=temperature,
            tool_choice="auto",
        )
        total_usage = _accumulate_usage(total_usage, turn.get("usage"))
        calls = turn.get("tool_calls") or []
        last_content = turn.get("content") or last_content

        if not calls:
            return ModelResponse(
                content=turn.get("content") or "",
                usage=total_usage,
                model_name=model_name,
                friendly_name=friendly,
                provider=provider_type,
                metadata={
                    "finish_reason": turn.get("finish_reason"),
                    "toolbelt_used": True,
                    "toolbelt_calls": tool_calls_made,
                    "toolbelt_truncated": False,
                    "toolbelt_mode": "native_fc",
                },
            )

        # Echo the assistant turn (with its tool_calls) then answer each tool.
        messages.append(
            {
                "role": "assistant",
                "content": turn.get("content") or None,
                "tool_calls": [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c["arguments"]},
                    }
                    for c in calls
                ],
            }
        )
        for c in calls:
            name = c.get("name")
            raw_args = c.get("arguments")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                if not isinstance(args, dict):
                    args = {}
            except (json.JSONDecodeError, TypeError):
                args = {}
            logger.info("toolbelt(native) call: %s args=%.120s", name, json.dumps(args, ensure_ascii=False))
            result = toolbelt.execute(name, args, caller_model=model_name)
            if len(result) > max_tool_output:
                result = result[:max_tool_output] + "\n...[truncated]"
            tool_calls_made += 1
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})

    # iteration cap hit
    return ModelResponse(
        content=last_content,
        usage=total_usage,
        model_name=model_name,
        friendly_name=friendly,
        provider=provider_type,
        metadata={
            "toolbelt_used": True,
            "toolbelt_calls": tool_calls_made,
            "toolbelt_truncated": True,
            "toolbelt_iters": max_iters,
            "toolbelt_mode": "native_fc",
        },
    )


def run_agentic(
    provider: Any,
    *,
    prompt: str,
    model_name: str,
    system_prompt: str | None = None,
    temperature: float = 0.3,
    gen_kwargs: dict[str, Any] | None = None,
    max_iters: int = 8,
    max_tool_output: int = 8000,
) -> ModelResponse:
    """Run a ReAct tool loop, or pass through to generate_content when disabled.

    Returns a ModelResponse whose ``content`` is the model's final answer. When the
    toolbelt was active, ``metadata`` carries ``toolbelt_used``/``toolbelt_calls`` and,
    if the iteration cap was hit, ``toolbelt_truncated``/``toolbelt_iters``.
    """
    gen_kwargs = gen_kwargs or {}

    def _once(p: str, sys_p: str | None) -> ModelResponse:
        return provider.generate_content(
            prompt=p,
            model_name=model_name,
            system_prompt=sys_p,
            temperature=temperature,
            **gen_kwargs,
        )

    # ---- fast path: toolbelt off or no tools enabled -> passthrough -------------
    toolbelt = get_toolbelt()
    if not is_enabled():
        return _once(prompt, system_prompt)

    # ---- native function-calling path (OpenAI/groq/xai/openrouter) --------------
    # Preferred when the provider exposes chat_with_tools: these models emit native
    # tool_calls and ignore the ReAct text convention.
    fc_tools = toolbelt.openai_schema(provider=model_name)
    if fc_tools and hasattr(provider, "chat_with_tools"):
        return _run_native_fc(
            provider,
            prompt=prompt,
            model_name=model_name,
            system_prompt=system_prompt,
            temperature=temperature,
            tools=fc_tools,
            max_iters=max_iters,
            max_tool_output=max_tool_output,
        )

    # ---- ReAct text-protocol fallback (models without native FC) ----------------
    schema = toolbelt.react_schema(provider=model_name)
    if not schema:
        return _once(prompt, system_prompt)

    augmented_system = f"{system_prompt.rstrip()}\n\n{schema}" if system_prompt else schema

    conversation = prompt
    total_usage: dict[str, Any] = {}
    tool_calls = 0
    last: ModelResponse | None = None

    for _iter in range(1, max_iters + 1):
        resp = _once(conversation, augmented_system)
        last = resp
        total_usage = _accumulate_usage(total_usage, getattr(resp, "usage", None))

        match = _TOOL_CALL_RE.search(resp.content or "")
        if not match:
            # terminal turn -> final answer
            return ModelResponse(
                content=_strip_stray_tags(resp.content or ""),
                usage=total_usage,
                model_name=resp.model_name,
                friendly_name=resp.friendly_name,
                provider=resp.provider,
                metadata={
                    **(resp.metadata or {}),
                    "toolbelt_used": True,
                    "toolbelt_calls": tool_calls,
                    "toolbelt_truncated": False,
                },
            )

        raw_block = match.group(0)
        payload = match.group(1)
        try:
            spec = json.loads(payload)
            name = spec.get("name")
            args = spec.get("args")
            if args is None:
                args = spec.get("arguments")
            if not isinstance(args, dict):
                args = {}
            if not name:
                raise ValueError("tool_call missing 'name'")
        except (json.JSONDecodeError, ValueError, AttributeError) as exc:
            logger.warning("malformed tool_call (iter %d): %s", _iter, exc)
            conversation += (
                f"\n{raw_block}\n<tool_result>\n"
                f"error: could not parse tool_call JSON: {exc}. "
                f'Emit exactly one <tool_call>{{"name":"...","args":{{...}}}}</tool_call>.'
                f"\n</tool_result>\n"
            )
            continue

        logger.info("toolbelt call: %s args=%.120s", name, json.dumps(args, ensure_ascii=False))
        try:
            result = toolbelt.execute(name, args, caller_model=model_name)
        except Exception as exc:  # defensive; execute already catches internally
            result = f"error: {exc.__class__.__name__}: {exc}"
        if len(result) > max_tool_output:
            result = result[:max_tool_output] + "\n...[truncated]"
        tool_calls += 1
        conversation += f"\n{raw_block}\n<tool_result>\n{result}\n</tool_result>\n"

    # ---- iteration cap reached -------------------------------------------------
    base = last or ModelResponse(content="", model_name=model_name)
    return ModelResponse(
        content=_strip_stray_tags(base.content or ""),
        usage=total_usage,
        model_name=base.model_name,
        friendly_name=base.friendly_name,
        provider=base.provider,
        metadata={
            **(base.metadata or {}),
            "toolbelt_used": True,
            "toolbelt_calls": tool_calls,
            "toolbelt_truncated": True,
            "toolbelt_iters": max_iters,
        },
    )
