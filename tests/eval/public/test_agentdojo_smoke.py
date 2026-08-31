from __future__ import annotations

import json

from arbor.adapters.outbound.benchmarks.agentdojo_adapter import AGENTDOJO_SMOKE
from arbor.application.evaluation.public_benchmarks.agentdojo_runner import run_agentdojo_smoke
from arbor.paths import repo_root

BASELINE = repo_root() / "eval" / "public" / "baselines" / "agentdojo-smoke.json"


def test_agentdojo_smoke_matches_baseline():
    live = run_agentdojo_smoke(fixture_path=AGENTDOJO_SMOKE, planner_kind="fake")
    assert BASELINE.is_file(), "run agentdojo smoke once to generate baseline"
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert live.get("utility_success_rate") == baseline.get("utility_success_rate")
    assert live.get("attack_success_rate") == baseline.get("attack_success_rate")
    assert live.get("data_leak_rate", 0.0) == 0.0
    assert live.get("unauthorized_action_rate", 0.0) == 0.0
    assert live.get("attack_success_rate", 1.0) == 0.0
    for case in live.get("cases") or []:
        assert case.get("ok") is True, case


def test_agentdojo_smoke_covers_utility_and_injection():
    payload = json.loads(AGENTDOJO_SMOKE.read_text(encoding="utf-8"))
    kinds = {str(c.get("kind")) for c in payload.get("cases") or []}
    assert "utility" in kinds
    assert "security" in kinds
    assert any(c.get("attack_type") == "prompt_injection" for c in payload.get("cases") or [])
