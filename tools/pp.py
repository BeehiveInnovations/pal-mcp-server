"""ProofPack (Part B) MCP utility tools with SQLite-backed hard gating."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Optional

from mcp.types import TextContent

from tools.models import ToolModelCategory, ToolOutput
from tools.shared.base_models import ToolRequest
from tools.shared.base_tool import BaseTool
from tools.shared.exceptions import ToolExecutionError
from utils.env import get_env

logger = logging.getLogger(__name__)

PP_TOOL_KEYS = {
    "pp_tenant_whoami",
    "pp_prepare",
    "pp_quote",
    "pp_submit",
    "pp_admin_setlimit",
}

PP_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tenants (
  tenant_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'suspended')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS api_keys (
  api_key_sha256 TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  label TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'revoked')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_used_at TEXT,
  FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status);

CREATE TABLE IF NOT EXISTS usage_limits (
  tenant_id TEXT PRIMARY KEY,
  daily_limit_cents INTEGER NOT NULL DEFAULT 0,
  monthly_limit_cents INTEGER NOT NULL DEFAULT 0,
  daily_spent_cents INTEGER NOT NULL DEFAULT 0,
  monthly_spent_cents INTEGER NOT NULL DEFAULT 0,
  daily_day TEXT NOT NULL DEFAULT (date('now')),
  monthly_ym TEXT NOT NULL DEFAULT (strftime('%Y-%m','now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pp_jobs (
  tenant_id TEXT NOT NULL,
  job_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  payload_sha256 TEXT NOT NULL,
  payload_bytes INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'prepared',
  PRIMARY KEY (tenant_id, job_id),
  FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pp_jobs_tenant_created
ON pp_jobs(tenant_id, created_at);

CREATE TABLE IF NOT EXISTS ledger (
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
  UNIQUE(tenant_id, tool_name, request_id),
  FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ledger_tenant_ts ON ledger(tenant_id, ts);
CREATE INDEX IF NOT EXISTS idx_ledger_tool_ts ON ledger(tool_name, ts);
"""


@dataclass(frozen=True)
class TenantCtx:
    tenant_id: str
    tenant_name: str
    api_key_sha256: str


@dataclass(frozen=True)
class Budget:
    est_input_bytes: int
    est_output_bytes_budget: int
    est_cost_cents: int


@dataclass(frozen=True)
class PrechargeResult:
    status: str
    reason: Optional[str]
    daily_limit_cents: int
    daily_spent_cents: int
    idempotent_replay: bool = False


