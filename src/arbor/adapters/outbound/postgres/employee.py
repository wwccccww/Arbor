from __future__ import annotations

from datetime import UTC, datetime

from psycopg.types.json import Jsonb

from arbor.domain.agent.employee import DigitalEmployeeDefinition, EmployeeReleaseStatus
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _definition_from_row(row: dict) -> DigitalEmployeeDefinition:
    payload = dict(row.get("definition") or {})
    return DigitalEmployeeDefinition(
        tenant_id=TenantId(str(row["tenant_id"])),
        persona_id=PersonaId(str(row["persona_id"])),
        version=str(row["version"]),
        role=str(row.get("role") or payload.get("role") or ""),
        goals=list(payload.get("goals") or []),
        skills=list(payload.get("skills") or []),
        knowledge_scopes=list(payload.get("knowledge_scopes") or []),
        tool_policy=dict(payload.get("tool_policy") or {}),
        approval_policy=dict(payload.get("approval_policy") or {}),
        memory_policy=dict(payload.get("memory_policy") or {}),
        escalation_policy=dict(payload.get("escalation_policy") or {}),
        run_budget_policy=dict(payload.get("run_budget_policy") or {}),
        evaluation_suite=str(payload.get("evaluation_suite") or "agent-v1"),
        release_status=EmployeeReleaseStatus(str(row.get("release_status") or "draft")),
        eval_gate_passed=bool(row.get("eval_gate_passed")),
    )


def _payload(definition: DigitalEmployeeDefinition) -> dict:
    return {
        "goals": list(definition.goals),
        "skills": list(definition.skills),
        "knowledge_scopes": list(definition.knowledge_scopes),
        "tool_policy": dict(definition.tool_policy),
        "approval_policy": dict(definition.approval_policy),
        "memory_policy": dict(definition.memory_policy),
        "escalation_policy": dict(definition.escalation_policy),
        "run_budget_policy": dict(definition.run_budget_policy),
        "evaluation_suite": definition.evaluation_suite,
        "role": definition.role,
    }


def _policy_snapshot(definition: DigitalEmployeeDefinition) -> dict:
    return {
        "version": definition.version,
        "role": definition.role,
        "tool_policy": dict(definition.tool_policy),
        "approval_policy": dict(definition.approval_policy),
        "memory_policy": dict(definition.memory_policy),
        "escalation_policy": dict(definition.escalation_policy),
        "run_budget_policy": dict(definition.run_budget_policy),
        "evaluation_suite": definition.evaluation_suite,
    }


class PgEmployeeDefinitionRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def create_draft(
        self,
        tenant_id: TenantId,
        definition: DigitalEmployeeDefinition,
    ) -> DigitalEmployeeDefinition:
        if definition.release_status != EmployeeReleaseStatus.DRAFT:
            raise DomainError("VALIDATION_ERROR", "create_draft requires draft status")
        existing = self.get(tenant_id, definition.persona_id, definition.version)
        if existing is not None:
            raise DomainError("CONFLICT", "employee definition version already exists")
        self.conn.execute(
            """
            INSERT INTO employee_definitions (
                tenant_id, persona_id, version, role, definition, release_status,
                eval_gate_passed, eval_report, policy_snapshot
            ) VALUES (
                %s::uuid, %s::uuid, %s, %s, %s, 'draft', false, '{}'::jsonb, '{}'::jsonb
            )
            """,
            (
                tenant_id.value,
                definition.persona_id.value,
                definition.version,
                definition.role,
                Jsonb(_payload(definition)),
            ),
        )
        saved = self.get(tenant_id, definition.persona_id, definition.version)
        if saved is None:
            raise DomainError("INTERNAL", "failed to persist employee definition draft")
        return saved

    def get(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str | None = None,
    ) -> DigitalEmployeeDefinition | None:
        if version:
            row = self.conn.execute(
                """
                SELECT * FROM employee_definitions
                WHERE tenant_id = %s::uuid AND persona_id = %s::uuid AND version = %s
                """,
                (tenant_id.value, persona_id.value, version),
            ).fetchone()
            return _definition_from_row(row) if row else None
        row = self.conn.execute(
            """
            SELECT * FROM employee_definitions
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid
              AND release_status = 'published'
            ORDER BY version DESC
            LIMIT 1
            """,
            (tenant_id.value, persona_id.value),
        ).fetchone()
        if row:
            return _definition_from_row(row)
        row = self.conn.execute(
            """
            SELECT * FROM employee_definitions
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid AND version = '1.0'
            """,
            (tenant_id.value, persona_id.value),
        ).fetchone()
        return _definition_from_row(row) if row else None

    def list_versions(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
    ) -> list[DigitalEmployeeDefinition]:
        rows = self.conn.execute(
            """
            SELECT * FROM employee_definitions
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid
            ORDER BY version DESC
            """,
            (tenant_id.value, persona_id.value),
        ).fetchall()
        return [_definition_from_row(row) for row in rows]

    def record_eval_gate(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str,
        *,
        gate_passed: bool,
        report: dict | None = None,
    ) -> None:
        row = self.conn.execute(
            """
            UPDATE employee_definitions
            SET eval_gate_passed = %s,
                eval_report = %s,
                updated_at = now()
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid AND version = %s
            RETURNING version
            """,
            (
                gate_passed,
                Jsonb(report or {}),
                tenant_id.value,
                persona_id.value,
                version,
            ),
        ).fetchone()
        if row is None:
            raise DomainError("NOT_FOUND", "employee definition not found")

    def publish(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str,
    ) -> DigitalEmployeeDefinition:
        definition = self.get(tenant_id, persona_id, version)
        if definition is None:
            raise DomainError("NOT_FOUND", "employee definition not found")
        if definition.release_status == EmployeeReleaseStatus.PUBLISHED:
            raise DomainError("VALIDATION_ERROR", "already published")
        if definition.release_status == EmployeeReleaseStatus.ARCHIVED:
            raise DomainError("VALIDATION_ERROR", "cannot publish archived definition")
        if not definition.eval_gate_passed:
            raise DomainError("EMPLOYEE_EVAL_GATE", "employee eval gate not passed")
        snapshot = _policy_snapshot(definition)
        self.conn.execute(
            """
            UPDATE employee_definitions
            SET release_status = 'archived', updated_at = now()
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid
              AND release_status = 'published' AND version <> %s
            """,
            (tenant_id.value, persona_id.value, version),
        )
        row = self.conn.execute(
            """
            UPDATE employee_definitions
            SET release_status = 'published',
                policy_snapshot = %s,
                published_at = now(),
                updated_at = now()
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid AND version = %s
            RETURNING *
            """,
            (
                Jsonb(snapshot),
                tenant_id.value,
                persona_id.value,
                version,
            ),
        ).fetchone()
        if row is None:
            raise DomainError("INTERNAL", "publish failed")
        return _definition_from_row(row)

    def archive(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str,
    ) -> DigitalEmployeeDefinition:
        row = self.conn.execute(
            """
            UPDATE employee_definitions
            SET release_status = 'archived', updated_at = now()
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid AND version = %s
            RETURNING *
            """,
            (tenant_id.value, persona_id.value, version),
        ).fetchone()
        if row is None:
            raise DomainError("NOT_FOUND", "employee definition not found")
        return _definition_from_row(row)

    def archive_all_for_persona(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
    ) -> int:
        result = self.conn.execute(
            """
            UPDATE employee_definitions
            SET release_status = 'archived', updated_at = now()
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid
              AND release_status <> 'archived'
            """,
            (tenant_id.value, persona_id.value),
        )
        return int(result.rowcount or 0)

    def ensure_published(
        self,
        tenant_id: TenantId,
        definition: DigitalEmployeeDefinition,
    ) -> None:
        if self.get(tenant_id, definition.persona_id, definition.version) is not None:
            return
        snapshot = _policy_snapshot(definition)
        self.conn.execute(
            """
            INSERT INTO employee_definitions (
                tenant_id, persona_id, version, role, definition, release_status,
                eval_gate_passed, eval_report, policy_snapshot, published_at
            ) VALUES (
                %s::uuid, %s::uuid, %s, %s, %s, 'published', true, '{}'::jsonb, %s, now()
            )
            ON CONFLICT (tenant_id, persona_id, version) DO NOTHING
            """,
            (
                tenant_id.value,
                definition.persona_id.value,
                definition.version,
                definition.role,
                Jsonb(_payload(definition)),
                Jsonb(snapshot),
            ),
        )
