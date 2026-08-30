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
    ) -> dict:
        if plan_script:
            index = len(steps)
            if index < len(plan_script):
                return validate_planner_action(plan_script[index])
        completed_kinds = {step.get("kind") for step in steps}
        goal_lower = (goal or "").lower()
        if "retrieve" not in completed_kinds:
            return validate_planner_action(
                {
                    "schema_version": 1,
                    "action": "retrieve",
                    "query": goal,
                    "scopes": ["semantic_memory", "procedural_memory", "episodic_memory"],
                    "reason": "gather evidence before acting",
                }
            )
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
