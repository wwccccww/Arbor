from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime

from arbor.application.tools.registry import ToolRegistry
from arbor.application.tools.run_tools import normalize_tool_name
from arbor.domain.agent.run import AgentRun
from arbor.domain.agent.step import AgentStep
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import TenantId, UserId
from arbor.observability.helpers import obs_or_noop


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _idempotency_key(run_id: str, step_sequence: int, tool_name: str) -> str:
    raw = f"{run_id}:{step_sequence}:{tool_name}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class ToolExecutor:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        tool_executions,
        calendar_tool=None,
        ticket_tool=None,
        observability=None,
    ) -> None:
        self.registry = registry
        self.tool_executions = tool_executions
        self.calendar_tool = calendar_tool
        self.ticket_tool = ticket_tool
        self.observability = observability

    def execute(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        run: AgentRun,
        step: AgentStep,
        tool_name: str,
        arguments: dict,
        allowed_tools: set[str],
    ) -> dict:
        obs = obs_or_noop(self.observability)
        tool = self.registry.get(tool_name)
        if tool is None:
            raise DomainError("FORBIDDEN_TOOL", f"unknown tool: {tool_name}")
        canonical = tool.name
        allowed_normalized = set(allowed_tools)
        for name in allowed_tools:
            normalized = normalize_tool_name(str(name))
            if normalized:
                allowed_normalized.add(normalized)
        canonical_short = normalize_tool_name(canonical) or canonical.split(".", 1)[0]
        if canonical not in allowed_normalized and canonical_short not in allowed_normalized:
            raise DomainError("FORBIDDEN_TOOL", f"tool not allowed: {canonical}")
        args = self.registry.validate_arguments(tool, arguments)
        idem_key = _idempotency_key(run.id, step.sequence, canonical)
        if tool.idempotency_policy.value == "required":
            existing = self.tool_executions.reserve(
                tenant_id,
                canonical,
                idem_key,
                run_id=run.id,
                step_id=step.id,
                arguments=args,
            )
            if existing is not None and existing.get("result") is not None:
                obs.event("tool.call", tool=canonical, result="idempotent_hit")
                return dict(existing["result"])

        started = time.perf_counter()
        try:
            if canonical == "calendar.list":
                if self.calendar_tool is None:
                    result = {"tool": "calendar", "status": "ok", "provider": "stub", "events": []}
                else:
                    result = self.calendar_tool.list_upcoming(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        query_text=str(args.get("query") or run.goal),
                    )
            elif canonical == "ticket.create":
                if self.ticket_tool is None:
                    result = {
                        "tool": "ticket",
                        "status": "ok",
                        "provider": "stub",
                        "ticket_id": f"stub-{idem_key[:8]}",
                        "title": str(args.get("title") or run.goal[:80]),
                    }
                else:
                    result = self.ticket_tool.create(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        title=str(args.get("title") or run.goal[:80]),
                        description=str(args.get("description") or run.goal),
                    )
            else:
                if tool.handler is None:
                    raise DomainError("FORBIDDEN_TOOL", f"tool not wired: {canonical}")
                result = tool.handler(**args)
            result = self.registry.redact_result(tool, dict(result))
            if tool.idempotency_policy.value == "required":
                self.tool_executions.complete(tenant_id, canonical, idem_key, result)
            obs.event(
                "tool.call",
                tool=canonical,
                result="success",
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return result
        except DomainError:
            raise
        except Exception as exc:
            if tool.idempotency_policy.value == "required":
                self.tool_executions.fail(tenant_id, canonical, idem_key, exc.__class__.__name__)
            obs.event(
                "tool.call",
                tool=canonical,
                result="error",
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                error_kind=exc.__class__.__name__,
            )
            raise DomainError("TOOL_EXECUTION_FAILED", str(exc)) from exc


def build_default_tool_registry() -> ToolRegistry:
    from arbor.application.tools.registry import IdempotencyPolicy, ToolDefinition, ToolRiskLevel

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="calendar.list",
            aliases=["calendar"],
            description="List upcoming calendar events",
            risk_level=ToolRiskLevel.READ,
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string", "default": ""}},
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="ticket.create",
            aliases=["ticket"],
            description="Create support ticket",
            risk_level=ToolRiskLevel.HIGH,
            approval_required=True,
            idempotency_policy=IdempotencyPolicy.REQUIRED,
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string", "default": ""},
                    "priority": {"type": "string", "default": "normal"},
                },
                "required": ["title"],
            },
        )
    )
    return registry


def register_mcp_stub_tools(registry: ToolRegistry, mcp_stub) -> None:
    from arbor.application.tools.registry import ToolDefinition, ToolRiskLevel

    for spec in mcp_stub.to_registry_specs():
        registry.register(
            ToolDefinition(
                name=str(spec["name"]),
                description=str(spec.get("description") or ""),
                input_schema=dict(spec.get("input_schema") or {}),
                risk_level=ToolRiskLevel.READ,
                approval_required=bool(spec.get("approval_required")),
            )
        )
