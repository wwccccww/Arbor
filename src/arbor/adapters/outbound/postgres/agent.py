from __future__ import annotations

from psycopg.types.json import Jsonb

from arbor.domain.agent.approval import ApprovalRequest, ApprovalStatus
from arbor.domain.agent.run import AgentRun, AgentRunStatus
from arbor.domain.agent.step import AgentStep, StepKind, StepStatus
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def _run_from_row(row: dict) -> AgentRun:
    thread_id = row.get("thread_id")
    from arbor.domain.shared.ids import ThreadId

    return AgentRun(
        id=str(row["id"]),
        tenant_id=TenantId(str(row["tenant_id"])),
        persona_id=PersonaId(str(row["persona_id"])),
        requested_by=UserId(str(row["requested_by"])),
        goal=str(row.get("goal") or ""),
        status=AgentRunStatus(str(row.get("status") or "pending")),
        thread_id=ThreadId(str(thread_id)) if thread_id else None,
        current_step=int(row.get("current_step") or 0),
        max_steps=int(row.get("max_steps") or 8),
        token_budget=int(row.get("token_budget") or 16000),
        consumed_tokens=int(row.get("consumed_tokens") or 0),
        cost_budget_micros=int(row.get("cost_budget_micros") or 0),
        consumed_cost_micros=int(row.get("consumed_cost_micros") or 0),
        version=int(row.get("version") or 1),
        employee_definition_version=row.get("employee_definition_version"),
        final_output=dict(row.get("final_output") or {}) if row.get("final_output") else None,
        failure=dict(row.get("failure") or {}) if row.get("failure") else None,
        metadata=dict(row.get("metadata") or {}),
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
        finished_at=_iso(row.get("finished_at")) if row.get("finished_at") else None,
    )


def _step_from_row(row: dict) -> AgentStep:
    return AgentStep(
        id=str(row["id"]),
        run_id=str(row["run_id"]),
        tenant_id=TenantId(str(row["tenant_id"])),
        persona_id=PersonaId(str(row["persona_id"])),
        sequence=int(row["sequence"]),
        kind=StepKind(str(row.get("kind") or "plan")),
        status=StepStatus(str(row.get("status") or "pending")),
        input=dict(row.get("input") or {}),
        output=dict(row.get("output") or {}),
        observation=dict(row.get("observation") or {}),
        retry_count=int(row.get("retry_count") or 0),
        error_kind=row.get("error_kind"),
        error_message=row.get("error_message"),
        trace_id=row.get("trace_id"),
        started_at=_iso(row.get("started_at")) if row.get("started_at") else None,
        finished_at=_iso(row.get("finished_at")) if row.get("finished_at") else None,
    )


def _approval_from_row(row: dict) -> ApprovalRequest:
    evidence = row.get("evidence_ids") or []
    approved_by = row.get("approved_by")
    modified = row.get("modified_arguments")
    return ApprovalRequest(
        id=str(row["id"]),
        tenant_id=TenantId(str(row["tenant_id"])),
        run_id=str(row["run_id"]),
        step_id=str(row["step_id"]),
        persona_id=PersonaId(str(row["persona_id"])),
        requested_by=UserId(str(row["requested_by"])),
        tool_name=str(row.get("tool_name") or ""),
        arguments=dict(row.get("arguments") or {}),
        reason=str(row.get("reason") or ""),
        evidence_ids=[str(item) for item in evidence],
        status=ApprovalStatus(str(row.get("status") or "proposed")),
        approved_by=UserId(str(approved_by)) if approved_by else None,
        modified_arguments=dict(modified) if modified else None,
        expires_at=_iso(row.get("expires_at")) if row.get("expires_at") else None,
        created_at=_iso(row.get("created_at")),
        resolved_at=_iso(row.get("resolved_at")) if row.get("resolved_at") else None,
    )


