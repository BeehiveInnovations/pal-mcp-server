"""Tests for ProofPack MCP utility tools."""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from tools.pp import PP_SCHEMA_SQL, PPPrepareTool, PPQuoteTool, PPSubmitTool
from tools.shared.exceptions import ToolExecutionError


def _create_tenant(db_path: Path, tenant_id: str, api_key: str, daily_limit_cents: int) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(PP_SCHEMA_SQL)

    api_key_sha = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    conn.execute(
        "INSERT INTO tenants(tenant_id, name, status) VALUES (?, ?, 'active')",
        (tenant_id, f"Tenant {tenant_id}"),
    )
    conn.execute(
        "INSERT INTO api_keys(api_key_sha256, tenant_id, label, status) VALUES (?, ?, ?, 'active')",
        (api_key_sha, tenant_id, "test-key"),
    )
    conn.execute(
        """
        INSERT INTO usage_limits(
          tenant_id, daily_limit_cents, monthly_limit_cents,
          daily_spent_cents, monthly_spent_cents, daily_day, monthly_ym, updated_at
        ) VALUES (?, ?, 0, 0, 0, date('now'), strftime('%Y-%m','now'), datetime('now'))
        """,
        (tenant_id, daily_limit_cents),
    )

    conn.commit()
    conn.close()


