from __future__ import annotations

import json

from arbor.adapters.outbound.benchmarks.bfcl_loader import BFCL_DEV, load_dev_cases
from arbor.application.evaluation.public_benchmarks.bfcl_runner import run_bfcl_dev
from arbor.paths import repo_root

BASELINE = repo_root() / "eval" / "public" / "baselines" / "bfcl-dev-fake.json"


def test_bfcl_dev_fixture_is_official_subset():
    payload = load_dev_cases()
    assert len(payload["cases"]) == 200
    cats = {c["source_category"] for c in payload["cases"]}
    assert cats == {"simple", "multiple", "parallel", "irrelevance"}
    assert all(c.get("metadata", {}).get("official") for c in payload["cases"])


def test_bfcl_dev_fake_matches_baseline():
    live = run_bfcl_dev(fixture_path=BFCL_DEV, planner_kind="fake")
    assert BASELINE.is_file(), "run bfcl dev fake once to freeze baseline"
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert live.get("task_success_rate") == baseline.get("task_success_rate")
    assert live.get("function_match_rate") == baseline.get("function_match_rate")
    assert live.get("argument_match_rate") == baseline.get("argument_match_rate")
    for case in live.get("cases") or []:
        assert case.get("ok") is True, case
