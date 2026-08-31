from __future__ import annotations

import json

from arbor.adapters.outbound.benchmarks.multihop_loader import MULTIHOP_DEV, load_dev_cases
from arbor.application.evaluation.public_benchmarks.multihop_rag_runner import run_multihop_dev
from arbor.paths import repo_root

BASELINE = repo_root() / "eval" / "public" / "baselines" / "multihop-dev-fake.json"


def test_multihop_dev_fixture_is_official_subset():
    payload = load_dev_cases()
    assert len(payload["cases"]) == 100
    assert len(payload.get("corpus") or []) >= 100
    assert all(c.get("metadata", {}).get("official") for c in payload["cases"])
    types = {str(c.get("question_type")) for c in payload["cases"]}
    assert types == {"inference_query", "comparison_query", "temporal_query", "null_query"}


def test_multihop_dev_fake_matches_baseline():
    live = run_multihop_dev(fixture_path=MULTIHOP_DEV, planner_kind="fake")
    assert BASELINE.is_file(), "run multihop dev fake once to freeze baseline"
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert live.get("supporting_fact_recall") == baseline.get("supporting_fact_recall")
    assert live.get("answer_em") == baseline.get("answer_em")
    assert live.get("faithfulness") == baseline.get("faithfulness")
    assert live.get("tenant_leak_rate", 0.0) == 0.0
    for case in live.get("cases") or []:
        assert case.get("ok") is True, case
