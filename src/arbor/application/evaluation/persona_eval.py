from __future__ import annotations

import time

from arbor.application.evaluation.scoring import aggregate, score_case
from arbor.application.retrieval import retrieve
from arbor.domain.shared.ids import PersonaId, TenantId


def run_persona_retrieval_eval(
    *,
    tenant_id: TenantId,
    persona_id: PersonaId,
    strategy: str,
    cases: list[dict],
    list_active,
    list_events,
    summary_for,
    vector_search,
    embed,
    k: int = 5,
    memory_catalog: list[dict],
    list_edges=None,
    lexical_search=None,
) -> dict:
    rows = []
    for case in cases:
        actor = case["actor"]
        case_tenant = TenantId(actor["tenant_id"])
        case_persona = PersonaId(actor["persona_id"])
        started = time.perf_counter()
        retrieved = retrieve(
            strategy=strategy,
            query=case["query"],
            tenant_id=case_tenant,
            persona_id=case_persona,
            k=k,
            memories=list_active(case_tenant, case_persona),
            events=list_events(case_tenant, case_persona),
            edges=list_edges(case_tenant, case_persona) if list_edges else None,
            summary=summary_for(case_persona),
            vector_search=vector_search,
            embed=embed,
            lexical_search=lexical_search,
        )
        retrieved["latency_ms"] = (time.perf_counter() - started) * 1000
        row = score_case(case, retrieved)
        row["actor_tenant"] = actor["tenant_id"]
        row["query"] = case["query"]
        row["persona_id"] = actor["persona_id"]
        rows.append(row)

    world = {"memories": memory_catalog}
    metrics = aggregate(rows, world)
    return {
        "suite_version": "persona",
        "strategy": strategy,
        "mode": "retrieval",
        "metrics": metrics,
        "p0_tenant_leak_zero": metrics.get("tenant_leak_count", 0) == 0,
        "cases": rows,
        "persona_id": persona_id.value,
    }
