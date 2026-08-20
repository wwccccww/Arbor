import os

import pytest

from arbor.env import chat_api_key


pytestmark = pytest.mark.llm


@pytest.mark.skipif(not chat_api_key(), reason="generation tests need DEEPSEEK_API_KEY")
def test_suite_v1_generation_citation_subset_and_no_refuse_leak():
    from arbor.adapters.inbound.eval_runner import ROOT, run_generation

    report = run_generation(suite_dir=ROOT / "eval/fixtures/suite-v1", strategy="layered_tree")
    metrics = report["metrics"]
    assert metrics["citation_subset_rate"] == 1.0
    assert metrics["refuse_text_leak_count"] == 0
    assert metrics["n_leaking_cases"] == 0
    assert metrics["n_cases"] == 13
    # RAGAS needs a separate judge key; same-model scoring is skipped on purpose.
    if not os.environ.get("ARBOR_JUDGE_API_KEY"):
        assert metrics["ragas_skipped"] is True