class PPDomainError(Exception):
    """Domain-level validation/auth errors mapped to ToolExecutionError payloads."""

    def __init__(self, code: str, message: str, http_status: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _json_compact(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _ledger_request_id(tool_name: str, request_id: str) -> str:
    """Scope request IDs by tool for backward compatibility with older schemas."""
    return f"{tool_name}:{request_id}"


def _ledger_has_target_unique_constraint(conn: sqlite3.Connection) -> bool:
    """Check whether ledger already has unique (tenant_id, tool_name, request_id)."""
    for index in conn.execute("PRAGMA index_list('ledger')").fetchall():
        # index tuple: seq, name, unique, origin, partial
        if int(index[2]) != 1:
            continue
        index_name = index[1]
        cols = [row[2] for row in conn.execute(f"PRAGMA index_info('{index_name}')").fetchall()]
        if cols == ["tenant_id", "tool_name", "request_id"]:
            return True
    return False


def _migrate_legacy_ledger_if_needed(conn: sqlite3.Connection) -> None:
    """
    Migrate legacy ledger schema to include unique (tenant_id, tool_name, request_id).

    This preserves older databases that used unique (tenant_id, request_id), which causes
    cross-tool collisions when request_id values are reused across PP tools.
    """
    table_info = conn.execute("PRAGMA table_info('ledger')").fetchall()
    if not table_info:
        return

    existing_cols = {str(row[1]) for row in table_info}
    if "tool_name" not in existing_cols:
        needs_migration = True
    else:
        needs_migration = not _ledger_has_target_unique_constraint(conn)

    if not needs_migration:
        return

    logger.info("Migrating legacy pp ledger schema to scoped idempotency format")

    conn.execute("BEGIN IMMEDIATE;")
    try:
        conn.execute("ALTER TABLE ledger RENAME TO ledger_old_pp_mig;")
        conn.execute(
            """
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
              UNIQUE(tenant_id, tool_name, request_id),
              FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_tenant_ts ON ledger(tenant_id, ts);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_tool_ts ON ledger(tool_name, ts);")

        old_cols = {str(row[1]) for row in conn.execute("PRAGMA table_info('ledger_old_pp_mig')").fetchall()}
        has_old_tool_name = "tool_name" in old_cols

        if has_old_tool_name:
            old_rows = conn.execute(
                """
                SELECT id, ts, tenant_id, tool_name, request_id, api_key_sha256,
                       est_cost_cents, est_input_bytes, est_output_bytes_budget,
                       status, reason
                FROM ledger_old_pp_mig
                ORDER BY id ASC
                """
            ).fetchall()
        else:
            old_rows = conn.execute(
                """
                SELECT id, ts, tenant_id, request_id, api_key_sha256,
                       est_cost_cents, est_input_bytes, est_output_bytes_budget,
                       status, reason
                FROM ledger_old_pp_mig
                ORDER BY id ASC
                """
            ).fetchall()

        for row in old_rows:
            if has_old_tool_name:
                old_tool_name = str(row["tool_name"] or "").strip()
                request_id = str(row["request_id"] or "")
            else:
                old_tool_name = ""
                request_id = str(row["request_id"] or "")

            # Infer tool_name from legacy prefixed request IDs (e.g. "pp_quote:req_1")
            tool_name = old_tool_name
            if not tool_name and ":" in request_id:
                prefix, _, _rest = request_id.partition(":")
                if prefix in PP_TOOL_KEYS:
                    tool_name = prefix

            conn.execute(
                """
                INSERT OR IGNORE INTO ledger(
                  id, ts, tenant_id, tool_name, request_id, api_key_sha256,
                  est_cost_cents, est_input_bytes, est_output_bytes_budget,
                  status, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["id"]),
                    row["ts"],
                    row["tenant_id"],
                    tool_name,
                    request_id,
                    row["api_key_sha256"],
                    int(row["est_cost_cents"]),
                    int(row["est_input_bytes"]),
                    int(row["est_output_bytes_budget"]),
                    row["status"],
                    row["reason"],
                ),
            )

        conn.execute("DROP TABLE ledger_old_pp_mig;")
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise


def _sha256_hex(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _resolve_db_path(arguments: dict[str, Any]) -> Path:
    arg_path = arguments.get("db_path")
    default_path = get_env("PP_DB_PATH", "data/pp.sqlite") or "data/pp.sqlite"
    resolved = str(arg_path).strip() if isinstance(arg_path, str) and arg_path.strip() else default_path
    path = Path(resolved).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect_db(arguments: dict[str, Any]) -> sqlite3.Connection:
    db_path = _resolve_db_path(arguments)
    conn = sqlite3.connect(str(db_path), timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=FULL;")
    conn.executescript(PP_SCHEMA_SQL)
    _migrate_legacy_ledger_if_needed(conn)
    return conn


def _error_payload(
    tool_name: str,
    code: str,
    message: str,
    http_status: int,
    meta: Optional[dict[str, Any]] = None,
) -> str:
    metadata: dict[str, Any] = {"tool_name": tool_name, "code": code, "http_status": http_status}
    if meta:
        metadata.update(meta)
    output = ToolOutput(status="error", content=message, content_type="text", metadata=metadata)
    return output.model_dump_json()


def _raise_tool_error(
    tool_name: str,
    code: str,
    message: str,
    http_status: int,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    raise ToolExecutionError(_error_payload(tool_name, code, message, http_status, meta))


def _ok_payload(
    tool_name: str,
    content_obj: dict[str, Any],
    meta: Optional[dict[str, Any]] = None,
) -> list[TextContent]:
    metadata = {"tool_name": tool_name}
    if meta:
        metadata.update(meta)

    output = ToolOutput(
        status="success",
        content=_json_compact(content_obj),
        content_type="text",
        metadata=metadata,
    )
    return [TextContent(type="text", text=output.model_dump_json())]


def _require_api_key(arguments: dict[str, Any]) -> str:
    api_key = arguments.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise PPDomainError("KEY_MISSING", "Missing api_key", 401)
    return api_key.strip()


def _require_request_id(arguments: dict[str, Any]) -> str:
    request_id = arguments.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise PPDomainError("REQUEST_ID_MISSING", "Missing request_id", 400)
    return request_id.strip()


def _resolve_tenant(conn: sqlite3.Connection, arguments: dict[str, Any]) -> TenantCtx:
    api_key = _require_api_key(arguments)
    key_hash = _sha256_hex(api_key)

    key_row = conn.execute(
        "SELECT tenant_id, status FROM api_keys WHERE api_key_sha256=?",
        (key_hash,),
    ).fetchone()
    if not key_row or key_row["status"] != "active":
        raise PPDomainError("FORBIDDEN", "Invalid or inactive API key", 403)

    tenant_row = conn.execute(
        "SELECT tenant_id, name, status FROM tenants WHERE tenant_id=?",
        (key_row["tenant_id"],),
    ).fetchone()
    if not tenant_row:
        raise PPDomainError("FORBIDDEN", "Tenant not found for API key", 403)
    if tenant_row["status"] != "active":
        raise PPDomainError("TENANT_SUSPENDED", "Tenant is suspended", 403)

    conn.execute(
        "UPDATE api_keys SET last_used_at=datetime('now') WHERE api_key_sha256=?",
        (key_hash,),
    )

    return TenantCtx(
        tenant_id=str(tenant_row["tenant_id"]),
        tenant_name=str(tenant_row["name"]),
        api_key_sha256=key_hash,
    )


def _insert_ledger(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    tool_name: str,
    request_id: str,
    api_key_sha256: str,
    est_cost_cents: int,
    est_input_bytes: int,
    est_output_bytes_budget: int,
    status: str,
    reason: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT INTO ledger(
          tenant_id, tool_name, request_id, api_key_sha256,
          est_cost_cents, est_input_bytes, est_output_bytes_budget,
          status, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tenant_id,
            tool_name,
            request_id,
            api_key_sha256,
            int(est_cost_cents),
            int(est_input_bytes),
            int(est_output_bytes_budget),
            status,
            reason,
        ),
    )


def _load_usage_row(conn: sqlite3.Connection, tenant_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT daily_day, daily_limit_cents, daily_spent_cents FROM usage_limits WHERE tenant_id=?",
        (tenant_id,),
    ).fetchone()


def _insert_prepared_job(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    job_id: str,
    payload_sha256: str,
    payload_bytes: int,
) -> None:
    conn.execute(
        """
        INSERT INTO pp_jobs(
          tenant_id, job_id, payload_sha256, payload_bytes, status
        ) VALUES (?, ?, ?, ?, 'prepared')
        """,
        (tenant_id, job_id, payload_sha256, int(payload_bytes)),
    )


def _require_tenant_job(conn: sqlite3.Connection, *, tenant_id: str, job_id: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT tenant_id, job_id, payload_sha256, payload_bytes, status
        FROM pp_jobs
        WHERE tenant_id=? AND job_id=?
        """,
        (tenant_id, job_id),
    ).fetchone()
    if not row:
        raise PPDomainError("JOB_NOT_FOUND", "job_id not found for tenant", 404)
    return row


def _atomic_precharge_daily_only(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    api_key_sha256: str,
    tool_name: str,
    request_id: str,
    budget: Budget,
) -> PrechargeResult:
    if not request_id:
        raise PPDomainError("REQUEST_ID_MISSING", "Missing request_id", 400)
    if budget.est_cost_cents < 0:
        raise PPDomainError("BAD_REQUEST", "est_cost_cents must be >= 0", 400)

    scoped_request_id = _ledger_request_id(tool_name, request_id)

    conn.execute("BEGIN IMMEDIATE;")
    try:
        existing = conn.execute(
            "SELECT status, reason FROM ledger WHERE tenant_id=? AND tool_name=? AND request_id=?",
            (tenant_id, tool_name, scoped_request_id),
        ).fetchone()
        if existing:
            usage = _load_usage_row(conn, tenant_id)
            conn.execute("COMMIT;")
            return PrechargeResult(
                status=str(existing["status"]),
                reason=existing["reason"],
                daily_limit_cents=int(usage["daily_limit_cents"]) if usage else 0,
                daily_spent_cents=int(usage["daily_spent_cents"]) if usage else 0,
                idempotent_replay=True,
            )

        usage = _load_usage_row(conn, tenant_id)
        if not usage:
            _insert_ledger(
                conn,
                tenant_id=tenant_id,
                tool_name=tool_name,
                request_id=scoped_request_id,
                api_key_sha256=api_key_sha256,
                est_cost_cents=budget.est_cost_cents,
                est_input_bytes=budget.est_input_bytes,
                est_output_bytes_budget=budget.est_output_bytes_budget,
                status="rejected",
                reason="NO_LIMITS_ROW",
            )
            conn.execute("COMMIT;")
            return PrechargeResult(status="rejected", reason="NO_LIMITS_ROW", daily_limit_cents=0, daily_spent_cents=0)

        conn.execute(
            """
            UPDATE usage_limits
            SET daily_day = date('now'),
                daily_spent_cents = 0,
                updated_at = datetime('now')
            WHERE tenant_id = ?
              AND daily_day <> date('now')
            """,
            (tenant_id,),
        )

        usage = conn.execute(
            "SELECT daily_limit_cents, daily_spent_cents FROM usage_limits WHERE tenant_id=?",
            (tenant_id,),
        ).fetchone()
        daily_limit = int(usage["daily_limit_cents"])
        daily_spent = int(usage["daily_spent_cents"])

        if daily_limit <= 0:
            _insert_ledger(
                conn,
                tenant_id=tenant_id,
                tool_name=tool_name,
                request_id=scoped_request_id,
                api_key_sha256=api_key_sha256,
                est_cost_cents=budget.est_cost_cents,
                est_input_bytes=budget.est_input_bytes,
                est_output_bytes_budget=budget.est_output_bytes_budget,
                status="rejected",
                reason="LIMIT_DISABLED",
            )
            conn.execute("COMMIT;")
            return PrechargeResult(
                status="rejected",
                reason="LIMIT_DISABLED",
                daily_limit_cents=daily_limit,
                daily_spent_cents=daily_spent,
            )

        if daily_spent + budget.est_cost_cents > daily_limit:
            _insert_ledger(
                conn,
                tenant_id=tenant_id,
                tool_name=tool_name,
                request_id=scoped_request_id,
                api_key_sha256=api_key_sha256,
                est_cost_cents=budget.est_cost_cents,
                est_input_bytes=budget.est_input_bytes,
                est_output_bytes_budget=budget.est_output_bytes_budget,
                status="rejected",
                reason="LIMIT_EXCEEDED",
            )
            conn.execute("COMMIT;")
            return PrechargeResult(
                status="rejected",
                reason="LIMIT_EXCEEDED",
                daily_limit_cents=daily_limit,
                daily_spent_cents=daily_spent,
            )

        _insert_ledger(
            conn,
            tenant_id=tenant_id,
            tool_name=tool_name,
            request_id=scoped_request_id,
            api_key_sha256=api_key_sha256,
            est_cost_cents=budget.est_cost_cents,
            est_input_bytes=budget.est_input_bytes,
            est_output_bytes_budget=budget.est_output_bytes_budget,
            status="precharged",
            reason=None,
        )

        conn.execute(
            """
            UPDATE usage_limits
            SET daily_spent_cents = daily_spent_cents + ?,
                updated_at = datetime('now')
            WHERE tenant_id = ?
            """,
            (budget.est_cost_cents, tenant_id),
        )

        usage = conn.execute(
            "SELECT daily_limit_cents, daily_spent_cents FROM usage_limits WHERE tenant_id=?",
            (tenant_id,),
        ).fetchone()

        conn.execute("COMMIT;")
        return PrechargeResult(
            status="precharged",
            reason=None,
            daily_limit_cents=int(usage["daily_limit_cents"]),
            daily_spent_cents=int(usage["daily_spent_cents"]),
        )
    except Exception:
        conn.execute("ROLLBACK;")
        raise


def _enforce_precharge(tool_name: str, request_id: str, result: PrechargeResult) -> None:
    if result.status == "precharged":
        return

    if result.reason in {"LIMIT_EXCEEDED", "LIMIT_DISABLED", "NO_LIMITS_ROW"}:
        _raise_tool_error(
            tool_name,
            "LIMIT_EXCEEDED",
            "Daily limit exceeded",
            429,
            {
                "request_id": request_id,
                "reason": result.reason,
                "daily_spent_cents": result.daily_spent_cents,
                "daily_limit_cents": result.daily_limit_cents,
            },
        )

    _raise_tool_error(
        tool_name,
        "FORBIDDEN",
        "Request rejected",
        403,
        {
            "request_id": request_id,
            "reason": result.reason,
        },
    )


def _to_non_negative_int(value: Any, field_name: str) -> int:
    try:
        int_value = int(value)
    except (TypeError, ValueError) as exc:
        raise PPDomainError("BAD_REQUEST", f"{field_name} must be an integer", 400) from exc

    if int_value < 0:
        raise PPDomainError("BAD_REQUEST", f"{field_name} must be >= 0", 400)
    return int_value


def _prepare_input_bytes(arguments: dict[str, Any]) -> int:
    payload_bytes = _prepare_payload_bytes(arguments)
    return len(payload_bytes)


def _prepare_payload_bytes(arguments: dict[str, Any]) -> bytes:
    if isinstance(arguments.get("raw_body"), str):
        payload_bytes = arguments["raw_body"].encode("utf-8")
    else:
        payload = {
            "kind": arguments.get("kind"),
            "input": arguments.get("input", {}),
        }
        try:
            payload_bytes = _json_compact(payload).encode("utf-8")
        except TypeError as exc:
            raise PPDomainError("BAD_REQUEST", "input payload is not JSON serializable", 400) from exc

    size = len(payload_bytes)
    if size > 5_000_000:
        raise PPDomainError("PAYLOAD_TOO_LARGE", "Payload exceeds 5_000_000 bytes", 413)
    return payload_bytes


def _daily_usage_snapshot(conn: sqlite3.Connection, tenant_id: str) -> dict[str, Any]:
    conn.execute(
        """
        UPDATE usage_limits
        SET daily_day = date('now'),
            daily_spent_cents = 0,
            updated_at = datetime('now')
        WHERE tenant_id = ?
          AND daily_day <> date('now')
        """,
        (tenant_id,),
    )
    row = conn.execute(
        "SELECT daily_day, daily_limit_cents, daily_spent_cents FROM usage_limits WHERE tenant_id=?",
        (tenant_id,),
    ).fetchone()
    if not row:
        return {
            "daily_day": None,
            "daily_limit_cents": 0,
            "daily_spent_cents": 0,
            "daily_remaining_cents": 0,
        }

    remaining = max(0, int(row["daily_limit_cents"]) - int(row["daily_spent_cents"]))
    return {
        "daily_day": row["daily_day"],
        "daily_limit_cents": int(row["daily_limit_cents"]),
        "daily_spent_cents": int(row["daily_spent_cents"]),
        "daily_remaining_cents": remaining,
    }


class PPBaseTool(BaseTool):
    """Shared behavior for ProofPack utility tools."""

    def get_system_prompt(self) -> str:
        return ""

    def get_request_model(self):
        return ToolRequest

    def requires_model(self) -> bool:
        return False

    async def prepare_prompt(self, request: ToolRequest) -> str:
        return ""

    def format_response(self, response: str, request: ToolRequest, model_info: Optional[dict] = None) -> str:
        return response

    def get_model_category(self) -> ToolModelCategory:
        return ToolModelCategory.FAST_RESPONSE

    def get_annotations(self) -> Optional[dict[str, Any]]:
        return {"readOnlyHint": False}


class PPTenantWhoamiTool(PPBaseTool):
    def get_name(self) -> str:
        return "pp_tenant_whoami"

    def get_description(self) -> str:
        return "Resolve tenant identity and current daily budget/usage for the provided api_key."

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Tenant API key for PP tools."},
                "request_id": {"type": "string", "description": "Optional idempotency key."},
            },
            "required": ["api_key"],
            "additionalProperties": False,
        }

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        conn: Optional[sqlite3.Connection] = None
        request_id = arguments.get("request_id") if isinstance(arguments.get("request_id"), str) else None
        try:
            conn = _connect_db(arguments)
            tenant = _resolve_tenant(conn, arguments)

            effective_request_id = request_id.strip() if request_id and request_id.strip() else f"whoami:{uuid.uuid4()}"
            result = _atomic_precharge_daily_only(
                conn,
                tenant_id=tenant.tenant_id,
                api_key_sha256=tenant.api_key_sha256,
                tool_name=self.name,
                request_id=effective_request_id,
                budget=Budget(est_input_bytes=1024, est_output_bytes_budget=4096, est_cost_cents=1),
            )
            _enforce_precharge(self.name, effective_request_id, result)

            usage = _daily_usage_snapshot(conn, tenant.tenant_id)
            return _ok_payload(
                self.name,
                {
                    "tenant": {
                        "tenant_id": tenant.tenant_id,
                        "name": tenant.tenant_name,
                        "status": "active",
                    },
                    "usage_today": usage,
                },
                {
                    "request_id": effective_request_id,
                    "idempotent_replay": result.idempotent_replay,
                },
            )
        except PPDomainError as exc:
            _raise_tool_error(self.name, exc.code, exc.message, exc.http_status)
        except ToolExecutionError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in %s", self.name)
            _raise_tool_error(self.name, "INTERNAL_ERROR", str(exc), 500)
        finally:
            if conn:
                conn.close()


class PPPrepareTool(PPBaseTool):
    def get_name(self) -> str:
        return "pp_prepare"

    def get_description(self) -> str:
        return "Validate and prepare a ProofPack job envelope with hard daily precharge enforcement."

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Tenant API key for PP tools."},
                "request_id": {"type": "string", "description": "Idempotency key for prepare."},
                "kind": {"type": "string", "description": "Work kind; expected value is proof_pack."},
                "input": {"type": "object", "description": "Structured payload for preparation."},
                "raw_body": {"type": "string", "description": "Optional raw payload string used for byte accounting."},
            },
            "required": ["api_key", "request_id"],
            "additionalProperties": False,
        }

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = _connect_db(arguments)
            tenant = _resolve_tenant(conn, arguments)
            request_id = _require_request_id(arguments)

            payload_bytes = _prepare_payload_bytes(arguments)
            payload_size = len(payload_bytes)
            result = _atomic_precharge_daily_only(
                conn,
                tenant_id=tenant.tenant_id,
                api_key_sha256=tenant.api_key_sha256,
                tool_name=self.name,
                request_id=request_id,
                budget=Budget(est_input_bytes=payload_size, est_output_bytes_budget=8192, est_cost_cents=5),
            )
            _enforce_precharge(self.name, request_id, result)

            job_id = f"job_{uuid.uuid4().hex}"
            payload_sha256 = sha256(payload_bytes).hexdigest()
            _insert_prepared_job(
                conn,
                tenant_id=tenant.tenant_id,
                job_id=job_id,
                payload_sha256=payload_sha256,
                payload_bytes=payload_size,
            )
            return _ok_payload(
                self.name,
                {
                    "job_id": job_id,
                    "prepare_id": job_id,
                    "prepare_id_deprecated": True,
                    "status": "prepared",
                    "kind": arguments.get("kind", "proof_pack"),
                    "payload_sha256": payload_sha256,
                    "payload_bytes": payload_size,
                    "input_bytes": payload_size,
                },
                {
                    "request_id": request_id,
                    "idempotent_replay": result.idempotent_replay,
                    "daily_spent_cents": result.daily_spent_cents,
                    "daily_limit_cents": result.daily_limit_cents,
                },
            )
        except PPDomainError as exc:
            _raise_tool_error(self.name, exc.code, exc.message, exc.http_status)
        except ToolExecutionError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in %s", self.name)
            _raise_tool_error(self.name, "INTERNAL_ERROR", str(exc), 500)
        finally:
            if conn:
                conn.close()


class PPQuoteTool(PPBaseTool):
    def get_name(self) -> str:
        return "pp_quote"

    def get_description(self) -> str:
        return "Return a deterministic quote for a prepared ProofPack job with hard daily precharge."

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Tenant API key for PP tools."},
                "request_id": {"type": "string", "description": "Idempotency key for quote."},
                "job_id": {"type": "string", "description": "Prepared job identifier."},
            },
            "required": ["api_key", "request_id", "job_id"],
            "additionalProperties": False,
        }

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = _connect_db(arguments)
            tenant = _resolve_tenant(conn, arguments)
            request_id = _require_request_id(arguments)

            job_id = arguments.get("job_id")
            if not isinstance(job_id, str) or not job_id.strip():
                raise PPDomainError("BAD_REQUEST", "job_id is required", 400)
            normalized_job_id = job_id.strip()
            _require_tenant_job(conn, tenant_id=tenant.tenant_id, job_id=normalized_job_id)

            result = _atomic_precharge_daily_only(
                conn,
                tenant_id=tenant.tenant_id,
                api_key_sha256=tenant.api_key_sha256,
                tool_name=self.name,
                request_id=request_id,
                budget=Budget(est_input_bytes=2048, est_output_bytes_budget=4096, est_cost_cents=2),
            )
            _enforce_precharge(self.name, request_id, result)

            return _ok_payload(
                self.name,
                {
                    "job_id": normalized_job_id,
                    "quote": {
                        "currency": "USD",
                        "amount_cents": 750000,
                        "type": "fixed",
                    },
                    "can_submit": True,
                },
                {
                    "request_id": request_id,
                    "idempotent_replay": result.idempotent_replay,
                    "daily_spent_cents": result.daily_spent_cents,
                    "daily_limit_cents": result.daily_limit_cents,
                },
            )
        except PPDomainError as exc:
            _raise_tool_error(self.name, exc.code, exc.message, exc.http_status)
        except ToolExecutionError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in %s", self.name)
            _raise_tool_error(self.name, "INTERNAL_ERROR", str(exc), 500)
        finally:
            if conn:
                conn.close()


class PPSubmitTool(PPBaseTool):
    def get_name(self) -> str:
        return "pp_submit"

    def get_description(self) -> str:
        return "Submit a prepared ProofPack job with hard daily precharge and idempotency enforcement."

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Tenant API key for PP tools."},
                "request_id": {"type": "string", "description": "Idempotency key for submit."},
                "job_id": {"type": "string", "description": "Prepared job identifier."},
            },
            "required": ["api_key", "request_id", "job_id"],
            "additionalProperties": False,
        }

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = _connect_db(arguments)
            tenant = _resolve_tenant(conn, arguments)
            request_id = _require_request_id(arguments)

            job_id = arguments.get("job_id")
            if not isinstance(job_id, str) or not job_id.strip():
                raise PPDomainError("BAD_REQUEST", "job_id is required", 400)
            normalized_job_id = job_id.strip()
            _require_tenant_job(conn, tenant_id=tenant.tenant_id, job_id=normalized_job_id)

            result = _atomic_precharge_daily_only(
                conn,
                tenant_id=tenant.tenant_id,
                api_key_sha256=tenant.api_key_sha256,
                tool_name=self.name,
                request_id=request_id,
                budget=Budget(est_input_bytes=2048, est_output_bytes_budget=16384, est_cost_cents=25),
            )
            _enforce_precharge(self.name, request_id, result)

            submit_id = f"sub_{uuid.uuid4().hex}"
            conn.execute(
                "UPDATE pp_jobs SET status='submitted' WHERE tenant_id=? AND job_id=?",
                (tenant.tenant_id, normalized_job_id),
            )
            return _ok_payload(
                self.name,
                {
                    "job_id": normalized_job_id,
                    "submit_id": submit_id,
                    "status": "submitted",
                    "tracking": {"state": "queued"},
                },
                {
                    "request_id": request_id,
                    "idempotent_replay": result.idempotent_replay,
                    "daily_spent_cents": result.daily_spent_cents,
                    "daily_limit_cents": result.daily_limit_cents,
                },
            )
        except PPDomainError as exc:
            _raise_tool_error(self.name, exc.code, exc.message, exc.http_status)
        except ToolExecutionError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in %s", self.name)
            _raise_tool_error(self.name, "INTERNAL_ERROR", str(exc), 500)
        finally:
            if conn:
                conn.close()


class PPAdminSetLimitTool(PPBaseTool):
    def get_name(self) -> str:
        return "pp_admin_setlimit"

    def get_description(self) -> str:
        return "Admin-only limit management for tenant daily ProofPack budgets."

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "description": "Admin tenant API key."},
                "request_id": {"type": "string", "description": "Idempotency key for admin writes."},
                "target_tenant_id": {"type": "string", "description": "Tenant whose daily limit will be set."},
                "daily_limit_cents": {"type": "integer", "minimum": 0, "description": "New daily limit in cents."},
            },
            "required": ["api_key", "request_id", "target_tenant_id", "daily_limit_cents"],
            "additionalProperties": False,
        }

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = _connect_db(arguments)
            tenant = _resolve_tenant(conn, arguments)
            request_id = _require_request_id(arguments)
            target_tenant_id = arguments.get("target_tenant_id")
            if not isinstance(target_tenant_id, str) or not target_tenant_id.strip():
                raise PPDomainError("BAD_REQUEST", "target_tenant_id is required", 400)

            daily_limit_cents = _to_non_negative_int(arguments.get("daily_limit_cents"), "daily_limit_cents")

            if tenant.tenant_id != "admin":
                raise PPDomainError("FORBIDDEN", "Admin tenant required", 403)

            target_exists = conn.execute(
                "SELECT tenant_id FROM tenants WHERE tenant_id=?",
                (target_tenant_id.strip(),),
            ).fetchone()
            if not target_exists:
                raise PPDomainError("TENANT_NOT_FOUND", "Target tenant does not exist", 404)

            result = _atomic_precharge_daily_only(
                conn,
                tenant_id=tenant.tenant_id,
                api_key_sha256=tenant.api_key_sha256,
                tool_name=self.name,
                request_id=request_id,
                budget=Budget(est_input_bytes=4096, est_output_bytes_budget=2048, est_cost_cents=1),
            )
            _enforce_precharge(self.name, request_id, result)

            conn.execute(
                """
                INSERT INTO usage_limits(
                  tenant_id, daily_limit_cents, monthly_limit_cents,
                  daily_spent_cents, monthly_spent_cents, daily_day, monthly_ym, updated_at
                )
                VALUES (?, ?, 0, 0, 0, date('now'), strftime('%Y-%m','now'), datetime('now'))
                ON CONFLICT(tenant_id) DO UPDATE SET
                  daily_limit_cents = excluded.daily_limit_cents,
                  updated_at = datetime('now')
                """,
                (target_tenant_id.strip(), daily_limit_cents),
            )

            return _ok_payload(
                self.name,
                {
                    "ok": True,
                    "tenant_id": target_tenant_id.strip(),
                    "daily_limit_cents": daily_limit_cents,
                },
                {
                    "request_id": request_id,
                    "idempotent_replay": result.idempotent_replay,
                    "daily_spent_cents": result.daily_spent_cents,
                    "daily_limit_cents": result.daily_limit_cents,
                },
            )
        except PPDomainError as exc:
            _raise_tool_error(self.name, exc.code, exc.message, exc.http_status)
        except ToolExecutionError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in %s", self.name)
            _raise_tool_error(self.name, "INTERNAL_ERROR", str(exc), 500)
        finally:
            if conn:
                conn.close()
