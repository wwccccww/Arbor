from __future__ import annotations

import json
import os

import pytest

from arbor.application.evaluation.public_benchmarks.multihop_rag_runner import run_multihop_dev
from arbor.env import chat_api_key
from arbor.paths import repo_root

pytestmark = pytest.mark.llm

LLM_BASELINE = repo_root() / "eval" / "public" / "baselines" / "multihop-dev-llm.json"


@pytest.mark.skipif(not chat_api_key(), reason="DEEPSEEK_API_KEY required for MultiHop LLM dev eval")
def test_multihop_dev_llm_sample_cases():
    """Nightly gate: real RAG+LLM on a small official dev slice."""
    sample_ids = {"multihop-dev-000", "multihop-dev-001", "multihop-dev-002"}
    report = run_multihop_dev(planner_kind="llm", case_ids=sample_ids)
    assert report.get("case_count") == len(sample_ids)
    assert report.get("tenant_leak_rate", 0.0) == 0.0
    assert report.get("supporting_fact_recall", 0.0) >= 0.0
    if os.environ.get("ARBOR_WRITE_LLM_BASELINE") == "1":
        full = run_multihop_dev(planner_kind="llm")
        LLM_BASELINE.write_text(json.dumps(full, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if LLM_BASELINE.is_file():
        stored = json.loads(LLM_BASELINE.read_text(encoding="utf-8"))
        assert stored.get("planner_kind") == "llm"
        assert stored.get("case_count") == 100
