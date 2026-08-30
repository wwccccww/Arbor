"""JSON-RPC transport stub for MCP tool discovery and invocation."""

from __future__ import annotations

import json
from typing import Any


class McpJsonRpcTransport:
    """Phase 8 stub — in-process JSON-RPC without external MCP server."""

    def __init__(self, adapter) -> None:
        self._adapter = adapter

    def handle(self, payload: dict | str) -> dict:
        request = json.loads(payload) if isinstance(payload, str) else dict(payload)
        method = str(request.get("method") or "")
        params = dict(request.get("params") or {})
        request_id = request.get("id")

        if method == "tools/list":
            result = {"tools": self._adapter.list_tools()}
        elif method == "tools/call":
            tool_name = str(params.get("name") or "")
            result = {
                "content": [{"type": "text", "text": f"stub result for {tool_name}"}],
                "isError": False,
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }

        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def call(self, method: str, params: dict | None = None) -> Any:
        response = self.handle({"jsonrpc": "2.0", "id": "1", "method": method, "params": params or {}})
        if "error" in response:
            raise RuntimeError(str(response["error"]))
        return response.get("result")
