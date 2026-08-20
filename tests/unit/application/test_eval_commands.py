import pytest

from arbor.adapters.outbound.inmemory import SeqIdGenerator
from arbor.application.evaluation.commands import StartEvalRun
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
