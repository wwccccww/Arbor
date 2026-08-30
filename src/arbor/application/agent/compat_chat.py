"""Record SendMessage turns as max_steps=1 agent runs for observability parity."""

from __future__ import annotations

from datetime import UTC, datetime

from arbor.domain.agent.run import AgentRunStatus
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId, UserId


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class AgentCompatRecorder:
    def __init__(self, *, start_run, runs, job_queue=None) -> None:
        self.start_run = start_run
        self.runs = runs
        self.job_queue = job_queue

    def record_completed_turn(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        thread_id: ThreadId,
        goal: str,
        text: str,
        citations: list[str],
        retrieval_meta: dict,
    ) -> str:
        run = self.start_run(
            tenant_id=tenant_id,
            user_id=user_id,
            persona_id=persona_id,
            goal=goal,
            thread_id=thread_id,
            max_steps=1,
            token_budget=16000,
            plan_script=[
                {
                    "schema_version": 1,
                    "action": "answer",
                    "text": text,
                    "citations": list(citations),
                    "completion": True,
                }
            ],
            enqueue=False,
        )
        run.metadata["compat_mode"] = True
        run.metadata["retrieval_meta"] = dict(retrieval_meta)
        if run.status != AgentRunStatus.COMPLETED:
            run.mark_completed({"text": text, "citations": list(citations)})
            run.updated_at = _now_iso()
            self.runs.save(run)
        return run.id
