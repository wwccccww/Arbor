import os

import pytest

from arbor.env import chat_api_key

pytestmark = pytest.mark.llm


@pytest.mark.skipif(not chat_api_key(), reason="generation tests need DEEPSEEK_API_KEY")
@pytest.mark.skipif(not os.environ.get("ARBOR_JUDGE_API_KEY"), reason="RAGAS judge key required")
def test_ragas_official_generation_full_metrics_when_judge_configured():
    from arbor.adapters.inbound.eval_runner import run_ragas_official_generation

    report = run_ragas_official_generation(backend="memory", case_limit=3)
    metrics = report["metrics"]
    assert metrics["ragas_skipped"] is False
    assert metrics["judge_status"] == "configured"
    assert metrics["ragas_n"] >= 3
    assert metrics["ragas_faithfulness"] is not None
    assert metrics["ragas_context_recall"] is not None
    assert metrics["ragas_answer_correctness"] is not None
    assert metrics["citation_subset_rate"] == 1.0
