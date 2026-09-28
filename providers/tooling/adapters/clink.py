"""clink adapter for the toolbelt.

Lets an LLM (mid ReAct-loop) delegate a self-contained subtask to a full agent CLI
(e.g. gemini, codex, claude) that has its own shell/file/browser tools, and returns
the CLI's final text answer. Imports defensively so the module loads even when clink
is unavailable, and guards against runaway nesting via PAL_CLINK_DEPTH.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
from typing import Any

from providers.tooling.toolbelt import ToolSpec, get_toolbelt

log = logging.getLogger(__name__)

try:
    from clink import get_registry
    from clink.agents import CLIAgentError, create_agent

    _CLINK_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    _CLINK_AVAILABLE = False
    log.warning("clink not importable; clink adapter disabled: %s", exc)


def _run_coro(coro: Any) -> Any:
    """Run *coro* in a fresh event loop on a worker thread.

    The toolbelt handler is sync but is invoked from inside the server's running
    event loop, where bare asyncio.run() would raise. A dedicated thread gets a
    clean loop of its own.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(lambda: asyncio.run(coro)).result()


def _run(args: dict[str, Any]) -> str:
    if not _CLINK_AVAILABLE:
        return "error: clink integration not available"

    try:
        cli_name = str(args["cli_name"])
        prompt = str(args["prompt"])
    except KeyError as e:
        return f"error: missing required argument {e.args[0]}"
    role = str(args.get("role", "default"))

    # recursion guard
    try:
        depth = int(os.getenv("PAL_CLINK_DEPTH", "0"))
    except ValueError:
        depth = 0
    if depth >= 1:
        return "error: clink nesting depth exceeded (recursion guard)"

    log.info("clink delegate cli=%s prompt=%.100s", cli_name, prompt)

    registry = get_registry()
    clients = registry.list_clients()
    if cli_name not in clients:
        return f"error: unknown cli '{cli_name}'; available: {', '.join(sorted(clients))}"

    original_depth = os.environ.get("PAL_CLINK_DEPTH")
    os.environ["PAL_CLINK_DEPTH"] = str(depth + 1)
    try:
        client = registry.get_client(cli_name)
        try:
            role_cfg = client.get_role(role)
        except KeyError:
            return f"error: unknown role '{role}' for cli '{cli_name}'"

        agent = create_agent(client)

        async def _go():
            return await agent.run(role=role_cfg, prompt=prompt, system_prompt=None, files=[], images=[])

        result = _run_coro(_go())
        text = getattr(result.parsed, "content", None) or getattr(result, "stdout", "") or ""
        if len(text) > 12_000:
            text = text[:12_000] + "\n...[clink output truncated]"
        return text
    except KeyError as e:
        return f"error: {e}"
    except CLIAgentError as e:
        return f"error: {e}"
    except Exception as e:  # pragma: no cover
        return f"error: {e.__class__.__name__}: {e}"
    finally:
        if original_depth is None:
            os.environ.pop("PAL_CLINK_DEPTH", None)
        else:
            os.environ["PAL_CLINK_DEPTH"] = original_depth


if _CLINK_AVAILABLE:
    get_toolbelt().register(
        ToolSpec(
            name="clink",
            description=(
                "Delegate a self-contained subtask to a full agent CLI (e.g. gemini, codex, "
                "claude) that has its own shell/file/browser tools; returns the CLI's final "
                "text answer. Use for heavy autonomous work or browser tasks."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "cli_name": {"type": "string", "description": "A configured CLI client name"},
                    "prompt": {"type": "string", "description": "Full self-contained instruction for the sub-agent"},
                    "role": {"type": "string", "default": "default", "description": "Role name"},
                },
                "required": ["cli_name", "prompt"],
            },
            handler=_run,
            sandbox="readonly",
        )
    )
