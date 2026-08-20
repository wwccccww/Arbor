from __future__ import annotations

from arbor.application.evaluation.runner import comparison_row
from arbor.application.retrieval import STRATEGIES
from arbor.domain.errors import DomainError

SUITES = frozenset({"v1", "ragas-v1"})


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
        return {
            "id": self.ids.new_id(),
            "status": "completed",
            "strategy": strategy,
            "suite_version": suite_version,
            "mode": "retrieval",
            "metrics": comparison_row(report),
            "p0_tenant_leak_zero": bool(report.get("p0_tenant_leak_zero")),
        }
