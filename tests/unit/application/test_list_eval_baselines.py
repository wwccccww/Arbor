from __future__ import annotations

from arbor.application.evaluation.list_baselines import list_eval_baselines


def test_list_eval_baselines_reads_smoke_files():
    payload = list_eval_baselines()
    ids = {item["id"] for item in payload["items"]}
    assert "agent-v1-smoke" in ids
    assert "memory-v1-smoke" in ids
    assert "multimodal-v1-smoke" in ids
    assert "agent-evolution-v1" in ids
    public = [item for item in payload["items"] if item.get("category") == "public"]
    assert any(item["id"] == "bfcl-smoke" for item in public)
    assert any(item["id"] == "agentdojo-smoke" for item in public)
    assert any(item["id"] == "multihop-smoke" for item in public)
