from __future__ import annotations

import json
from pathlib import Path

from arbor.application.evaluation.agent_runner import run_agent_smoke
from arbor.paths import repo_root


def _case_has_retrieve(case: dict) -> bool:
    script = list(case.get("plan_script") or [])
    return any(str(step.get("action") or "") == "retrieve" for step in script)


def _case_needs_hitl(case: dict) -> bool:
    return any(
        [
            case.get("expect_waiting_approval"),
            case.get("simulate_worker_restart"),
            case.get("expect_timeout_retry"),
            case.get("replay_tool_on_last_step"),
        ]
    )


def classify_agent_case(case: dict) -> str:
    if not _case_has_retrieve(case):
        return "bounded_agent_loop"
    if not _case_needs_hitl(case):
        return "bounded_step_rag"
    return "bounded_rag_recovery_hitl"


def agent_fixture_path() -> Path:
    return repo_root() / "eval" / "fixtures" / "agent-v1" / "cases.json"


def run_agent_evolution_tracks(
    *,
    stack: dict,
    fixture_path: Path | None = None,
) -> dict:
    if stack is None:
        raise ValueError("stack is required")
    fixture_path = fixture_path or agent_fixture_path()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    all_cases = list(payload.get("cases") or [])

    loop_ids = {c["id"] for c in all_cases if classify_agent_case(c) == "bounded_agent_loop"}
    rag_ids = {c["id"] for c in all_cases if classify_agent_case(c) == "bounded_step_rag"}
    hitl_ids = {c["id"] for c in all_cases}

    def _run(case_ids: set[str] | None = None, max_steps_cap: int | None = None) -> dict:
        return run_agent_smoke(
            fixture_path=fixture_path,
            start_run=stack["start_run"],
            approve_step=stack["approve_step"],
            reject_step=stack["reject_step"],
            resume_run=stack["resume_run"],
            personas=stack["personas"],
            runs=stack["runs"],
            flaky_ticket_tool=stack["flaky_ticket_tool"],
            counting_ticket_tool=stack["counting_ticket_tool"],
            case_ids=case_ids,
            max_steps_cap=max_steps_cap,
        )

    single_round = _run(case_ids=hitl_ids, max_steps_cap=1)
    bounded_loop = _run(case_ids=loop_ids)
    bounded_rag = _run(case_ids=rag_ids)
    full_hitl = _run(case_ids=hitl_ids)

    tracks = [
        {
            "id": "single_round_tool",
            "label": "单轮 tool calling（max_steps=1）",
            "task_success_rate": single_round.get("task_success_rate", 0.0),
            "case_count": len(single_round.get("cases") or []),
        },
        {
            "id": "bounded_agent_loop",
            "label": "有界 Agent 循环（无 Step RAG）",
            "task_success_rate": bounded_loop.get("task_success_rate", 0.0),
            "case_count": len(loop_ids),
        },
        {
            "id": "bounded_step_rag",
            "label": "有界循环 + Step RAG",
            "task_success_rate": bounded_rag.get("task_success_rate", 0.0),
            "case_count": len(rag_ids),
        },
        {
            "id": "bounded_rag_recovery_hitl",
            "label": "Step RAG + 恢复/HITL",
            "task_success_rate": full_hitl.get("task_success_rate", 0.0),
            "case_count": len(hitl_ids),
        },
    ]
    return {
        "suite_version": "agent-evolution-v1",
        "description": "Four-track agent comparison per guide §11.3",
        "tracks": tracks,
    }


def evolution_baseline_path() -> Path:
    return repo_root() / "eval" / "baselines" / "agent-evolution-v1.json"
