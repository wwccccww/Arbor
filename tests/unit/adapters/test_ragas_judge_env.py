from __future__ import annotations

import os

import pytest

from arbor.env import judge_api_key, judge_base_url, judge_embedding_model, judge_model, judge_status


def test_judge_defaults_siliconflow_friendly():
    assert judge_base_url().endswith("/v1")
    assert "Qwen" in judge_model() or judge_model()
    assert "bge" in judge_embedding_model().lower() or judge_embedding_model()


def test_judge_falls_back_to_embedding_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ARBOR_JUDGE_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("EMBEDDING_API_KEY", "silicon-key")
    assert judge_api_key() == "silicon-key"
    assert judge_status() == "configured"
