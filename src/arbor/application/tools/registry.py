from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolRiskLevel(str, Enum):
    READ = "read"
    LOW = "low"
    HIGH = "high"


class IdempotencyPolicy(str, Enum):
    NONE = "none"
    REQUIRED = "required"


@dataclass
class ToolDefinition:
    name: str
    version: str = "1"
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    required_capability: str | None = None
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    approval_required: bool = False
    timeout_ms: int = 30000
    retry_policy: dict = field(default_factory=dict)
    idempotency_policy: IdempotencyPolicy = IdempotencyPolicy.NONE
    redact_fields: list[str] = field(default_factory=list)
    handler: Callable[..., dict] | None = None
    aliases: list[str] = field(default_factory=list)


class ToolRegistry:
  def __init__(self) -> None:
    self._tools: dict[str, ToolDefinition] = {}

  def register(self, tool: ToolDefinition) -> None:
    self._tools[tool.name] = tool
    for alias in tool.aliases:
      self._tools[alias] = tool

  def get(self, name: str) -> ToolDefinition | None:
    key = (name or "").strip().lower()
    if not key:
      return None
    if key in self._tools:
      return self._tools[key]
    normalized = key.replace(".", "_")
    return self._tools.get(normalized) or self._tools.get(key.replace("_", "."))

  def list_names(self) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for tool in self._tools.values():
      if tool.name not in seen:
        seen.add(tool.name)
        names.append(tool.name)
    return sorted(names)

  def validate_arguments(self, tool: ToolDefinition, arguments: dict) -> dict:
    schema = tool.input_schema or {}
    props = schema.get("properties") if isinstance(schema, dict) else None
    if not props:
      return dict(arguments or {})
    out: dict[str, Any] = {}
    for key, spec in props.items():
      if key in (arguments or {}):
        out[key] = arguments[key]
      elif isinstance(spec, dict) and "default" in spec:
        out[key] = spec["default"]
    required = schema.get("required") or []
    for key in required:
      if key not in out or out[key] is None or str(out[key]).strip() == "":
        from arbor.domain.errors import DomainError

        raise DomainError("VALIDATION_ERROR", f"missing tool argument: {key}")
    return out

  def redact_result(self, tool: ToolDefinition, result: dict) -> dict:
    if not tool.redact_fields:
      return result
    cleaned = dict(result)
    for key in tool.redact_fields:
      if key in cleaned:
        cleaned[key] = "[redacted]"
    return cleaned
