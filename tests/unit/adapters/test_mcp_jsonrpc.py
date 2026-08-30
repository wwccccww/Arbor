from __future__ import annotations

from arbor.adapters.outbound.mcp.jsonrpc_transport import McpJsonRpcTransport
from arbor.adapters.outbound.mcp.stub_adapter import default_mcp_stub


def test_mcp_jsonrpc_lists_tools():
    transport = McpJsonRpcTransport(default_mcp_stub())
    result = transport.call("tools/list")
    tools = result.get("tools") or []
    assert any("demo:search" in str(t.get("name")) for t in tools)
