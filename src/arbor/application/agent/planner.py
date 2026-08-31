from __future__ import annotations

from arbor.domain.agent.action import validate_planner_action


class ScriptedPlanner:
    """Deterministic planner for tests and agent-smoke eval."""

    def next_action(
        self,
        *,
        goal: str,
        steps: list[dict],
        plan_script: list[dict] | None,
        evidence_ids: list[str],
        run_metadata: dict | None = None,
    ) -> dict:
        meta = dict(run_metadata or {})
        eval_variant = dict(meta.get("eval_variant") or {})
        step_rag_enabled = eval_variant.get("step_rag_enabled", True)
        pending_query = str(meta.get("pending_retrieve_query") or "").strip()
        if pending_query and step_rag_enabled:
            last_tool_idx = max(
                (i for i, s in enumerate(steps) if s.get("kind") == "tool"),
                default=-1,
            )
            retrieve_after_tool = any(
                s.get("kind") == "retrieve" for s in steps[last_tool_idx + 1 :]
            )
            if not retrieve_after_tool:
                return validate_planner_action(
                    {
                        "schema_version": 1,
                        "action": "retrieve",
                        "query": pending_query,
                        "scopes": ["semantic_memory", "procedural_memory", "episodic_memory"],
                        "reason": "re-retrieve after tool observation",
                    }
                )

        if plan_script:
            index = len(steps)
            if index < len(plan_script):
                return validate_planner_action(plan_script[index])

        if not any(s.get("kind") == "retrieve" for s in steps):
            return validate_planner_action(
                {
                    "schema_version": 1,
                    "action": "retrieve",
                    "query": goal,
                    "scopes": ["semantic_memory", "procedural_memory", "episodic_memory"],
                    "reason": "gather evidence before acting",
                }
            )
        goal_lower = (goal or "").lower()
        if "ticket" in goal_lower and not any(s.get("kind") == "tool" for s in steps):
            return validate_planner_action(
                {
                    "schema_version": 1,
                    "action": "tool",
                    "tool_name": "ticket.create",
                    "arguments": {"title": goal[:80], "priority": "high"},
                    "evidence_ids": list(evidence_ids),
                    "reason": "goal requires ticket",
                }
            )
        return validate_planner_action(
            {
                "schema_version": 1,
                "action": "answer",
                "text": f"已完成处理：{goal}",
                "citations": list(evidence_ids),
                "completion": True,
            }
        )
