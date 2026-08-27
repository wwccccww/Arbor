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
        "persona_id": row.get("persona_id"),
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


def _generation_case_view(row: dict) -> dict:
    """Project one scored generation case into the API-facing per-case view."""
    behavior = row.get("behavior")
    passed = not row.get("leaked")
    if behavior in {"answer", "cite"}:
        passed = passed and bool(row.get("citation_subset"))
    citations = list(row.get("citations") or [])
    return {
        "id": row.get("id"),
        "query": row.get("query"),
        "skill": row.get("skill"),
        "expected_source": None,
        "expected_behavior": behavior,
        "expected_memory_count": len(row.get("injected_memory_ids") or []),
        "expected_event_id": None,
        "hit_ids": citations,
        "leak_ids": [],
        "sources": {},
        "recall": 1.0 if row.get("citation_subset") else 0.0,
        "leaked": bool(row.get("leaked")),
        "event_hit": True,
        "profile_miss": False,
        "passed": passed,
        "citation_subset": bool(row.get("citation_subset")),
        "ragas_faithfulness": row.get("ragas_faithfulness"),
        "text": row.get("text") or "",
        "injected_memory_ids": list(row.get("injected_memory_ids") or []),
        "citations": citations,
        "text_leak": bool(row.get("text_leak")),
    }


class StartEvalRun:
    """Run frozen-fixture retrieval or generation (suite-v1)."""

    def __init__(self, *, run_retrieval, run_generation=None, ids) -> None:
        self.run_retrieval = run_retrieval
        self.run_generation = run_generation
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
        if mode not in {"retrieval", "generation"}:
            raise DomainError("VALIDATION_ERROR", "unknown mode")
        if strategy not in STRATEGIES:
            raise DomainError("VALIDATION_ERROR", "unknown strategy")
        if suite_version not in SUITES:
            raise DomainError("VALIDATION_ERROR", "unknown suite_version")
        if mode == "generation":
            if suite_version != "v1":
                raise DomainError("VALIDATION_ERROR", "generation only supports suite v1")
            if self.run_generation is None:
                raise DomainError("VALIDATION_ERROR", "generation not configured")
            report = self.run_generation(strategy=strategy, suite_version=suite_version)
            cases = [_generation_case_view(row) for row in report.get("cases") or []]
            return {
                "id": self.ids.new_id(),
                "status": "completed",
                "strategy": strategy,
                "suite_version": suite_version,
                "mode": "generation",
                "metrics": report.get("metrics") or {},
                "p0_tenant_leak_zero": bool(report.get("p0_tenant_leak_zero")),
                "cases": cases,
            }
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


class StartPersonaEvalRun:
    """Auto-generate smoke questions for one live persona."""

    def __init__(self, *, run_persona_retrieval, ids) -> None:
        self.run_persona_retrieval = run_persona_retrieval
        self.ids = ids

    def __call__(
        self,
        *,
        workspace_admin: bool,
        tenant_id,
        user_id,
        persona_id,
        strategy: str,
    ) -> dict:
        if not workspace_admin:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        if strategy not in STRATEGIES:
            raise DomainError("VALIDATION_ERROR", "unknown strategy")
        report = self.run_persona_retrieval(
            tenant_id=tenant_id,
            user_id=user_id,
            persona_id=persona_id,
            strategy=strategy,
        )
        cases = [_case_view(row) for row in report.get("cases") or []]
        return {
            "id": self.ids.new_id(),
            "status": "completed",
            "strategy": strategy,
            "suite_version": "persona",
            "mode": "retrieval",
            "persona_id": persona_id.value,
            "metrics": comparison_row(report),
            "p0_tenant_leak_zero": bool(report.get("p0_tenant_leak_zero")),
            "cases": cases,
        }
