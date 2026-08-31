from __future__ import annotations

import time
from datetime import UTC, datetime

from arbor.application.agent.planner import ScriptedPlanner, is_repeated_action_loop
from arbor.application.agent.step_retrieval import StepRetrieval, build_step_context_items
from arbor.application.agent.tool_executor import ToolExecutor
from arbor.application.memory.working_memory import clear_working_memory_for_run
from arbor.application.retrieval_config import RetrievalConfig
from arbor.application.tools.run_tools import allowed_tool_names, normalize_tool_name
from arbor.domain.agent.action import validate_planner_action
from arbor.domain.agent.approval import ApprovalRequest
from arbor.domain.agent.run import AgentRun, AgentRunStatus
from arbor.domain.agent.step import AgentStep, StepKind, StepStatus
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import TenantId, UserId
from arbor.observability.context import current_request_context
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
        extract_memory=None,
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
        self.extract_memory = extract_memory
        self.step_retrieval = StepRetrieval(
            memories=memories,
            events=events,
            vector_search=vector_search,
            embed=embed,
            retrieval_config=self.retrieval_config,
            lexical_search=lexical_search,
            observability=observability,
        )

    def _finalize_terminal_run(self, run: AgentRun) -> None:
        if not run.is_terminal():
            return
        clear_working_memory_for_run(
            self.memories,
            run.tenant_id,
            run.persona_id,
            run.id,
        )

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
            self._finalize_terminal_run(run)
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
            context_manifest=dict(run.metadata.get("context_manifest") or {}),
            tool_schemas=self._tool_schemas(),
            budget={
                "max_steps": run.max_steps,
                "current_step": run.current_step,
                "token_budget": run.token_budget,
                "consumed_tokens": run.consumed_tokens,
                "cost_budget_micros": run.cost_budget_micros,
                "consumed_cost_micros": run.consumed_cost_micros,
            },
            plan_script=list(run.metadata.get("plan_script") or []),
            evidence_ids=evidence_ids,
            run_metadata=run.metadata,
        )
        action = validate_planner_action(action)
        if is_repeated_action_loop(
            [{"input": dict(s.input or {})} for s in prior_steps],
            action,
        ):
            run.mark_failed({"kind": "action_loop", "message": "repeated planner action"})
            run.updated_at = _now_iso()
            self._finalize_terminal_run(run)
            self.runs.save(run)
            return run
        planner_meta = getattr(self.planner, "last_metadata", None)
        if isinstance(planner_meta, dict) and planner_meta:
            run.metadata["planner"] = dict(planner_meta)

        step_id = self.ids.new_id()
        trace_id = str(run.metadata.get("request_id") or "")
        ctx = current_request_context()
        if not trace_id and ctx is not None:
            trace_id = ctx.request_id
        if not trace_id:
            trace_id = run.id
        if not run.metadata.get("request_id"):
            run.metadata["request_id"] = trace_id
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
            trace_id=trace_id,
        )

        with obs.span("agent.step", kind=step.kind.value, sequence=sequence):
            step_started = time.perf_counter()
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
                step.mark_failed(exc.code, str(exc))
                run.mark_failed({"kind": exc.code, "message": str(exc)})
                run.updated_at = _now_iso()
                self.steps.add(step)
                self._finalize_terminal_run(run)
                self.runs.save(run)
                return run
            latency_ms = round((time.perf_counter() - step_started) * 1000, 2)
            step.observation = dict(step.observation or {})
            step.observation["latency_ms"] = latency_ms
            metrics = dict(run.metadata.get("metrics") or {})
            latencies = list(metrics.get("step_latencies_ms") or [])
            latencies.append(latency_ms)
            metrics["step_latencies_ms"] = latencies
            metrics["total_latency_ms"] = round(sum(latencies), 2)
            metrics["step_count"] = len(latencies)
            run.metadata["metrics"] = metrics
            run.consumed_cost_micros += 50_000

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
            from arbor.application.agent.retrieval_dto import RetrievalRequest

            query = str(action.get("query") or run.goal)
            scopes = list(action.get("scopes") or [])
            filters = {}
            if scopes:
                class_map = {
                    "semantic_memory": "semantic",
                    "episodic_memory": "episodic",
                    "procedural_memory": "procedural",
                    "working_memory": "working",
                }
                filters["memory_classes"] = [
                    class_map.get(s, s.replace("_memory", "")) for s in scopes
                ]
            request = RetrievalRequest(
                tenant_id=tenant_id,
                persona_id=run.persona_id,
                query=query,
                purpose="agent_step",
                scopes=scopes,
                filters=filters or None,
                k=5,
                run_id=run.id,
                step_id=step.id,
            )
            with obs_or_noop(self.observability).span("rag.retrieve"):
                result = self.step_retrieval.execute(
                    request,
                    capabilities=caps,
                )
            hit_ids = list(result.hit_ids)
            for hid in hit_ids:
                if hid not in evidence_ids:
                    evidence_ids.append(hid)
            run.metadata["evidence_ids"] = evidence_ids
            run.metadata["last_retrieval"] = {
                "strategy": result.strategy,
                "hit_ids": hit_ids,
                "sub_queries": list(result.sub_queries),
            }
            run.metadata.pop("pending_retrieve_query", None)
            active = self.memories.list_active(tenant_id, run.persona_id)
            by_id = {m.id.value: m for m in active}
            _, manifest = build_step_context_items(
                goal=run.goal,
                persona_profile={"display_name": persona.profile.display_name},
                evidence_ids=evidence_ids,
                memories_by_id=by_id,
                tool_results=list(run.metadata.get("tool_results") or []),
            )
            run.metadata["context_manifest"] = manifest
            obs_or_noop(self.observability).observe(
                "arbor_agent_context_tokens", manifest.get("token_usage", 0)
            )
            untrusted_total = int(
                manifest.get("untrusted_instruction_count")
                or manifest.get("untrusted_instruction_total")
                or 0
            )
            obs_or_noop(self.observability).observe(
                "arbor_context_untrusted_instruction_total", untrusted_total
            )
            run.consumed_tokens += int(manifest.get("token_usage") or 200)
            pass_count = sum(1 for s in prior_steps if s.kind == StepKind.RETRIEVE) + 1
            step.mark_completed(
                {"hit_ids": hit_ids, "strategy": result.strategy, "context_manifest": manifest},
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
            allowed_normalized = set(allowed)
            for name in allowed:
                normalized = normalize_tool_name(str(name))
                if normalized:
                    allowed_normalized.add(normalized)
            canonical_short = normalize_tool_name(canonical) or canonical.split(".", 1)[0]
            if canonical not in allowed_normalized and canonical_short not in allowed_normalized:
                raise DomainError("FORBIDDEN_TOOL", f"tool not allowed: {canonical}")
            if tool_def.approval_required:
                eval_variant = dict(run.metadata.get("eval_variant") or {})
                if eval_variant.get("approval_enabled") is False:
                    run.status = AgentRunStatus.HANDED_OFF
                    run.final_output = {
                        "text": "approval required but disabled for eval variant",
                        "kind": "handoff",
                    }
                    run.finished_at = _now_iso()
                    step.mark_completed(run.final_output, observation={"approval_disabled": True})
                    return
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
            pending = str(result.get("title") or result.get("ticket_id") or "").strip()
            eval_variant = dict(run.metadata.get("eval_variant") or {})
            if pending and eval_variant.get("step_rag_enabled", True):
                run.metadata["pending_retrieve_query"] = f"{pending} 处理方案"
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
            self._finalize_terminal_run(run)
            if self.extract_memory is not None:
                self.extract_memory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    persona_id=run.persona_id,
                    run_id=run.id,
                    goal=run.goal,
                    final_output=output,
                    tool_results=list(run.metadata.get("tool_results") or []),
                )
            step.mark_completed(output, observation={"completion": True})
            return

        if action["action"] == "request_clarification":
            run.status = AgentRunStatus.HANDED_OFF
            run.final_output = {"text": str(action.get("text") or ""), "kind": "clarification"}
            run.finished_at = _now_iso()
            self._finalize_terminal_run(run)
            step.mark_completed(run.final_output)
            return

        if action["action"] == "handoff":
            run.status = AgentRunStatus.HANDED_OFF
            run.final_output = {"text": str(action.get("text") or ""), "kind": "handoff"}
            run.finished_at = _now_iso()
            self._finalize_terminal_run(run)
            step.mark_completed(run.final_output)
            return

        raise DomainError("VALIDATION_ERROR", f"unsupported action: {action['action']}")

    def _tool_schemas(self) -> list[dict]:
        schemas: list[dict] = []
        for name in self.tool_executor.registry.list_names():
            tool = self.tool_executor.registry.get(name)
            if tool is None:
                continue
            schemas.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                    "approval_required": tool.approval_required,
                }
            )
        return schemas
