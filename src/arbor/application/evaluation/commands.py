from __future__ import annotations

from arbor.application.evaluation.runner import comparison_row
from arbor.application.retrieval import STRATEGIES
from arbor.domain.errors import DomainError

SUITES = frozenset({"v1", "ragas-v1"})


def _case_view(row: dict) -> dict:
    """Project one scored retrieval case into the API-facing per-case view."""
    expected = list(row.get("expected_memory_ids") or [])
    expected_event = row.get("expected_event_id")
    expected_source = row.get("expected_source")
    passed = True
    if row.get("leaked"):
        passed = False
    if expected and row.get("recall", 1.0) < 1.0:
        passed = False
    if expected_source == "event_tree" and expected_event and not row.get("event_hit"):
        passed = False
    return {
        "id": row.get("id"),
        "query": row.get("query"),
        "skill": row.get("skill"),
        "expected_source": expected_source,
        "expected_behavior": row.get("behavior") or row.get("expected_behavior"),
        "expected_memory_count": len(expected),
        "expected_event_id": expected_event,
        "hit_ids": list(row.get("hit_ids") or []),
        "leak_ids": list(row.get("leak_ids") or []),
        "sources": dict(row.get("sources") or {}),
        "recall": row.get("recall", 1.0),
        "leaked": bool(row.get("leaked")),
        "event_hit": bool(row.get("event_hit")),
        "profile_miss": bool(row.get("profile_miss")),
        "passed": passed,
    }


class StartEvalRun:
    """Run frozen-fixture retrieval. Generation is not started from HTTP in this slice."""

    def __init__(self, *, run_retrieval, ids) -> None:
        self.run_retrieval = run_retrieval
        self.ids = ids

    def __call__(
        self,
        *,
        workspace_admin: bool,
        strategy: str,
        suite_version: str,
        mode: str = "retrieval",
    ) -> dict:
        if not workspace_admin:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        if mode != "retrieval":
            raise DomainError("VALIDATION_ERROR", "only retrieval mode is available")
        if strategy not in STRATEGIES:
            raise DomainError("VALIDATION_ERROR", "unknown strategy")
        if suite_version not in SUITES:
            raise DomainError("VALIDATION_ERROR", "unknown suite_version")
        report = self.run_retrieval(strategy=strategy, suite_version=suite_version)
        cases = [_case_view(row) for row in report.get("cases") or []]
        return {
            "id": self.ids.new_id(),
            "status": "completed",
            "strategy": strategy,
            "suite_version": suite_version,
            "mode": "retrieval",
            "metrics": comparison_row(report),
            "p0_tenant_leak_zero": bool(report.get("p0_tenant_leak_zero")),
            "cases": cases,
        }
