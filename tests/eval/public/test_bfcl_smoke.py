from __future__ import annotations

import json

from arbor.adapters.outbound.benchmarks.bfcl_loader import BFCL_SMOKE, calls_equivalent
from arbor.application.evaluation.public_benchmarks.bfcl_runner import run_bfcl_smoke
from arbor.paths import repo_root

BASELINE = repo_root() / "eval" / "public" / "baselines" / "bfcl-smoke.json"


def test_bfcl_smoke_matches_baseline():
    live = run_bfcl_smoke(fixture_path=BFCL_SMOKE, planner_kind="fake")
    assert BASELINE.is_file(), "run bfcl smoke once to generate baseline"
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert live.get("function_match_rate") == baseline.get("function_match_rate")
    assert live.get("argument_match_rate") == baseline.get("argument_match_rate")
    assert live.get("executable_rate") == baseline.get("executable_rate")
    assert live.get("task_success_rate") == baseline.get("task_success_rate")
    assert live.get("unauthorized_action_rate", 0.0) == 0.0
    assert live.get("approval_bypass_rate", 0.0) == 0.0
    for case in live.get("cases") or []:
        assert case.get("ok") is True, case


def test_bfcl_scoring_detects_wrong_tool_name():
    fn_ok, arg_ok = calls_equivalent(
        {"name": "get_weather", "arguments": {"city": "SF"}},
        {"name": "send_email", "arguments": {"city": "SF"}},
    )
    assert fn_ok is False
    assert arg_ok is False


def test_bfcl_scoring_detects_argument_mismatch():
    fn_ok, arg_ok = calls_equivalent(
        {"name": "calc", "arguments": {"a": 1, "b": 2}},
        {"name": "calc", "arguments": {"a": 1, "b": 3}},
    )
    assert fn_ok is True
    assert arg_ok is False


def test_bfcl_smoke_covers_multi_tool_and_reject_cases():
    payload = json.loads(BFCL_SMOKE.read_text(encoding="utf-8"))
    ids = {str(c["id"]) for c in payload.get("cases") or []}
    assert "multi-tool-order" in ids
    assert "reject-harmful" in ids
    assert any(c.get("expect_no_tool") for c in payload.get("cases") or [])
