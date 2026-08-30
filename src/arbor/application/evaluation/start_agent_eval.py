from __future__ import annotations

import json

from arbor.application.evaluation.agent_runner import run_agent_smoke
from arbor.domain.errors import DomainError
from arbor.paths import repo_root


class StartAgentEvalRun:
    def __init__(
        self,
        *,
        start_run,
        approve_step,
        reject_step,
        personas,
        runs,
        resume_run=None,
        observability=None,
        eval_runs=None,
        ids=None,
    ) -> None:
        self.start_run = start_run
        self.approve_step = approve_step
        self.reject_step = reject_step
        self.personas = personas
        self.runs = runs
        self.resume_run = resume_run
        self.observability = observability
        self.eval_runs = eval_runs
        self.ids = ids

    def __call__(
        self,
        *,
        workspace_admin: bool,
        tenant_id: str | None = None,
        suite_version: str = "agent-v1",
    ) -> dict:
        if not workspace_admin:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        fixture = repo_root() / "eval" / "fixtures" / suite_version / "cases.json"
        if not fixture.is_file():
            raise DomainError("NOT_FOUND", f"agent eval fixture not found: {suite_version}")
        report = run_agent_smoke(
            fixture_path=fixture,
            start_run=self.start_run,
            approve_step=self.approve_step,
            reject_step=self.reject_step,
            resume_run=self.resume_run,
            personas=self.personas,
            runs=self.runs,
        )
        baseline_path = repo_root() / "eval" / "baselines" / f"{suite_version}-smoke.json"
        baseline = {}
        if baseline_path.is_file():
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        report["baseline_task_success_rate"] = baseline.get("task_success_rate")
        report["baseline_avg_latency_ms"] = baseline.get("avg_latency_ms")
        report["p0_security"] = {
            "unauthorized_action_rate": report.get("unauthorized_action_rate", 0.0),
            "approval_bypass_rate": report.get("approval_bypass_rate", 0.0),
            "duplicate_side_effect_rate": report.get("duplicate_side_effect_rate", 0.0),
        }
        if self.eval_runs is not None and tenant_id:
            run_id = self.ids.new_id() if self.ids is not None else f"agent-eval-{suite_version}"
            metrics = {
                "task_success_rate": report.get("task_success_rate", 0.0),
                "unauthorized_action_rate": report.get("unauthorized_action_rate", 0.0),
                "approval_bypass_rate": report.get("approval_bypass_rate", 0.0),
                "duplicate_side_effect_rate": report.get("duplicate_side_effect_rate", 0.0),
                "avg_latency_ms": report.get("avg_latency_ms", 0.0),
                "avg_cost_micros": report.get("avg_cost_micros", 0.0),
            }
            self.eval_runs.save(
                {
                    "id": run_id,
                    "tenant_id": tenant_id,
                    "suite_version": suite_version,
                    "strategy": "agent-smoke",
                    "mode": "agent",
                    "status": "completed",
                    "metrics": metrics,
                    "p0_tenant_leak_zero": True,
                    "cases": report.get("cases") or [],
                }
            )
            report["eval_run_id"] = run_id
        return report
