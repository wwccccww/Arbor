from __future__ import annotations

from arbor.observability.eval_metrics import export_eval_run_metrics, record_citation_violation
from arbor.observability.memory import InMemoryObservability


def test_export_eval_run_metrics_sets_gauges():
    obs = InMemoryObservability()
    export_eval_run_metrics(
        obs,
        suite="v1",
        strategy="layered_tree",
        metrics={"recall_at_5": 0.8, "p0_tenant_leak_zero": True},
        p0_tenant_leak_zero=True,
    )
    assert any(name == "arbor_eval_metric" for name, _, _ in obs.gauges)
    assert not any(name == "arbor_tenant_leak_total" for name, _, _ in obs.counters)


def test_export_eval_run_metrics_increments_tenant_leak():
    obs = InMemoryObservability()
    export_eval_run_metrics(
        obs,
        suite="v1",
        strategy="layered_tree",
        metrics={"recall_at_5": 0.2},
        p0_tenant_leak_zero=False,
    )
    assert any(name == "arbor_tenant_leak_total" for name, _, _ in obs.counters)


def test_export_eval_run_metrics_sets_persona_leak_gauge():
    obs = InMemoryObservability()
    export_eval_run_metrics(
        obs,
        suite="v1",
        strategy="layered_tree",
        metrics={"persona_leak_rate": 0.0, "recall_at_5": 0.9},
        p0_tenant_leak_zero=True,
    )
    assert any(name == "arbor_persona_leak_rate" for name, _, _ in obs.gauges)


def test_record_citation_violation():
    obs = InMemoryObservability()
    record_citation_violation(obs, count=2)
    match = next(item for item in obs.counters if item[0] == "arbor_citation_out_of_injection_total")
    assert match[1] == 2.0
