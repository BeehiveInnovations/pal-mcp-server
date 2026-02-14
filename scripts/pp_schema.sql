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

CREATE TABLE IF NOT EXISTS pp_quotes (
  quote_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  job_id TEXT NOT NULL,
  request_id TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  currency TEXT NOT NULL,
  base_cents INTEGER NOT NULL,
  processing_cents INTEGER NOT NULL,
  quote_signature TEXT NOT NULL,
  issued_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'consumed')),
  consumed_request_id TEXT,
  consumed_at TEXT,
  UNIQUE(tenant_id, request_id),
  FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, job_id) REFERENCES pp_jobs(tenant_id, job_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pp_quotes_tenant_job ON pp_quotes(tenant_id, job_id, status);

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
  request_ip TEXT,
  user_agent TEXT,
  status TEXT NOT NULL,
  reason TEXT,
  UNIQUE(tenant_id, tool_name, request_id),
  FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ledger_tenant_ts ON ledger(tenant_id, ts);
CREATE INDEX IF NOT EXISTS idx_ledger_tool_ts ON ledger(tool_name, ts);
