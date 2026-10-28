"""Unified `pal` command-line entry point.

Ties the previously-scattered invocations into one CLI:

    pal serve              # launch the MCP server (same as pal-mcp-server)
    pal diag [--json]      # dump smart-router + learning state
    pal distill [args...]  # run the offline routing-proposal distiller
    pal models [args...]   # capability-aware model catalog (--provider/--refresh/--json)

Registered as the `pal` console script in pyproject.toml. After a
`pip install -e .` in the venv, `pal` is on PATH; until then it also runs as
`python cli.py <subcommand>`.
"""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_serve(_args: argparse.Namespace) -> int:
    from server import run

    run()
    return 0


def _cmd_chat(_args: argparse.Namespace) -> int:
    from providers.router import chat_repl

    return chat_repl.run()


def _cmd_diag(args: argparse.Namespace) -> int:
    from providers.router import diag

    data = diag.collect()
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True, default=str))
    else:
        print(diag.render(data))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pal",
        description="PAL smart-router control CLI.",
        epilog="`pal distill ...` forwards all following args to the distiller "
        "(e.g. `pal distill --print-only --min-samples 10`).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("serve", help="launch the MCP server").set_defaults(func=_cmd_serve)

    sub.add_parser(
        "chat", help="interactive chat: auto cheap/smart routing, /debate, /delegate"
    ).set_defaults(func=_cmd_chat)

    d = sub.add_parser("diag", help="dump router + learning state")
    d.add_argument("--json", action="store_true", help="machine-readable output")
    d.set_defaults(func=_cmd_diag)

    # documented here for `pal -h`; their args are forwarded verbatim in main()
    sub.add_parser("distill", help="run the offline routing-proposal distiller (args forwarded)")
    sub.add_parser("models", help="capability-aware model catalog [--provider X] [--refresh] [--json] [--all]")
    sub.add_parser("debate", help="executor->reviewers->judge pipeline (args forwarded)")
    sub.add_parser("run", help="headless: run a task or --plan and print the result (args forwarded)")
    sub.add_parser("mission", help='writer->executor->judge pipeline: pal mission "<goal>" (args forwarded)')

    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    # passthrough subcommands: forward everything after them to their own
    # argparse untouched, avoiding argparse.REMAINDER's leading-flag quirk.
    if argv and argv[0] == "distill":
        from providers.router import distill

        return distill.main(argv[1:])
    if argv and argv[0] == "models":
        from providers.router import catalog_cli

        return catalog_cli.main(argv[1:])
    if argv and argv[0] == "debate":
        from providers.router import debate

        return debate.main(argv[1:])
    if argv and argv[0] == "run":
        from providers.router import headless

        return headless.main(argv[1:])
    if argv and argv[0] == "mission":
        from providers.router import mission

        return mission.main(argv[1:])
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
