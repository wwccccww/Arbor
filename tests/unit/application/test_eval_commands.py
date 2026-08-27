import pytest

from arbor.adapters.outbound.inmemory import SeqIdGenerator
from arbor.application.evaluation.commands import StartEvalRun, _generation_case_view
from arbor.domain.errors import DomainError

_STUB_METRICS = {
    "identity_consistency": 1.0,
    "recall_at_5": 0.5,
    "persona_leak_rate": 0.0,
    "tenant_leak_count": 0,
    "key_event_hit_rate": 1.0,
    "latency_ms": {"retrieval": 1.0},
    "profile_miss_count": 0,
    "superseded_in_topk": 0,
    "n_cases": 1,
}


def _cmd(called: list | None = None) -> StartEvalRun:
    def run_retrieval(*, strategy: str, suite_version: str) -> dict:
        if called is not None:
            called.append((strategy, suite_version))
        return {"p0_tenant_leak_zero": True, "metrics": dict(_STUB_METRICS)}

    return StartEvalRun(run_retrieval=run_retrieval, ids=SeqIdGenerator())


def test_start_eval_requires_workspace_admin():
    with pytest.raises(DomainError) as exc:
        _cmd()(workspace_admin=False, strategy="layered_tree", suite_version="v1")
    assert exc.value.code == "FORBIDDEN_WORKSPACE"


def test_start_eval_rejects_generation_and_unknown_suite():
    cmd = _cmd()
    with pytest.raises(DomainError) as exc:
        cmd(workspace_admin=True, strategy="layered_tree", suite_version="v1", mode="generation")
    assert exc.value.code == "VALIDATION_ERROR"
    with pytest.raises(DomainError) as exc:
        cmd(workspace_admin=True, strategy="layered_tree", suite_version="v9")
    assert exc.value.code == "VALIDATION_ERROR"


def test_start_eval_runs_injected_retrieval():
    called: list = []
    result = _cmd(called)(workspace_admin=True, strategy="layered_tree", suite_version="v1")
    assert called == [("layered_tree", "v1")]
    assert result["status"] == "completed"
    assert result["metrics"]["tenant_leak_count"] == 0
    assert result["p0_tenant_leak_zero"] is True


def test_generation_case_view_marks_citation_subset_fail():
    view = _generation_case_view(
        {
            "id": "g1",
            "behavior": "cite",
            "skill": "episode_detail",
            "query": "在哪吵的？",
            "citation_subset": False,
            "leaked": False,
            "citations": ["m2", "mX"],
            "injected_memory_ids": ["m2"],
            "text": "在老张面馆。",
        }
    )
    assert view["passed"] is False
    assert view["hit_ids"] == ["m2", "mX"]
    assert view["citation_subset"] is False


def test_start_eval_generation_maps_cases():
    def run_generation(*, strategy: str, suite_version: str) -> dict:
        return {
            "p0_tenant_leak_zero": True,
            "metrics": {
                "citation_subset_rate": 1.0,
                "generation_p0_pass": True,
                "judge_status": "missing_key",
                "ragas_skipped": True,
            },
            "cases": [
                {
                    "id": "g1",
                    "behavior": "answer",
                    "skill": "profile_fact",
                    "query": "你住哪？",
                    "citation_subset": True,
                    "leaked": False,
                    "citations": ["m1"],
                    "injected_memory_ids": ["m1"],
                    "text": "住在城西。",
                }
            ],
        }

    cmd = StartEvalRun(run_retrieval=lambda **_: {}, run_generation=run_generation, ids=SeqIdGenerator())
    result = cmd(
        workspace_admin=True,
        strategy="layered_tree",
        suite_version="v1",
        mode="generation",
    )
    assert result["mode"] == "generation"
    assert result["p0_tenant_leak_zero"] is True
    assert result["cases"][0]["passed"] is True
    assert result["cases"][0]["text"] == "住在城西。"
