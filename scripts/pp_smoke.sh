#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing virtualenv interpreter at ${PYTHON_BIN}" >&2
  echo "Create it first (example: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)." >&2
  exit 1
fi

if [[ -z "${PP_SMOKE_DB:-}" ]]; then
  tmp_base="$(mktemp /tmp/pp_smoke.XXXXXX)"
  export PP_SMOKE_DB="${tmp_base}.sqlite"
  rm -f "${tmp_base}"
fi
export PP_SMOKE_API_KEY="${PP_SMOKE_API_KEY:-pp_test_tenant_key_1}"
export PP_SMOKE_TENANT="${PP_SMOKE_TENANT:-tenant_smoke}"
export PP_SMOKE_DAILY_LIMIT_CENTS="${PP_SMOKE_DAILY_LIMIT_CENTS:-8}"

echo "Running PP transport smoke with:"
echo "  PP_SMOKE_DB=${PP_SMOKE_DB}"
echo "  PP_SMOKE_API_KEY=${PP_SMOKE_API_KEY}"
echo "  PP_SMOKE_TENANT=${PP_SMOKE_TENANT}"
echo "  PP_SMOKE_DAILY_LIMIT_CENTS=${PP_SMOKE_DAILY_LIMIT_CENTS}"

exec "${PYTHON_BIN}" "${REPO_ROOT}/scripts/pp_mcp_transport_smoke.py" --seed
