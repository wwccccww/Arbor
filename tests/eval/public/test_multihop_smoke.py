from __future__ import annotations

import json

from arbor.adapters.outbound.benchmarks.multihop_loader import (
    MULTIHOP_SMOKE,
    answer_em,
    answer_f1,
    supporting_fact_recall,
)
from arbor.application.evaluation.public_benchmarks.multihop_rag_runner import run_multihop_smoke
from arbor.paths import repo_root

BASELINE = repo_root() / "eval" / "public" / "baselines" / "multihop-smoke.json"


def test_multihop_smoke_matches_baseline():
    live = run_multihop_smoke(fixture_path=MULTIHOP_SMOKE, planner_kind="fake")
    assert BASELINE.is_file(), "run multihop smoke once to generate baseline"
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert live.get("supporting_fact_recall") == baseline.get("supporting_fact_recall")
    assert live.get("answer_em") == baseline.get("answer_em")
    assert live.get("answer_f1") == baseline.get("answer_f1")
    assert live.get("faithfulness") == baseline.get("faithfulness")
    assert live.get("tenant_leak_rate", 0.0) == 0.0
    for case in live.get("cases") or []:
        assert case.get("ok") is True, case


def test_multihop_scoring_helpers():
    assert answer_em("Jane Doe", "jane doe") == 1.0
    assert answer_f1("Austin Texas", "Austin") > 0.0
    assert supporting_fact_recall(expected_ids=["a", "b"], retrieved_ids=["a", "c"]) == 0.5


def test_multihop_smoke_has_multi_hop_and_isolation():
    payload = json.loads(MULTIHOP_SMOKE.read_text(encoding="utf-8"))
    ids = {str(c["id"]) for c in payload.get("cases") or []}
    assert "hop-3-labs-city" in ids
    assert "hop-tenant-isolation" in ids
    assert len(payload.get("corpus") or []) >= 10
