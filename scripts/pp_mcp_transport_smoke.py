#!/usr/bin/env python3
"""MCP stdio transport smoke for PP tools with defensive result parsing."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import uuid
from hashlib import sha256
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "scripts" / "pp_schema.sql"
DEFAULT_DB_PATH = Path(os.environ.get("PP_SMOKE_DB", "/tmp/pp_smoke.sqlite"))
DEFAULT_API_KEY = os.environ.get("PP_SMOKE_API_KEY", "pp_test_tenant_key_1")
DEFAULT_TENANT_ID = os.environ.get("PP_SMOKE_TENANT", "tenant_smoke")


def _default_daily_limit_cents() -> int:
    raw_value = os.environ.get("PP_SMOKE_DAILY_LIMIT_CENTS", "8")
    try:
        return int(raw_value)
    except ValueError:
        return 8


DEFAULT_DAILY_LIMIT_CENTS = _default_daily_limit_cents()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PP MCP stdio transport smoke.")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Force-seed tenant/key/limits before running the smoke steps.",
    )
    parser.add_argument(
        "--daily-limit-cents",
        type=int,
        default=DEFAULT_DAILY_LIMIT_CENTS,
        help="Daily tenant budget used by seed logic (default: %(default)s).",
    )
    return parser.parse_args()


def _seed_smoke_db(db_path: Path, tenant_id: str, api_key: str, daily_limit_cents: int) -> None:
    if daily_limit_cents <= 0:
        raise RuntimeError(f"--daily-limit-cents must be > 0, got {daily_limit_cents}")
    if not SCHEMA_PATH.exists():
        raise RuntimeError(f"schema not found: {SCHEMA_PATH}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        api_key_sha = sha256(api_key.encode("utf-8")).hexdigest()

        conn.execute(
            "INSERT INTO tenants(tenant_id, name, status) VALUES (?, ?, 'active') "
            "ON CONFLICT(tenant_id) DO UPDATE SET name=excluded.name, status='active'",
            (tenant_id, f"Tenant {tenant_id}"),
        )
        conn.execute(
            "INSERT INTO api_keys(api_key_sha256, tenant_id, label, status) VALUES (?, ?, ?, 'active') "
            "ON CONFLICT(api_key_sha256) DO UPDATE SET tenant_id=excluded.tenant_id, label=excluded.label, status='active'",
            (api_key_sha, tenant_id, "smoke-key"),
        )
        conn.execute(
            """
            INSERT INTO usage_limits(
              tenant_id, daily_limit_cents, monthly_limit_cents,
              daily_spent_cents, monthly_spent_cents, daily_day, monthly_ym, updated_at
            ) VALUES (?, ?, 0, 0, 0, date('now'), strftime('%Y-%m','now'), datetime('now'))
            ON CONFLICT(tenant_id) DO UPDATE SET
              daily_limit_cents=excluded.daily_limit_cents,
              monthly_limit_cents=0,
              daily_spent_cents=0,
              monthly_spent_cents=0,
              daily_day=date('now'),
              monthly_ym=strftime('%Y-%m','now'),
              updated_at=datetime('now')
            """,
            (tenant_id, daily_limit_cents),
        )
        # Keep seeded runs deterministic.
        conn.execute("DELETE FROM ledger WHERE tenant_id=?", (tenant_id,))
        conn.execute("DELETE FROM pp_jobs WHERE tenant_id=?", (tenant_id,))
        conn.commit()
    finally:
        conn.close()


def _content_to_text(result: Any) -> str:
    """
    Convert MCP result content to a displayable text blob.

    CallToolResult.content is typically a list of TextContent items, but for
    schema/input validation failures this may be plain text that is not JSON.
    """
    parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        parts.append(text if isinstance(text, str) else str(item))
    return "\n".join(parts).strip()


def parse_tool_result(result: Any) -> tuple[dict[str, Any] | None, str, bool]:
    """
    Parse CallToolResult safely.

    Returns:
      - payload: decoded JSON dict when possible, else None
      - raw_text: joined raw content text
      - is_error: MCP-level isError flag
    """
    is_error = bool(getattr(result, "isError", False))
    raw_text = _content_to_text(result)

    if not raw_text:
        return None, "", is_error

    try:
        return json.loads(raw_text), raw_text, is_error
    except json.JSONDecodeError:
        return None, raw_text, is_error


async def _call_tool_json(session: ClientSession, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a tool and require ToolOutput JSON response."""
    result = await session.call_tool(name, arguments)
    payload, raw_text, is_error = parse_tool_result(result)

    # Some MCP servers return ToolExecutionError payloads as JSON text with isError=True.
    # Accept JSON payloads regardless of isError so callers can assert expected failures.
    if payload is not None:
        return payload

    if is_error:
        raise RuntimeError(f"{name} returned MCP error (non-JSON):\n{raw_text}")
    if payload is None:
        raise RuntimeError(f"{name} returned non-JSON text:\n{raw_text}")
    raise RuntimeError(f"{name} returned unexpected empty response")