def _iso(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


class PgAgentRunRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def get(self, tenant_id: TenantId, run_id: str) -> AgentRun | None:
        row = self.conn.execute(
            """
            SELECT * FROM agent_runs WHERE id = %s AND tenant_id = %s::uuid
            """,
            (run_id, tenant_id.value),
        ).fetchone()
        return _run_from_row(row) if row else None

    def save(self, run: AgentRun) -> None:
        self.conn.execute(
            """
            INSERT INTO agent_runs (
                id, tenant_id, persona_id, thread_id, requested_by, goal, status,
                current_step, max_steps, token_budget, consumed_tokens,
                cost_budget_micros, consumed_cost_micros, version,
                employee_definition_version, final_output, failure, metadata,
                created_at, updated_at, finished_at
            ) VALUES (
                %s, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::timestamptz, %s::timestamptz, %s::timestamptz
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                current_step = EXCLUDED.current_step,
                consumed_tokens = EXCLUDED.consumed_tokens,
                consumed_cost_micros = EXCLUDED.consumed_cost_micros,
                version = EXCLUDED.version,
                final_output = EXCLUDED.final_output,
                failure = EXCLUDED.failure,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at,
                finished_at = EXCLUDED.finished_at
            """,
            (
                run.id,
                run.tenant_id.value,
                run.persona_id.value,
                run.thread_id.value if run.thread_id else None,
                run.requested_by.value,
                run.goal,
                run.status.value,
                run.current_step,
                run.max_steps,
                run.token_budget,
                run.consumed_tokens,
                run.cost_budget_micros,
                run.consumed_cost_micros,
                run.version,
                run.employee_definition_version,
                Jsonb(run.final_output) if run.final_output else None,
                Jsonb(run.failure) if run.failure else None,
                Jsonb(run.metadata),
                run.created_at or None,
                run.updated_at or None,
                run.finished_at or None,
            ),
        )

    def list_for_persona(
        self, tenant_id: TenantId, persona_id: PersonaId, *, limit: int = 20
    ) -> list[AgentRun]:
        rows = self.conn.execute(
            """
            SELECT * FROM agent_runs
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (tenant_id.value, persona_id.value, limit),
        ).fetchall()
        return [_run_from_row(row) for row in rows]

    def try_advance_version(self, tenant_id: TenantId, run_id: str, expected_version: int) -> bool:
        row = self.conn.execute(
            """
            UPDATE agent_runs
            SET version = version + 1, updated_at = now()
            WHERE id = %s AND tenant_id = %s::uuid AND version = %s
            RETURNING version
            """,
            (run_id, tenant_id.value, expected_version),
        ).fetchone()
        return row is not None


class PgAgentStepRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def add(self, step: AgentStep) -> None:
        self.conn.execute(
            """
            INSERT INTO agent_steps (
                id, run_id, tenant_id, persona_id, sequence, kind, status,
                input, output, observation, retry_count, error_kind, error_message,
                trace_id, started_at, finished_at
            ) VALUES (
                %s, %s, %s::uuid, %s::uuid, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s::timestamptz, %s::timestamptz
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                output = EXCLUDED.output,
                observation = EXCLUDED.observation,
                error_kind = EXCLUDED.error_kind,
                error_message = EXCLUDED.error_message,
                finished_at = EXCLUDED.finished_at
            """,
            (
                step.id,
                step.run_id,
                step.tenant_id.value,
                step.persona_id.value,
                step.sequence,
                step.kind.value,
                step.status.value,
                Jsonb(step.input),
                Jsonb(step.output),
                Jsonb(step.observation),
                step.retry_count,
                step.error_kind,
                step.error_message,
                step.trace_id,
                step.started_at,
                step.finished_at,
            ),
        )

    def list_for_run(self, tenant_id: TenantId, run_id: str) -> list[AgentStep]:
        rows = self.conn.execute(
            """
            SELECT * FROM agent_steps
            WHERE tenant_id = %s::uuid AND run_id = %s
            ORDER BY sequence
            """,
            (tenant_id.value, run_id),
        ).fetchall()
        return [_step_from_row(row) for row in rows]

    def get(self, tenant_id: TenantId, step_id: str) -> AgentStep | None:
        row = self.conn.execute(
            """
            SELECT * FROM agent_steps WHERE id = %s AND tenant_id = %s::uuid
            """,
            (step_id, tenant_id.value),
        ).fetchone()
        return _step_from_row(row) if row else None


class PgApprovalRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def add(self, approval: ApprovalRequest) -> None:
        self.save(approval)

    def get(self, tenant_id: TenantId, approval_id: str) -> ApprovalRequest | None:
        row = self.conn.execute(
            """
            SELECT * FROM approval_requests WHERE id = %s AND tenant_id = %s::uuid
            """,
            (approval_id, tenant_id.value),
        ).fetchone()
        return _approval_from_row(row) if row else None

    def save(self, approval: ApprovalRequest) -> None:
        self.conn.execute(
            """
            INSERT INTO approval_requests (
                id, tenant_id, run_id, step_id, persona_id, requested_by,
                tool_name, arguments, reason, evidence_ids, status,
                approved_by, modified_arguments, expires_at, created_at, resolved_at
            ) VALUES (
                %s, %s::uuid, %s, %s, %s::uuid, %s::uuid,
                %s, %s, %s, %s, %s, %s::uuid, %s, %s::timestamptz,
                %s::timestamptz, %s::timestamptz
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                approved_by = EXCLUDED.approved_by,
                modified_arguments = EXCLUDED.modified_arguments,
                resolved_at = EXCLUDED.resolved_at
            """,
            (
                approval.id,
                approval.tenant_id.value,
                approval.run_id,
                approval.step_id,
                approval.persona_id.value,
                approval.requested_by.value,
                approval.tool_name,
                Jsonb(approval.arguments),
                approval.reason,
                Jsonb(approval.evidence_ids),
                approval.status.value,
                approval.approved_by.value if approval.approved_by else None,
                Jsonb(approval.modified_arguments) if approval.modified_arguments else None,
                approval.expires_at,
                approval.created_at or None,
                approval.resolved_at or None,
            ),
        )

    def list_pending(self, tenant_id: TenantId, *, limit: int = 50) -> list[ApprovalRequest]:
        rows = self.conn.execute(
            """
            SELECT * FROM approval_requests
            WHERE tenant_id = %s::uuid AND status = 'proposed'
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (tenant_id.value, limit),
        ).fetchall()
        return [_approval_from_row(row) for row in rows]


class PgToolExecutionRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def reserve(
        self,
        tenant_id: TenantId,
        tool_name: str,
        idempotency_key: str,
        *,
        run_id: str | None,
        step_id: str | None,
        arguments: dict,
    ) -> dict | None:
        existing = self.conn.execute(
            """
            SELECT result, status FROM tool_executions
            WHERE tenant_id = %s::uuid AND tool_name = %s AND idempotency_key = %s
            """,
            (tenant_id.value, tool_name, idempotency_key),
        ).fetchone()
        if existing is not None:
            return {
                "status": existing["status"],
                "result": dict(existing["result"] or {}) if existing.get("result") else None,
            }
        self.conn.execute(
            """
            INSERT INTO tool_executions (
                id, tenant_id, run_id, step_id, tool_name, idempotency_key, arguments, status
            ) VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, 'pending')
            ON CONFLICT (tenant_id, tool_name, idempotency_key) DO NOTHING
            """,
            (
                f"{tenant_id.value}:{tool_name}:{idempotency_key}",
                tenant_id.value,
                run_id,
                step_id,
                tool_name,
                idempotency_key,
                Jsonb(arguments),
            ),
        )
        return None

    def complete(self, tenant_id: TenantId, tool_name: str, idempotency_key: str, result: dict) -> None:
        self.conn.execute(
            """
            UPDATE tool_executions
            SET status = 'completed', result = %s, finished_at = now()
            WHERE tenant_id = %s::uuid AND tool_name = %s AND idempotency_key = %s
            """,
            (Jsonb(result), tenant_id.value, tool_name, idempotency_key),
        )

    def fail(self, tenant_id: TenantId, tool_name: str, idempotency_key: str, error_kind: str) -> None:
        self.conn.execute(
            """
            UPDATE tool_executions
            SET status = 'failed', error_kind = %s, finished_at = now()
            WHERE tenant_id = %s::uuid AND tool_name = %s AND idempotency_key = %s
            """,
            (error_kind, tenant_id.value, tool_name, idempotency_key),
        )
