from __future__ import annotations

from datetime import UTC, datetime

from arbor.application.agent.planner import ScriptedPlanner
from arbor.application.agent.tool_executor import ToolExecutor
from arbor.application.retrieval import retrieve
from arbor.application.retrieval_config import RetrievalConfig
from arbor.application.tools.run_tools import allowed_tool_names
from arbor.domain.agent.action import validate_planner_action
from arbor.domain.agent.approval import ApprovalRequest
from arbor.domain.agent.run import AgentRun, AgentRunStatus
from arbor.domain.agent.step import AgentStep, StepKind, StepStatus
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import TenantId, UserId
from arbor.observability.helpers import obs_or_noop


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class AdvanceAgentRun:
    def __init__(
        self,
        *,
        personas,
        runs,
        steps,
        approvals,
        memories,
        events,
        auth: AuthorizationPolicy,
        ids,
        vector_search,
        embed,
        tool_executor: ToolExecutor,
        planner: ScriptedPlanner | None = None,
        retrieval_config: RetrievalConfig | None = None,
        job_queue=None,
        observability=None,
        lexical_search=None,
    ) -> None:
        self.personas = personas
        self.runs = runs
        self.steps = steps
        self.approvals = approvals
        self.memories = memories
        self.events = events
        self.auth = auth
        self.ids = ids
        self.vector_search = vector_search
        self.embed = embed
        self.tool_executor = tool_executor
        self.planner = planner or ScriptedPlanner()
        self.retrieval_config = retrieval_config or RetrievalConfig.from_env()
        self.job_queue = job_queue
        self.observability = observability
        self.lexical_search = lexical_search

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        run_id: str,
        expected_version: int | None = None,
        enqueue_next: bool = True,
    ) -> AgentRun:
        obs = obs_or_noop(self.observability)
        run = self.runs.get(tenant_id, run_id)
        if run is None:
            raise DomainError("NOT_FOUND", "agent run not found")

        persona = self.personas.get(tenant_id, run.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.CHAT not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_CHAT", "chat required")

        if run.status == AgentRunStatus.WAITING_APPROVAL:
            return run
        if run.is_terminal():
            return run
        if run.budget_exhausted():
            run.mark_failed({"kind": "budget_exhausted"})
            run.updated_at = _now_iso()
            self.runs.save(run)
            return run

        if expected_version is not None and run.version != expected_version:
            raise DomainError("AGENT_VERSION_CONFLICT", "stale agent run version")
        if not self.runs.try_advance_version(tenant_id, run_id, run.version):
            raise DomainError("AGENT_VERSION_CONFLICT", "concurrent agent advance")

        run = self.runs.get(tenant_id, run_id)
        if run is None:
            raise DomainError("NOT_FOUND", "agent run not found")
        run.mark_running()
        run.current_step += 1
        sequence = run.current_step
        now = _now_iso()
        run.updated_at = now

        prior_steps = self.steps.list_for_run(tenant_id, run_id)
        evidence_ids = list(run.metadata.get("evidence_ids") or [])
        step_summaries = [
            {"kind": step.kind.value, "status": step.status.value, "output": step.output}
            for step in prior_steps
        ]

        action = self.planner.next_action(
            goal=run.goal,
            steps=step_summaries,
            plan_script=list(run.metadata.get("plan_script") or []),
            evidence_ids=evidence_ids,
        )
        action = validate_planner_action(action)

        step_id = self.ids.new_id()
        step = AgentStep(
            id=step_id,
            run_id=run.id,
            tenant_id=tenant_id,
            persona_id=run.persona_id,
            sequence=sequence,
            kind=self._kind_for_action(action["action"]),
            status=StepStatus.RUNNING,
            input=action,
            started_at=now,
        )

        with obs.span("agent.step", kind=step.kind.value, sequence=sequence):
            try:
                self._execute_action(
                    run=run,
                    step=step,
                    action=action,
                    persona=persona,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    evidence_ids=evidence_ids,
                    prior_steps=prior_steps,
                )
            except DomainError as exc:
                step.mark_failed(exc.code, exc.message)
                run.mark_failed({"kind": exc.code, "message": exc.message})
                run.updated_at = _now_iso()
                self.steps.add(step)
                self.runs.save(run)
                return run

        step.finished_at = _now_iso()
        self.steps.add(step)
        self.runs.save(run)

        if enqueue_next and self.job_queue is not None and run.can_advance() and not run.budget_exhausted():
            self.job_queue.enqueue_run(tenant_id, run.id, run.version)
        return run

    def _kind_for_action(self, action: str) -> StepKind:
        mapping = {
            "retrieve": StepKind.RETRIEVE,
            "tool": StepKind.TOOL,
            "answer": StepKind.ANSWER,
            "request_clarification": StepKind.REFLECT,
            "handoff": StepKind.HANDOFF,
        }
        return mapping.get(action, StepKind.PLAN)

    def _execute_action(
        self,
        *,
        run: AgentRun,
        step: AgentStep,
        action: dict,
        persona,
        user_id: UserId,
        tenant_id: TenantId,
        evidence_ids: list[str],
        prior_steps: list[AgentStep],
    ) -> None:
        caps = self.auth.capabilities_for(persona, user_id)
        if action["action"] == "retrieve":
            memories = (
                self.memories.list_active(tenant_id, run.persona_id)
                if Capability.READ_MEMORY in caps
                else []
            )
            event_nodes = self.events.list_nodes(tenant_id, run.persona_id)
            event_edges = self.events.list_edges(tenant_id, run.persona_id)
            query = action.get("query") or run.goal
            with obs_or_noop(self.observability).span("rag.retrieve"):
                retrieved = retrieve(
                    strategy="layered_tree",
                    query=query,
                    tenant_id=tenant_id,
                    persona_id=run.persona_id,
                    k=5,
                    memories=memories,
                    events=event_nodes,
                    edges=event_edges,
                    summary="",
                    vector_search=self.vector_search,
                    embed=self.embed,
                    config=self.retrieval_config,
                    lexical_search=self.lexical_search,
                    observability=self.observability,
                )
            hit_ids = list(retrieved.get("hit_ids") or [])
            for hid in hit_ids:
                if hid not in evidence_ids:
                    evidence_ids.append(hid)
            run.metadata["evidence_ids"] = evidence_ids
            run.metadata["last_retrieval"] = {
                "strategy": retrieved.get("strategy"),
                "hit_ids": hit_ids,
                "sub_queries": list(retrieved.get("sub_queries") or []),
            }
            run.consumed_tokens += 200
            pass_count = sum(1 for s in prior_steps if s.kind == StepKind.RETRIEVE) + 1
            step.mark_completed(
                {"hit_ids": hit_ids, "strategy": retrieved.get("strategy")},
                observation={"retrieval_pass": pass_count},
            )
            return

        if action["action"] == "tool":
            tool_name = str(action.get("tool_name") or "")
            tool_def = self.tool_executor.registry.get(tool_name)
            if tool_def is None:
                raise DomainError("FORBIDDEN_TOOL", f"unknown tool: {tool_name}")
            allowed = allowed_tool_names(persona.tool_policy)
            canonical = tool_def.name
            if tool_def.approval_required:
                approval = ApprovalRequest(
                    id=self.ids.new_id(),
                    tenant_id=tenant_id,
                    run_id=run.id,
                    step_id=step.id,
                    persona_id=run.persona_id,
                    requested_by=user_id,
                    tool_name=canonical,
                    arguments=dict(action.get("arguments") or {}),
                    reason=str(action.get("reason") or ""),
                    evidence_ids=list(action.get("evidence_ids") or evidence_ids),
                    created_at=_now_iso(),
                )
                self.approvals.add(approval)
                run.metadata["pending_approval_id"] = approval.id
                run.mark_waiting_approval()
                step.mark_completed(
                    {"approval_id": approval.id, "status": "waiting_approval"},
                    observation={"approval_required": True},
                )
                return

            result = self.tool_executor.execute(
                tenant_id=tenant_id,
                user_id=user_id,
                run=run,
                step=step,
                tool_name=tool_name,
                arguments=dict(action.get("arguments") or {}),
                allowed_tools=allowed,
            )
            run.consumed_tokens += 100
            run.metadata.setdefault("tool_results", []).append(result)
            step.mark_completed({"tool": canonical, "result": result}, observation=result)
            return

        if action["action"] == "answer":
            citations = [
                cid
                for cid in (action.get("citations") or [])
                if cid in evidence_ids
            ]
            output = {
                "text": str(action.get("text") or ""),
                "citations": citations,
            }
            run.mark_completed(output)
            run.updated_at = _now_iso()
            step.mark_completed(output, observation={"completion": True})
            return

        if action["action"] == "request_clarification":
            run.status = AgentRunStatus.HANDED_OFF
            run.final_output = {"text": str(action.get("text") or ""), "kind": "clarification"}
            run.finished_at = _now_iso()
            step.mark_completed(run.final_output)
            return

        if action["action"] == "handoff":
            run.status = AgentRunStatus.HANDED_OFF
            run.final_output = {"text": str(action.get("text") or ""), "kind": "handoff"}
            run.finished_at = _now_iso()
            step.mark_completed(run.final_output)
            return

        raise DomainError("VALIDATION_ERROR", f"unsupported action: {action['action']}")
