from __future__ import annotations

from datetime import UTC, datetime

from arbor.domain.memory.memory import InboxItem
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ExtractRunMemory:
    """Create pending Inbox candidates from completed agent runs (no auto-write)."""

    def __init__(self, *, personas, inbox, ids, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.inbox = inbox
        self.ids = ids
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        run_id: str,
        goal: str,
        final_output: dict | None,
        tool_results: list[dict],
    ) -> int:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            return 0
        if Capability.WRITE_MEMORY not in self.auth.capabilities_for(persona, user_id):
            return 0
        text = str((final_output or {}).get("text") or "").strip()
        if not text and not tool_results:
            return 0
        summary_parts = [f"任务：{goal}"]
        if text:
            summary_parts.append(f"结果：{text}")
        if tool_results:
            summary_parts.append(f"工具记录：{len(tool_results)} 条")
        payload = {
            "text": "；".join(summary_parts),
            "source": f"agent_run:{run_id}",
            "memory_type": "episode_summary",
            "memory_class": "episodic",
            "source_run_id": run_id,
        }
        self.inbox.add(
            InboxItem(
                id=self.ids.new_id(),
                tenant_id=tenant_id,
                persona_id=persona_id,
                kind="fact",
                payload=payload,
            )
        )
        return 1
