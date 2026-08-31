from __future__ import annotations

from typing import Protocol


class PlannerPort(Protocol):
    """Structured next-action planner for Agent advance loop."""

    def next_action(
        self,
        *,
        goal: str,
        steps: list[dict],
        context_manifest: dict,
        tool_schemas: list[dict],
        budget: dict,
        plan_script: list[dict] | None = None,
        evidence_ids: list[str] | None = None,
        run_metadata: dict | None = None,
    ) -> dict: ...
