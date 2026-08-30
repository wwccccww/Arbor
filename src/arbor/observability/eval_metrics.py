from __future__ import annotations

from arbor.observability.helpers import obs_or_noop


def export_eval_run_metrics(
    observability: object | None,
    *,
    suite: str,
    strategy: str,
    metrics: dict[str, object] | None,
    p0_tenant_leak_zero: bool | None = None,
) -> None:
    obs = obs_or_noop(observability)
    for name, raw in (metrics or {}).items():
        if isinstance(raw, bool):
            value = 1.0 if raw else 0.0
        elif isinstance(raw, (int, float)):
            value = float(raw)
        else:
            continue
        obs.set_gauge(
            "arbor_eval_metric",
            value,
            suite=suite,
            strategy=strategy,
            metric_name=str(name),
        )
        if name == "persona_leak_rate":
            obs.set_gauge(
                "arbor_persona_leak_rate",
                value,
                suite=suite,
                strategy=strategy,
            )
    if p0_tenant_leak_zero is False:
        obs.increment("arbor_tenant_leak_total", 1.0)


def record_citation_violation(observability: object | None, *, count: int = 1) -> None:
    if count <= 0:
        return
    obs_or_noop(observability).increment("arbor_citation_out_of_injection_total", float(count))
