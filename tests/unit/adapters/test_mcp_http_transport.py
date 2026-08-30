from __future__ import annotations

from unittest.mock import MagicMock, patch

from arbor.adapters.outbound.mcp.http_transport import McpHttpJsonRpcTransport
from arbor.adapters.outbound.mcp.stub_adapter import default_mcp_stub


def test_mcp_http_uses_remote_when_available():
    stub = default_mcp_stub()
    transport = McpHttpJsonRpcTransport("http://mcp.example/rpc", fallback_adapter=stub)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {"tools": [{"name": "remote:ping"}]},
    }
    with patch("httpx.post", return_value=mock_response) as post:
        result = transport.call("tools/list")
    post.assert_called_once()
    assert result["tools"][0]["name"] == "remote:ping"


def test_mcp_http_falls_back_to_local_adapter():
    stub = default_mcp_stub()
    transport = McpHttpJsonRpcTransport("http://mcp.example/rpc", fallback_adapter=stub)
    with patch("httpx.post", side_effect=OSError("connection refused")):
        result = transport.call("tools/list")
    tools = result.get("tools") or []
    assert any("demo:search" in str(t.get("name")) for t in tools)
