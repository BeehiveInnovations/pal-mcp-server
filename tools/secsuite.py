"""
Security Suite Tool (secsuite) - Burp Suite alternative capabilities in PAL MCP Server

Provides HTTP request sending/repeater, SQLite traffic logging & FTS5 search,
JWT analysis & attacks, response comparison/diffing, and race condition testing.
"""

from __future__ import annotations

import base64
import concurrent.futures
import difflib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

import jwt
import requests
from pydantic import Field

from tools.models import ToolModelCategory
from tools.shared.base_models import ToolRequest
from tools.simple.base import SimpleTool

DB_PATH = Path.home() / ".pal" / "traffic.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            method TEXT,
            url TEXT,
            status_code INTEGER,
            request_headers TEXT,
            request_body TEXT,
            response_headers TEXT,
            response_body TEXT
        )
    """)
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS traffic_fts USING fts5(
            url, request_headers, request_body, response_headers, response_body
        )
    """)
    conn.commit()
    conn.close()


def log_traffic(method: str, url: str, status_code: int, req_headers: dict, req_body: str, resp_headers: dict, resp_body: str):
    try:
        init_db()
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        ts = time.time()
        rh_str = json.dumps(req_headers)
        rph_str = json.dumps(resp_headers)
        cursor.execute(
            "INSERT INTO traffic (timestamp, method, url, status_code, request_headers, request_body, response_headers, response_body) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, method, url, status_code, rh_str, req_body or "", rph_str, resp_body or "")
        )
        row_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO traffic_fts(rowid, url, request_headers, request_body, response_headers, response_body) VALUES (?, ?, ?, ?, ?, ?)",
            (row_id, url, rh_str, req_body or "", rph_str, resp_body or "")
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


class SecSuiteRequest(ToolRequest):
    action: str = Field(..., description="Action to perform: 'http_send', 'search_traffic', 'jwt_decode', 'jwt_forge', 'jwt_none_attack', 'compare_responses', 'send_parallel'")
    url: Optional[str] = Field(None, description="Target URL for HTTP requests or GraphQL")
    method: Optional[str] = Field("GET", description="HTTP method (GET, POST, PUT, DELETE, etc.)")
    headers: Optional[dict[str, str]] = Field(default_factory=dict, description="HTTP headers")
    body: Optional[str] = Field(None, description="HTTP request body / payload")
    query: Optional[str] = Field(None, description="Search query for traffic search")
    token: Optional[str] = Field(None, description="JWT token for JWT operations")
    secret: Optional[str] = Field(None, description="JWT secret for signing/forging")
    algorithm: Optional[str] = Field("HS256", description="JWT algorithm (HS256, RS256, none)")
    claims: Optional[dict[str, Any]] = Field(default_factory=dict, description="JWT claims for forging")
    text1: Optional[str] = Field(None, description="First text for response comparison")
    text2: Optional[str] = Field(None, description="Second text for response comparison")
    count: Optional[int] = Field(10, description="Number of parallel requests for race condition testing")


