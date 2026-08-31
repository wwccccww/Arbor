from __future__ import annotations

import json
from pathlib import Path

from arbor.application.evaluation.agent_runner import run_agent_smoke
from arbor.application.evaluation.agent_variants import (
    DEFAULT_ABLATION_VARIANTS,
    AgentEvalVariant,
)
from arbor.paths import repo_root


def ablation_fixture_path() -> Path:
    return repo_root() / "eval" / "fixtures" / "agent-ablation-v1" / "cases.json"


def ablation_baseline_path() -> Path:
    return repo_root() / "eval" / "baselines" / "agent-ablation-v1.json"


def load_ablation_case_ids(fixture_path: Path | None = None) -> list[str]:
    path = fixture_path or ablation_fixture_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [str(c["id"]) for c in payload.get("cases") or []]


def run_agent_ablation_tracks(
    *,
    stack: dict,
    fixture_path: Path | None = None,
    variants: tuple[AgentEvalVariant, ...] | None = None,
) -> dict:
    if stack is None:
        raise ValueError("stack is required")
    fixture_path = fixture_path or ablation_fixture_path()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    all_case_ids = load_ablation_case_ids(fixture_path)
    variants = variants or DEFAULT_ABLATION_VARIANTS

    tracks: list[dict] = []
    for variant in variants:
        report = run_agent_smoke(
            fixture_path=fixture_path,
            start_run=stack["start_run"],
            approve_step=stack["approve_step"],
            reject_step=stack["reject_step"],
            resume_run=stack["resume_run"],
            personas=stack["personas"],
            runs=stack["runs"],
            flaky_ticket_tool=stack["flaky_ticket_tool"],
            counting_ticket_tool=stack["counting_ticket_tool"],
            variant=variant,
        )
        case_ids = [str(c["id"]) for c in report.get("cases") or []]
        if set(case_ids) != set(all_case_ids):
            raise ValueError(
                f"variant {variant.id} case set mismatch: expected {sorted(all_case_ids)}, got {sorted(case_ids)}"
            )
        tracks.append(
            {
                "id": variant.id,
                "label": variant.label,
                "planner_version": variant.planner_version,
                "planner_kind": "fake",
                "max_steps": variant.max_steps,
                "step_rag_enabled": variant.step_rag_enabled,
                "recovery_enabled": variant.recovery_enabled,
                "approval_enabled": variant.approval_enabled,
                "case_count": len(case_ids),
                "case_ids": sorted(case_ids),
                **{
                    k: report[k]
                    for k in (
                        "task_success_rate",
                        "recovery_rate",
                        "unauthorized_action_rate",
                        "approval_bypass_rate",
                        "duplicate_side_effect_rate",
                        "tenant_leak_rate",
                        "human_handoff_rate",
                        "avg_latency_ms",
                        "p95_latency_ms",
                        "avg_steps",
                        "p95_steps",
                        "avg_cost_micros",
                        "cost_per_success_micros",
                    )
                    if k in report
                },
            }
        )

    return {
        "suite_version": "agent-ablation-v1",
        "description": "Fair four-track agent ablation (same frozen cases, capability flags only)",
        "fixture_version": payload.get("fixture_version") or payload.get("suite_version"),
        "seed": payload.get("seed", 42),
        "planner": payload.get("planner", "scripted-v1"),
        "planner_kind": "fake",
        "budget": payload.get("budget") or {"max_steps": 8, "token_budget": 16000},
        "case_count": len(all_case_ids),
        "case_ids": sorted(all_case_ids),
        "tracks": tracks,
    }
