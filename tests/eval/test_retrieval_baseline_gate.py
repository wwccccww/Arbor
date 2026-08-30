"""Gate: suite-v1 layered_tree in-memory metrics must not regress frozen baseline."""

from __future__ import annotations

import json

from arbor.adapters.inbound.eval_runner import ROOT, run_suite
from arbor.paths import repo_root


def test_suite_v1_layered_tree_meets_frozen_baseline():
    report = run_suite(
        suite_dir=ROOT / "eval/fixtures/suite-v1",
        strategy="layered_tree",
        backend="memory",
    )
    baseline_path = repo_root() / "eval/baselines/suite-v1.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    frozen = baseline["strategies"]["layered_tree"]
    metrics = report["metrics"]

    assert report["p0_tenant_leak_zero"] is True
    assert metrics["tenant_leak_count"] == 0
    assert metrics["persona_leak_rate"] <= frozen["persona_leak_rate"]
    assert metrics["recall_at_5"] >= frozen["recall_at_5"]
    assert metrics["identity_consistency"] >= frozen["identity_consistency"]
    assert metrics["superseded_in_topk"] <= frozen["superseded_in_topk"]