def _create_legacy_db_with_old_ledger_unique(
    db_path: Path, tenant_id: str, api_key: str, daily_limit_cents: int
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE tenants (
          tenant_id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE api_keys (
          api_key_sha256 TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          label TEXT,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          last_used_at TEXT
        );

        CREATE TABLE usage_limits (
          tenant_id TEXT PRIMARY KEY,
          daily_limit_cents INTEGER NOT NULL DEFAULT 0,
          monthly_limit_cents INTEGER NOT NULL DEFAULT 0,
          daily_spent_cents INTEGER NOT NULL DEFAULT 0,
          monthly_spent_cents INTEGER NOT NULL DEFAULT 0,
          daily_day TEXT NOT NULL DEFAULT (date('now')),
          monthly_ym TEXT NOT NULL DEFAULT (strftime('%Y-%m','now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Legacy shape with unique(tenant_id, request_id)
        CREATE TABLE ledger (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL DEFAULT (datetime('now')),
          tenant_id TEXT NOT NULL,
          tool_name TEXT NOT NULL,
          request_id TEXT NOT NULL,
          api_key_sha256 TEXT NOT NULL,
          est_cost_cents INTEGER NOT NULL,
          est_input_bytes INTEGER NOT NULL,
          est_output_bytes_budget INTEGER NOT NULL,
          status TEXT NOT NULL,
          reason TEXT,
          UNIQUE(tenant_id, request_id)
        );
        """
    )

    api_key_sha = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO tenants(tenant_id, name, status) VALUES (?, ?, 'active')",
        (tenant_id, f"Tenant {tenant_id}"),
    )
    conn.execute(
        "INSERT INTO api_keys(api_key_sha256, tenant_id, label, status) VALUES (?, ?, ?, 'active')",
        (api_key_sha, tenant_id, "legacy-key"),
    )
    conn.execute(
        """
        INSERT INTO usage_limits(
          tenant_id, daily_limit_cents, monthly_limit_cents,
          daily_spent_cents, monthly_spent_cents, daily_day, monthly_ym, updated_at
        ) VALUES (?, ?, 0, 0, 0, date('now'), strftime('%Y-%m','now'), datetime('now'))
        """,
        (tenant_id, daily_limit_cents),
    )
    conn.commit()
    conn.close()


def _create_job(db_path: Path, tenant_id: str, job_id: str, payload: str = "{}") -> None:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(PP_SCHEMA_SQL)
    payload_bytes = payload.encode("utf-8")
    payload_sha = hashlib.sha256(payload_bytes).hexdigest()
    conn.execute(
        """
        INSERT INTO pp_jobs(tenant_id, job_id, payload_sha256, payload_bytes, status)
        VALUES (?, ?, ?, ?, 'prepared')
        """,
        (tenant_id, job_id, payload_sha, len(payload_bytes)),
    )
    conn.commit()
    conn.close()


@pytest.mark.asyncio
async def test_pp_prepare_returns_job_id_and_persists_job(tmp_path: Path) -> None:
    db_path = tmp_path / "pp.sqlite"
    tenant_id = "tenant_prepare"
    api_key = "pp_prepare_key"
    _create_tenant(db_path, tenant_id, api_key, daily_limit_cents=100)

    tool = PPPrepareTool()
    result = await tool.execute(
        {
            "db_path": str(db_path),
            "api_key": api_key,
            "request_id": "req_prepare_1",
            "kind": "proof_pack",
            "input": {"customer_text": "hello"},
            "raw_body": '{"customer_text":"hello"}',
        }
    )

    payload = json.loads(result[0].text)
    content = json.loads(payload["content"])

    assert payload["status"] == "success"
    assert payload["metadata"]["tool_name"] == "pp_prepare"
    assert content["job_id"].startswith("job_")
    assert content["prepare_id"] == content["job_id"]
    assert content["prepare_id_deprecated"] is True

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT payload_sha256, payload_bytes, status FROM pp_jobs WHERE tenant_id=? AND job_id=?",
        (tenant_id, content["job_id"]),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0]
    assert int(row[1]) > 0
    assert row[2] == "prepared"


@pytest.mark.asyncio
async def test_pp_quote_precharge_success(tmp_path: Path) -> None:
    db_path = tmp_path / "pp.sqlite"
    tenant_id = "tenant_success"
    api_key = "pp_success_key"
    _create_tenant(db_path, tenant_id, api_key, daily_limit_cents=100)
    _create_job(db_path, tenant_id, "job_123")

    tool = PPQuoteTool()
    result = await tool.execute(
        {
            "db_path": str(db_path),
            "api_key": api_key,
            "request_id": "req_quote_1",
            "job_id": "job_123",
        }
    )

    payload = json.loads(result[0].text)
    assert payload["status"] == "success"
    assert payload["metadata"]["tool_name"] == "pp_quote"

    content = json.loads(payload["content"])
    assert content["job_id"] == "job_123"
    assert content["quote"]["amount_cents"] == 750000

    conn = sqlite3.connect(str(db_path))
    spent = conn.execute(
        "SELECT daily_spent_cents FROM usage_limits WHERE tenant_id=?",
        (tenant_id,),
    ).fetchone()[0]
    conn.close()
    assert spent == 2


@pytest.mark.asyncio
async def test_pp_submit_precharge_limit_exceeded_returns_429(tmp_path: Path) -> None:
    db_path = tmp_path / "pp.sqlite"
    tenant_id = "tenant_limited"
    api_key = "pp_limited_key"
    _create_tenant(db_path, tenant_id, api_key, daily_limit_cents=10)
    _create_job(db_path, tenant_id, "job_abc")

    tool = PPSubmitTool()
    with pytest.raises(ToolExecutionError) as exc_info:
        await tool.execute(
            {
                "db_path": str(db_path),
                "api_key": api_key,
                "request_id": "req_submit_1",
                "job_id": "job_abc",
            }
        )

    payload = json.loads(exc_info.value.payload)
    assert payload["status"] == "error"
    assert payload["metadata"]["code"] == "LIMIT_EXCEEDED"
    assert payload["metadata"]["http_status"] == 429

    conn = sqlite3.connect(str(db_path))
    spent = conn.execute(
        "SELECT daily_spent_cents FROM usage_limits WHERE tenant_id=?",
        (tenant_id,),
    ).fetchone()[0]
    conn.close()
    assert spent == 0


@pytest.mark.asyncio
async def test_pp_quote_idempotent_request_charges_once(tmp_path: Path) -> None:
    db_path = tmp_path / "pp.sqlite"
    tenant_id = "tenant_idempotent"
    api_key = "pp_idempotent_key"
    _create_tenant(db_path, tenant_id, api_key, daily_limit_cents=100)
    _create_job(db_path, tenant_id, "job_one")

    tool = PPQuoteTool()

    first = await tool.execute(
        {
            "db_path": str(db_path),
            "api_key": api_key,
            "request_id": "req_same",
            "job_id": "job_one",
        }
    )
    second = await tool.execute(
        {
            "db_path": str(db_path),
            "api_key": api_key,
            "request_id": "req_same",
            "job_id": "job_one",
        }
    )

    first_payload = json.loads(first[0].text)
    second_payload = json.loads(second[0].text)

    assert first_payload["status"] == "success"
    assert second_payload["status"] == "success"
    assert second_payload["metadata"]["idempotent_replay"] is True

    conn = sqlite3.connect(str(db_path))
    spent = conn.execute(
        "SELECT daily_spent_cents FROM usage_limits WHERE tenant_id=?",
        (tenant_id,),
    ).fetchone()[0]
    conn.close()
    assert spent == 2


@pytest.mark.asyncio
async def test_same_request_id_different_tools_do_not_collide(tmp_path: Path) -> None:
    db_path = tmp_path / "pp.sqlite"
    tenant_id = "tenant_cross_tool"
    api_key = "pp_cross_tool_key"
    _create_tenant(db_path, tenant_id, api_key, daily_limit_cents=100)
    _create_job(db_path, tenant_id, "job_q")
    _create_job(db_path, tenant_id, "job_s")

    quote_tool = PPQuoteTool()
    submit_tool = PPSubmitTool()

    await quote_tool.execute(
        {
            "db_path": str(db_path),
            "api_key": api_key,
            "request_id": "req_shared",
            "job_id": "job_q",
        }
    )
    await submit_tool.execute(
        {
            "db_path": str(db_path),
            "api_key": api_key,
            "request_id": "req_shared",
            "job_id": "job_s",
        }
    )

    conn = sqlite3.connect(str(db_path))
    spent = conn.execute(
        "SELECT daily_spent_cents FROM usage_limits WHERE tenant_id=?",
        (tenant_id,),
    ).fetchone()[0]
    conn.close()

    # quote=2 cents + submit=25 cents
    assert spent == 27


@pytest.mark.asyncio
async def test_legacy_ledger_schema_is_migrated_before_precharge(tmp_path: Path) -> None:
    db_path = tmp_path / "pp_legacy.sqlite"
    tenant_id = "tenant_legacy"
    api_key = "pp_legacy_key"
    _create_legacy_db_with_old_ledger_unique(db_path, tenant_id, api_key, daily_limit_cents=100)
    _create_job(db_path, tenant_id, "job_legacy_q")
    _create_job(db_path, tenant_id, "job_legacy_s")

    quote_tool = PPQuoteTool()
    submit_tool = PPSubmitTool()

    await quote_tool.execute(
        {
            "db_path": str(db_path),
            "api_key": api_key,
            "request_id": "req_legacy",
            "job_id": "job_legacy_q",
        }
    )
    await submit_tool.execute(
        {
            "db_path": str(db_path),
            "api_key": api_key,
            "request_id": "req_legacy",
            "job_id": "job_legacy_s",
        }
    )

    conn = sqlite3.connect(str(db_path))
    # quote=2 cents + submit=25 cents
    spent = conn.execute(
        "SELECT daily_spent_cents FROM usage_limits WHERE tenant_id=?",
        (tenant_id,),
    ).fetchone()[0]

    # Ensure migrated unique index exists
    idx_rows = conn.execute("PRAGMA index_list('ledger')").fetchall()
    found_target = False
    for _seq, idx_name, is_unique, *_rest in idx_rows:
        if int(is_unique) != 1:
            continue
        cols = [row[2] for row in conn.execute(f"PRAGMA index_info('{idx_name}')").fetchall()]
        if cols == ["tenant_id", "tool_name", "request_id"]:
            found_target = True
            break
    conn.close()

    assert spent == 27
    assert found_target is True


@pytest.mark.asyncio
async def test_pp_quote_rejects_unknown_job_id(tmp_path: Path) -> None:
    db_path = tmp_path / "pp.sqlite"
    tenant_id = "tenant_unknown_job"
    api_key = "pp_unknown_job_key"
    _create_tenant(db_path, tenant_id, api_key, daily_limit_cents=100)

    tool = PPQuoteTool()
    with pytest.raises(ToolExecutionError) as exc_info:
        await tool.execute(
            {
                "db_path": str(db_path),
                "api_key": api_key,
                "request_id": "req_quote_unknown",
                "job_id": "job_missing",
            }
        )

    payload = json.loads(exc_info.value.payload)
    assert payload["metadata"]["code"] == "JOB_NOT_FOUND"
    assert payload["metadata"]["http_status"] == 404


@pytest.mark.asyncio
async def test_pp_quote_rejects_other_tenant_job_id(tmp_path: Path) -> None:
    db_path = tmp_path / "pp.sqlite"
    tenant_a = "tenant_a"
    tenant_b = "tenant_b"
    api_key_a = "pp_tenant_a_key"
    api_key_b = "pp_tenant_b_key"
    _create_tenant(db_path, tenant_a, api_key_a, daily_limit_cents=100)
    _create_tenant(db_path, tenant_b, api_key_b, daily_limit_cents=100)
    _create_job(db_path, tenant_a, "job_a_only")

    tool = PPQuoteTool()
    with pytest.raises(ToolExecutionError) as exc_info:
        await tool.execute(
            {
                "db_path": str(db_path),
                "api_key": api_key_b,
                "request_id": "req_cross_tenant",
                "job_id": "job_a_only",
            }
        )

    payload = json.loads(exc_info.value.payload)
    assert payload["metadata"]["code"] == "JOB_NOT_FOUND"
    assert payload["metadata"]["http_status"] == 404

    conn = sqlite3.connect(str(db_path))
    spent = conn.execute(
        "SELECT daily_spent_cents FROM usage_limits WHERE tenant_id=?",
        (tenant_b,),
    ).fetchone()[0]
    conn.close()
    assert spent == 0
