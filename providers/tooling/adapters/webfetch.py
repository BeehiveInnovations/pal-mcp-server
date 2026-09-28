"""webfetch adapter — HTTP GET with denylist for private ranges + auth passthrough."""

from __future__ import annotations

import ipaddress
import socket

from providers.tooling.toolbelt import ToolSpec, get_toolbelt


def _is_private(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(socket.gethostbyname(host))
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except (OSError, ValueError):
        return True  # unresolveable = block


def _get(args: dict) -> str:
    import urllib.request

    url = args.get("url", "")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "error: only http(s) URLs allowed"
    if _is_private(parsed.hostname or ""):
        return f"error: host {parsed.hostname} is private / non-routable"
    req = urllib.request.Request(url, headers={"User-Agent": "pal-mcp/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(20_000).decode("utf-8", errors="replace")
        return body + f"\n[status={resp.status}]"
    except Exception as exc:
        return f"error: {exc}"


get_toolbelt().register(
    ToolSpec(
        name="web_fetch",
        description="HTTP GET a public URL. Blocks private/link-local IPs. Returns first 20 KB.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        handler=_get,
        sandbox="readonly",
    )
)
