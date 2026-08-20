from __future__ import annotations

import json
from pathlib import Path

from arbor.application.evaluation.scoring import aggregate, score_case, thresholds_ok
from arbor.application.retrieval import STRATEGIES, retrieve
from arbor.domain.shared.ids import PersonaId, TenantId

DEFAULT_THRESHOLDS = {
    "k": 5,
    "retrieval": {
        "tenant_leak_count": {"max": 0},
        "persona_leak_rate": {"max": 0},
        "recall_at_5": {"min": 0.0},
        "identity_consistency": {"min": 0.0},
        "superseded_in_topk": {"max": 0},
    },
}


def evaluate_retrieval(
    *,
    strategy: str,
    cases_doc: dict,
    world: dict,
    k: int,
    list_active,
    list_events,
    summary_for,
    vector_search,
    embed,
) -> dict:
    import time

    rows = []
    for case in cases_doc["cases"]:
        actor = case["actor"]
        tenant_id = TenantId(actor["tenant_id"])
        persona_id = PersonaId(actor["persona_id"])
        started = time.perf_counter()
        retrieved = retrieve(
            strategy=strategy,
            query=case["query"],
            tenant_id=tenant_id,
            persona_id=persona_id,
            k=k,
            memories=list_active(tenant_id, persona_id),
            events=list_events(tenant_id, persona_id),
            summary=summary_for(persona_id),
            vector_search=vector_search,
            embed=embed,
        )
        retrieved["latency_ms"] = (time.perf_counter() - started) * 1000
        row = score_case(case, retrieved)
        row["actor_tenant"] = actor["tenant_id"]
        row["query"] = case["query"]
        rows.append(row)
    metrics = aggregate(rows, world)
    thresholds = world.get("_thresholds") or DEFAULT_THRESHOLDS
    checks = thresholds_ok(metrics, thresholds)
    return {
        "suite_version": cases_doc.get("suite_version") or world.get("suite_version"),
        "strategy": strategy,
        "mode": "retrieval",
        "metrics": metrics,
        "threshold_checks": checks,
        "p0_tenant_leak_zero": checks.get("tenant_leak_count", False),
        "cases": rows,
    }


def comparison_row(report: dict) -> dict:
    metrics = report["metrics"]
    return {
        "identity_consistency": metrics["identity_consistency"],
        "recall_at_5": metrics["recall_at_5"],
        "persona_leak_rate": metrics["persona_leak_rate"],
        "tenant_leak_count": metrics["tenant_leak_count"],
        "key_event_hit_rate": metrics["key_event_hit_rate"],
        "latency_ms": metrics["latency_ms"],
        "profile_miss_count": metrics["profile_miss_count"],
        "superseded_in_topk": metrics["superseded_in_topk"],
        "n_cases": metrics["n_cases"],
    }


def resolve_world_path(suite_dir: Path) -> Path:
    world = suite_dir / "world.json"
    if world.exists():
        return world
    kg = suite_dir / "knowledge_graph.json"
    if kg.exists():
        return kg
    raise FileNotFoundError(f"missing world.json or knowledge_graph.json in {suite_dir}")


def normalize_world(world: dict) -> dict:
    data = dict(world)
    if "event_nodes" not in data and "events" in data:
        data["event_nodes"] = data["events"]
    if "users" not in data:
        users = []
        seen: set[str] = set()
        for persona in data.get("personas") or []:
            uid = persona.get("user_id")
            if uid and uid not in seen:
                seen.add(uid)
                users.append({"id": uid, "tenant_id": persona["tenant_id"]})
        data["users"] = users
    return data


def normalize_cases_doc(raw) -> dict:
    if isinstance(raw, list):
        return {"suite_version": "ragas-v1", "k": 5, "cases": raw}
    if isinstance(raw, dict) and "cases" in raw:
        return raw
    raise ValueError("cases.json must be a list or an object with a cases array")


def load_suite_files(suite_dir: Path) -> tuple[dict, dict, dict, int, Path]:
    world_path = resolve_world_path(suite_dir)
    world = normalize_world(json.loads(world_path.read_text(encoding="utf-8")))
    cases_doc = normalize_cases_doc(json.loads((suite_dir / "cases.json").read_text(encoding="utf-8")))
    threshold_path = suite_dir / "thresholds.json"
    thresholds = (
        json.loads(threshold_path.read_text(encoding="utf-8"))
        if threshold_path.exists()
        else dict(DEFAULT_THRESHOLDS)
    )
    world["_thresholds"] = thresholds
    k = cases_doc.get("k") or thresholds.get("k") or 5
    return world, cases_doc, thresholds, k, world_path


def strategy_names() -> tuple[str, ...]:
    return STRATEGIES
