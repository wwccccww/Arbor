from __future__ import annotations

from arbor.env import judge_base_url, judge_embedding_model, judge_model


def test_judge_defaults_siliconflow_friendly():
    assert judge_base_url().endswith("/v1")
    assert "Qwen" in judge_model() or judge_model()
    assert "bge" in judge_embedding_model().lower() or judge_embedding_model()