def _must_success(payload: dict[str, Any], label: str) -> dict[str, Any]:
    if payload.get("status") != "success":
        raise RuntimeError(f"{label} expected success, got: {json.dumps(payload, indent=2)}")
    if payload.get("content_type") != "text":
        raise RuntimeError(f"{label} expected content_type=text, got: {payload.get('content_type')}")
    content = payload.get("content")
    if not isinstance(content, str):
        raise RuntimeError(f"{label} expected string content field, got: {type(content)}")
    return json.loads(content)


def _print_usage(db_path: Path, tenant_id: str) -> None:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT daily_limit_cents, daily_spent_cents, daily_day FROM usage_limits WHERE tenant_id=?",
        (tenant_id,),
    ).fetchone()
    conn.close()
    if row:
        print(
            "usage:",
            {
                "daily_limit_cents": row[0],
                "daily_spent_cents": row[1],
                "daily_day": row[2],
            },
        )


async def main() -> None:
    args = _parse_args()
    run_id = uuid.uuid4().hex[:8]
    db_path = Path(os.environ.get("PP_SMOKE_DB", str(DEFAULT_DB_PATH))).expanduser()
    api_key = os.environ.get("PP_SMOKE_API_KEY", DEFAULT_API_KEY)
    tenant_id = os.environ.get("PP_SMOKE_TENANT", DEFAULT_TENANT_ID)

    auto_seed = not db_path.exists()
    if args.seed or auto_seed:
        _seed_smoke_db(db_path=db_path, tenant_id=tenant_id, api_key=api_key, daily_limit_cents=args.daily_limit_cents)
        print(
            "seed:",
            {
                "mode": "forced" if args.seed else "auto-missing-db",
                "db_path": str(db_path),
                "tenant_id": tenant_id,
                "daily_limit_cents": args.daily_limit_cents,
            },
        )
    print(
        "env:",
        {
            "PP_SMOKE_DB": str(db_path),
            "PP_SMOKE_API_KEY": api_key,
            "PP_SMOKE_TENANT": tenant_id,
            "PP_SMOKE_DAILY_LIMIT_CENTS": args.daily_limit_cents,
        },
    )

    params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        cwd=REPO_ROOT,
        env=dict(os.environ),
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            required = [
                "pp_tenant_whoami",
                "pp_prepare",
                "pp_quote",
                "pp_submit",
                "pp_admin_setlimit",
            ]
            for name in required:
                if name not in names:
                    raise RuntimeError(f"missing tool: {name}")

            common = {"api_key": api_key, "db_path": str(db_path)}

            who_payload = await _call_tool_json(session, "pp_tenant_whoami", {**common, "request_id": f"who-{run_id}"})
            whoami = _must_success(who_payload, "whoami")
            print("whoami:", whoami)

            prepare_payload = await _call_tool_json(
                session,
                "pp_prepare",
                {
                    **common,
                    "request_id": f"prep-{run_id}",
                    "kind": "proof_pack",
                    "input": {"customer_text": "hello"},
                    "raw_body": '{"customer_text":"hello"}',
                },
            )
            prepared = _must_success(prepare_payload, "prepare")
            job_id = prepared["job_id"]
            print("prepare:", {"job_id": job_id, "prepare_id_deprecated": prepared.get("prepare_id_deprecated")})

            quote_1 = await _call_tool_json(
                session, "pp_quote", {**common, "request_id": f"quote-1-{run_id}", "job_id": job_id}
            )
            _must_success(quote_1, "quote-1")
            print("quote-1 ok")

            quote_1_replay = await _call_tool_json(
                session, "pp_quote", {**common, "request_id": f"quote-1-{run_id}", "job_id": job_id}
            )
            _must_success(quote_1_replay, "quote-1-replay")
            if quote_1_replay.get("metadata", {}).get("idempotent_replay") is not True:
                raise RuntimeError("quote-1-replay missing metadata.idempotent_replay=true")
            print("quote-1 replay ok")

            quote_2 = await _call_tool_json(
                session, "pp_quote", {**common, "request_id": f"quote-2-{run_id}", "job_id": job_id}
            )
            if quote_2.get("status") != "error":
                raise RuntimeError(f"quote-2 expected error, got: {json.dumps(quote_2, indent=2)}")
            metadata = quote_2.get("metadata", {})
            if metadata.get("http_status") != 429 or metadata.get("code") != "LIMIT_EXCEEDED":
                raise RuntimeError(f"quote-2 expected 429/LIMIT_EXCEEDED, got: {metadata}")
            print("quote-2 rejected:", metadata.get("code"), metadata.get("http_status"))

    _print_usage(db_path, tenant_id)
    print("OK: transport smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
