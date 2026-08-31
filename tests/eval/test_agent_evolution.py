from __future__ import annotations

import json

from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack
from arbor.application.evaluation.agent_evolution import (
    evolution_baseline_path,
    run_agent_evolution_tracks,
)


def test_agent_evolution_tracks_match_frozen_baseline():
    stack = build_agent_eval_stack(use_employee_templates=False)
    live = run_agent_evolution_tracks(stack=stack)
    baseline_path = evolution_baseline_path()
    assert baseline_path.is_file()
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    live_tracks = {t["id"]: t for t in live.get("tracks") or []}
    for track in baseline.get("tracks") or []:
        tid = track["id"]
        assert tid in live_tracks
        assert live_tracks[tid]["task_success_rate"] == track["task_success_rate"]
    assert live_tracks["bounded_rag_recovery_hitl"]["task_success_rate"] >= live_tracks[
        "single_round_tool"
    ]["task_success_rate"]


def test_agent_evolution_baseline_listed():
    from arbor.application.evaluation.list_baselines import list_eval_baselines

    ids = {item["id"] for item in list_eval_baselines()["items"]}
    assert "agent-evolution-v1" in ids
