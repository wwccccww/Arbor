"""E2E: HTTP JSON-RPC MCP server invoked through McpHttpJsonRpcTransport."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from arbor.adapters.outbound.mcp.http_transport import McpHttpJsonRpcTransport
from arbor.adapters.outbound.mcp.jsonrpc_transport import McpJsonRpcTransport
from arbor.adapters.outbound.mcp.stub_adapter import default_mcp_stub


class _McpHttpHandler(BaseHTTPRequestHandler):
    transport: McpJsonRpcTransport

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        response = self.transport.handle(body)
        payload = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        return


def test_mcp_http_external_server_e2e():
    stub = default_mcp_stub()
    handler_cls = _McpHttpHandler
    handler_cls.transport = McpJsonRpcTransport(stub)
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        transport = McpHttpJsonRpcTransport(f"http://127.0.0.1:{port}/rpc")
        tools = transport.call("tools/list")
        names = [str(item.get("name")) for item in tools.get("tools") or []]
        assert any("demo:search" in name for name in names)
        result = transport.call(
            "tools/call",
            {"name": "demo:search", "arguments": {"query": "空调故障"}},
        )
        text = (result.get("content") or [{}])[0].get("text") or ""
        assert "stub hit" in text
    finally:
        server.shutdown()
