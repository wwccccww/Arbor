from __future__ import annotations

from arbor.adapters.outbound.mcp.stub_adapter import (
    McpStubAdapter,
    McpToolManifest,
    default_mcp_stub,
)
from arbor.application.agent.tool_executor import (
    build_default_tool_registry,
    register_mcp_stub_tools,
)


def test_mcp_stub_registers_tools():
    registry = build_default_tool_registry()
    stub = default_mcp_stub()
    register_mcp_stub_tools(registry, stub)
    tool = registry.get("demo.search")
    assert tool is not None
    assert tool.description


def test_mcp_stub_list_tools():
    stub = McpStubAdapter()
    stub.register_manifest(
        McpToolManifest(name="ping", description="ping", server_name="test")
    )
    names = [t["name"] for t in stub.list_tools()]
    assert "test:ping" in names
