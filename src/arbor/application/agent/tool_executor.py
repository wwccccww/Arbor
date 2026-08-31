from __future__ import annotations

import concurrent.futures
import hashlib
import time
from datetime import UTC, datetime

from arbor.application.tools.registry import ToolDefinition, ToolRegistry
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
        mcp_transport=None,
        observability=None,
    ) -> None:
        self.registry = registry
        self.tool_executions = tool_executions
        self.calendar_tool = calendar_tool
        self.ticket_tool = ticket_tool
        self.mcp_transport = mcp_transport
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
                obs.increment("arbor_tool_call_total", result="idempotent_hit", tool=canonical_short)
                return dict(existing["result"])

        max_attempts = max(1, int((tool.retry_policy or {}).get("max_attempts") or 1))
        started = time.perf_counter()
        last_error: DomainError | None = None

        for attempt in range(max_attempts):
            try:
                result = self._invoke_with_timeout(
                    tool=tool,
                    canonical=canonical,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    run=run,
                    args=args,
                )
                result = self.registry.redact_result(tool, dict(result))
                if tool.idempotency_policy.value == "required":
                    self.tool_executions.complete(tenant_id, canonical, idem_key, result)
                obs.event(
                    "tool.call",
                    tool=canonical,
                    result="success",
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    attempt=attempt + 1,
                )
                obs.increment("arbor_tool_call_total", result="success", tool=canonical_short)
                return result
            except DomainError as exc:
                last_error = exc
                if exc.code == "TOOL_TIMEOUT" and attempt < max_attempts - 1:
                    if tool.idempotency_policy.value == "required":
                        self.tool_executions.fail(tenant_id, canonical, idem_key, exc.code)
                    obs.event(
                        "tool.call",
                        tool=canonical,
                        result="timeout_retry",
                        attempt=attempt + 1,
                        duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    )
                    obs.increment("arbor_tool_call_total", result="timeout_retry", tool=canonical_short)
                    continue
                if tool.idempotency_policy.value == "required":
                    self.tool_executions.fail(tenant_id, canonical, idem_key, exc.code)
                obs.event(
                    "tool.call",
                    tool=canonical,
                    result="error",
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    error_kind=exc.code,
                )
                obs.increment("arbor_tool_call_total", result="error", tool=canonical_short)
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
                obs.increment("arbor_tool_call_total", result="error", tool=canonical_short)
                raise DomainError("TOOL_EXECUTION_FAILED", str(exc)) from exc

        if last_error is not None:
            raise last_error
        raise DomainError("TOOL_EXECUTION_FAILED", "tool execution failed")

    def _invoke_with_timeout(
        self,
        *,
        tool: ToolDefinition,
        canonical: str,
        tenant_id: TenantId,
        user_id: UserId,
        run: AgentRun,
        args: dict,
    ) -> dict:
        timeout_sec = max(int(tool.timeout_ms), 1) / 1000.0
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                self._invoke_tool,
                canonical=canonical,
                tenant_id=tenant_id,
                user_id=user_id,
                run=run,
                args=args,
            )
            try:
                return future.result(timeout=timeout_sec)
            except concurrent.futures.TimeoutError:
                raise DomainError("TOOL_TIMEOUT", f"tool timed out after {tool.timeout_ms}ms")

    def _invoke_tool(
        self,
        *,
        canonical: str,
        tenant_id: TenantId,
        user_id: UserId,
        run: AgentRun,
        args: dict,
    ) -> dict:
        if canonical == "calendar.list":
            if self.calendar_tool is None:
                return {"tool": "calendar", "status": "ok", "provider": "stub", "events": []}
            return self.calendar_tool.list_upcoming(
                tenant_id=tenant_id,
                user_id=user_id,
                query_text=str(args.get("query") or run.goal),
            )
        if canonical == "ticket.create":
            if self.ticket_tool is None:
                idem_key = _idempotency_key(run.id, run.current_step, canonical)
                return {
                    "tool": "ticket",
                    "status": "ok",
                    "provider": "stub",
                    "ticket_id": f"stub-{idem_key[:8]}",
                    "title": str(args.get("title") or run.goal[:80]),
                }
            return self.ticket_tool.create(
                tenant_id=tenant_id,
                user_id=user_id,
                title=str(args.get("title") or run.goal[:80]),
                description=str(args.get("description") or run.goal),
            )
        if self.mcp_transport is not None and canonical.startswith("demo."):
            mcp_key = canonical.replace(".", ":")
            payload = self.mcp_transport.call(
                "tools/call",
                {"name": mcp_key, "arguments": args},
            )
            return {
                "tool": canonical,
                "status": "ok",
                "provider": "mcp-jsonrpc",
                "mcp": payload,
            }
        tool = self.registry.get(canonical)
        if tool is None or tool.handler is None:
            raise DomainError("FORBIDDEN_TOOL", f"tool not wired: {canonical}")
        return tool.handler(**args)


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
            retry_policy={"max_attempts": 2},
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
