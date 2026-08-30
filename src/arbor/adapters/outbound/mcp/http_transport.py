"""HTTP JSON-RPC client for external MCP servers with optional in-process fallback."""

from __future__ import annotations

import json
from typing import Any

import httpx

from arbor.adapters.outbound.mcp.jsonrpc_transport import McpJsonRpcTransport


class McpHttpJsonRpcTransport:
    """POST JSON-RPC to a remote MCP endpoint; fall back to local adapter when unreachable."""

    def __init__(
        self,
        base_url: str,
        *,
        fallback_adapter=None,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._fallback = (
            McpJsonRpcTransport(fallback_adapter) if fallback_adapter is not None else None
        )

    def call(self, method: str, params: dict | None = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": method,
            "params": params or {},
        }
        try:
            response = httpx.post(self.base_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
            if "error" in body:
                raise RuntimeError(str(body["error"]))
            return body.get("result")
        except (httpx.HTTPError, OSError, json.JSONDecodeError, RuntimeError, ValueError):
            if self._fallback is not None:
                return self._fallback.call(method, params)
            raise
