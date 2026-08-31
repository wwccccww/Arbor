from __future__ import annotations

import json

from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack
from arbor.application.evaluation.agent_ablation import (
    ablation_baseline_path,
    ablation_fixture_path,
    load_ablation_case_ids,
    run_agent_ablation_tracks,
)


def test_ablation_all_tracks_share_identical_case_ids():
    stack = build_agent_eval_stack(use_employee_templates=False)
    live = run_agent_ablation_tracks(stack=stack, fixture_path=ablation_fixture_path())
    expected = set(load_ablation_case_ids())
    assert len(expected) == 8
    for track in live.get("tracks") or []:
        assert set(track.get("case_ids") or []) == expected
        assert track.get("case_count") == len(expected)


def test_ablation_p0_security_metrics_zero():
    stack = build_agent_eval_stack(use_employee_templates=False)
    live = run_agent_ablation_tracks(stack=stack, fixture_path=ablation_fixture_path())
    for track in live.get("tracks") or []:
        assert track.get("unauthorized_action_rate", 0.0) == 0.0
        assert track.get("approval_bypass_rate", 0.0) == 0.0
        assert track.get("duplicate_side_effect_rate", 0.0) == 0.0
        assert track.get("tenant_leak_rate", 0.0) == 0.0


def test_ablation_tracks_match_frozen_baseline():
    stack = build_agent_eval_stack(use_employee_templates=False)
    live = run_agent_ablation_tracks(stack=stack, fixture_path=ablation_fixture_path())
    baseline_path = ablation_baseline_path()
    assert baseline_path.is_file(), "run ablation once to freeze eval/baselines/agent-ablation-v1.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    live_tracks = {t["id"]: t for t in live.get("tracks") or []}
    for track in baseline.get("tracks") or []:
        tid = track["id"]
        assert tid in live_tracks
        assert live_tracks[tid]["task_success_rate"] == track["task_success_rate"]
        assert live_tracks[tid]["case_count"] == track["case_count"]


def test_ablation_full_track_beats_single_round_on_same_cases():
    stack = build_agent_eval_stack(use_employee_templates=False)
    live = run_agent_ablation_tracks(stack=stack, fixture_path=ablation_fixture_path())
    tracks = {t["id"]: t for t in live.get("tracks") or []}
    assert tracks["bounded_rag_recovery_hitl"]["task_success_rate"] >= tracks[
        "single_round_tool"
    ]["task_success_rate"]


def test_agent_ablation_baseline_listed():
    from arbor.application.evaluation.list_baselines import list_eval_baselines

    ids = {item["id"] for item in list_eval_baselines()["items"]}
    assert "agent-ablation-v1" in ids


def test_agent_evolution_marked_historical():
    from arbor.application.evaluation.list_baselines import list_eval_baselines

    items = {item["id"]: item for item in list_eval_baselines()["items"]}
    assert items["agent-evolution-v1"].get("historical") is True
