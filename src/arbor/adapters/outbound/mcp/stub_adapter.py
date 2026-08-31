"""MCP adapter stub: register external tool manifests into Tool Registry."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class McpToolManifest:
    name: str
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    server_name: str = "mcp-stub"
    approval_required: bool = False
    risk_level: str = "low"


class McpStubAdapter:
    """Phase 8 stub — maps MCP manifests to registry entries without live MCP transport."""

    def __init__(self) -> None:
        self._manifests: dict[str, McpToolManifest] = {}

    def register_manifest(self, manifest: McpToolManifest) -> None:
        key = f"{manifest.server_name}:{manifest.name}"
        self._manifests[key] = manifest

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": key,
                "description": manifest.description,
                "input_schema": dict(manifest.input_schema),
                "approval_required": manifest.approval_required,
                "risk_level": manifest.risk_level,
                "source": "mcp-stub",
            }
            for key, manifest in self._manifests.items()
        ]

    def invoke_tool(self, key: str, arguments: dict) -> dict:
        manifest = self._manifests.get(key)
        if manifest is None:
            raise ValueError(f"unknown mcp tool: {key}")
        if manifest.name == "search":
            query = str(arguments.get("query") or "").strip()
            return {
                "tool": key,
                "status": "ok",
                "provider": manifest.server_name,
                "results": [{"text": f"stub hit for {query or 'empty'}"}],
            }
        return {
            "tool": key,
            "status": "ok",
            "provider": manifest.server_name,
            "arguments": dict(arguments),
        }

    def to_registry_specs(self) -> list[dict]:
        specs: list[dict] = []
        for key, manifest in self._manifests.items():
            specs.append(
                {
                    "name": key.replace(":", "."),
                    "description": manifest.description or f"MCP tool {manifest.name}",
                    "input_schema": dict(manifest.input_schema),
                    "approval_required": manifest.approval_required,
                    "risk_level": manifest.risk_level,
                }
            )
        return specs


def default_mcp_stub() -> McpStubAdapter:
    adapter = McpStubAdapter()
    adapter.register_manifest(
        McpToolManifest(
            name="search",
            description="Stub MCP search tool",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            server_name="demo",
        )
    )
    return adapter