class SecSuiteTool(SimpleTool):
    """Security Suite Tool providing Burp Suite alternative capabilities (HTTP, JWT, Traffic Logging, Race Testing)."""

    def get_name(self) -> str:
        return "secsuite"

    def get_description(self) -> str:
        return (
            "Performs advanced security testing tasks: sends HTTP requests and logs traffic to SQLite with FTS5 search, "
            "analyzes/forges JWT tokens, compares HTTP responses, and tests race conditions with parallel requests."
        )

    def get_system_prompt(self) -> str:
        return ""

    def get_default_temperature(self) -> float:
        return 0.1

    def requires_model(self) -> bool:
        return False

    def get_model_category(self) -> ToolModelCategory:
        return ToolModelCategory.FAST_RESPONSE

    def get_request_model(self):
        return SecSuiteRequest

    async def prepare_prompt(self, request) -> str:
        return ""

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        return {
            "action": {"type": "string", "description": "Action to perform ('http_send', 'search_traffic', 'jwt_decode', 'jwt_forge', 'jwt_none_attack', 'compare_responses', 'send_parallel')"},
            "url": {"type": "string", "description": "Target URL"},
            "method": {"type": "string", "description": "HTTP method"},
            "headers": {"type": "object", "description": "HTTP headers"},
            "body": {"type": "string", "description": "Request body"},
            "query": {"type": "string", "description": "Search query"},
            "token": {"type": "string", "description": "JWT token"},
            "secret": {"type": "string", "description": "JWT secret"},
            "algorithm": {"type": "string", "description": "JWT algorithm"},
            "claims": {"type": "object", "description": "JWT claims"},
            "text1": {"type": "string", "description": "First text"},
            "text2": {"type": "string", "description": "Second text"},
            "count": {"type": "integer", "description": "Parallel request count"},
        }

    async def execute(self, arguments: dict[str, Any]) -> list:
        from mcp.types import TextContent

        req = self.get_request_model()(**arguments)
        result: dict[str, Any] = {"action": req.action}

        try:
            if req.action == "http_send":
                if not req.url:
                    raise ValueError("URL is required for http_send")
                headers = req.headers or {}
                resp = requests.request(req.method or "GET", req.url, headers=headers, data=req.body, timeout=30, verify=False)
                resp_headers = dict(resp.headers)
                log_traffic(req.method or "GET", req.url, resp.status_code, headers, req.body or "", resp_headers, resp.text)
                result["status_code"] = resp.status_code
                result["headers"] = resp_headers
                result["body"] = resp.text[:10000] # truncate if too large

            elif req.action == "search_traffic":
                init_db()
                conn = sqlite3.connect(str(DB_PATH))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if req.query:
                    cursor.execute("SELECT t.* FROM traffic t JOIN traffic_fts f ON t.id = f.rowid WHERE traffic_fts MATCH ? ORDER BY t.timestamp DESC LIMIT 50", (req.query,))
                else:
                    cursor.execute("SELECT * FROM traffic ORDER BY timestamp DESC LIMIT 50")
                rows = [dict(row) for row in cursor.fetchall()]
                conn.close()
                result["results"] = rows

            elif req.action == "jwt_decode":
                if not req.token:
                    raise ValueError("Token is required for jwt_decode")
                # Decode without verification first
                header = jwt.get_unverified_header(req.token)
                payload = jwt.decode(req.token, options={"verify_signature": False})
                result["header"] = header
                result["payload"] = payload

            elif req.action == "jwt_forge":
                if not req.claims:
                    raise ValueError("Claims are required for jwt_forge")
                secret = req.secret or "secret"
                algorithm = req.algorithm or "HS256"
                encoded = jwt.encode(req.claims, secret, algorithm=algorithm)
                result["token"] = encoded

            elif req.action == "jwt_none_attack":
                if not req.token and not req.claims:
                    raise ValueError("Token or claims required for jwt_none_attack")
                claims = req.claims
                if not claims and req.token:
                    claims = jwt.decode(req.token, options={"verify_signature": False})
                # Create token with alg none and no signature
                header = {"typ": "JWT", "alg": "none"}
                # Manually construct base64url encoded parts
                def b64url(data: bytes) -> str:
                    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")
                h_b64 = b64url(json.dumps(header).encode("utf-8"))
                p_b64 = b64url(json.dumps(claims).encode("utf-8"))
                forged = f"{h_b64}.{p_b64}."
                result["token"] = forged

            elif req.action == "compare_responses":
                if req.text1 is None or req.text2 is None:
                    raise ValueError("text1 and text2 are required for compare_responses")
                diff = list(difflib.unified_diff(
                    req.text1.splitlines(),
                    req.text2.splitlines(),
                    fromfile="Response 1",
                    tofile="Response 2",
                    lineterm=""
                ))
                result["diff"] = "\n".join(diff)

            elif req.action == "send_parallel":
                if not req.url:
                    raise ValueError("URL is required for send_parallel")
                count = req.count or 10
                headers = req.headers or {}
                method = req.method or "GET"
                body = req.body

                def send_one():
                    start = time.time()
                    try:
                        r = requests.request(method, req.url, headers=headers, data=body, timeout=15, verify=False)
                        return {"status_code": r.status_code, "time": time.time() - start, "length": len(r.text)}
                    except Exception as ex:
                        return {"error": str(ex), "time": time.time() - start}

                with concurrent.futures.ThreadPoolExecutor(max_workers=count) as executor:
                    futures = [executor.submit(send_one) for _ in range(count)]
                    results = [f.result() for f in futures]
                result["parallel_results"] = results

            else:
                raise ValueError(f"Unknown action: {req.action}")

        except Exception as e:
            result["error"] = str(e)

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
