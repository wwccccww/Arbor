from __future__ import annotations

import json
import os

import pytest

from arbor.application.evaluation.public_benchmarks.bfcl_runner import run_bfcl_dev
from arbor.env import chat_api_key
from arbor.paths import repo_root

pytestmark = pytest.mark.llm

LLM_BASELINE = repo_root() / "eval" / "public" / "baselines" / "bfcl-dev-llm.json"


@pytest.mark.skipif(not chat_api_key(), reason="DEEPSEEK_API_KEY required for BFCL LLM dev eval")
def test_bfcl_dev_llm_sample_cases():
    """Nightly gate: real LLM on a small official dev slice (not full 200 in PR)."""
    sample_ids = {"simple_0", "simple_1", "irrelevance_0", "multiple_0", "parallel_0"}
    report = run_bfcl_dev(planner_kind="llm", case_ids=sample_ids)
    assert report.get("case_count") == len(sample_ids)
    assert report.get("unauthorized_action_rate", 0.0) == 0.0
    if os.environ.get("ARBOR_WRITE_LLM_BASELINE") == "1":
        full = run_bfcl_dev(planner_kind="llm")
        LLM_BASELINE.write_text(json.dumps(full, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if LLM_BASELINE.is_file():
        stored = json.loads(LLM_BASELINE.read_text(encoding="utf-8"))
        assert stored.get("planner_kind") == "llm"
        assert stored.get("case_count") == 200
        assert stored.get("function_match_rate", 0.0) > 0.0
        assert stored.get("task_success_rate", 0.0) >= 0.68
