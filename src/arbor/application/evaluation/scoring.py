from __future__ import annotations

from collections import defaultdict


def score_case(case: dict, retrieved: dict) -> dict:
    hit_ids = list(retrieved["hit_ids"])
    injected_hit_ids = list(
        retrieved.get("injected_hit_ids")
        or [memory.id.value for memory in retrieved.get("hits") or []]
    )
    expected = list(case.get("expected_memory_ids") or [])
    forbidden = list(case.get("forbidden_memory_ids") or [])
    leak_ids = [i for i in hit_ids if i in forbidden]
    recall = 1.0 if not expected else len([i for i in expected if i in hit_ids]) / len(expected)
    injected_recall = (
        1.0
        if not expected
        else len([i for i in expected if i in injected_hit_ids]) / len(expected)
    )
    expected_event = case.get("expected_event_id")
    event_ids = [e.id.value for e in retrieved.get("event_nodes") or []]
    mem_events = [m.event_id.value for m in retrieved.get("hits") or [] if m.event_id]
    event_hit = True
    if expected_event:
        event_hit = expected_event in event_ids or expected_event in mem_events
    profile_ids = {m.id.value for m in retrieved.get("profile_hits") or []}
    profile_miss = False
    if case.get("expected_source") == "profile" and expected:
        profile_miss = any(mid not in profile_ids for mid in expected)
    return {
        "id": case["id"],
        "hit_ids": hit_ids,
        "injected_hit_ids": injected_hit_ids,
        "recall": recall,
        "injected_recall": injected_recall,
        "leak_ids": leak_ids,
        "leaked": bool(leak_ids),
        "event_hit": event_hit,
        "profile_miss": profile_miss,
        "skill": case.get("skill"),
        "expected_source": case.get("expected_source"),
        "expected_memory_ids": expected,
        "expected_event_id": expected_event,
        "repeat": case.get("repeat", 1),
        "behavior": case.get("expected_behavior"),
        "sources": retrieved.get("sources", {}),
        "latency_ms": retrieved.get("latency_ms", 0.0),
    }


def aggregate(rows: list[dict], world: dict) -> dict:
    memories = {m["id"]: m for m in world["memories"]}
    superseded_ids = {m["id"] for m in world["memories"] if m.get("status") == "superseded"}

    tenant_leaks = 0
    superseded_in_topk = 0
    for row in rows:
        actor_tenant = row.get("actor_tenant")
        for mid in row["hit_ids"]:
            if mid in superseded_ids:
                superseded_in_topk += 1
            mem = memories.get(mid)
            if mem and actor_tenant and mem["tenant_id"] != actor_tenant:
                tenant_leaks += 1

    isolation = [r for r in rows if r["skill"] in {"persona_isolation", "tenant_isolation"}]
    persona_leaks = sum(1 for r in isolation if r["leaked"])
    rec_vals = [r["recall"] for r in rows if r["expected_memory_ids"]]
    injected_rec_vals = [r["injected_recall"] for r in rows if r["expected_memory_ids"]]
    identity: list[float] = []
    key_event: list[float] = []
    for row in rows:
        if row["skill"] == "profile_fact":
            identity.extend([1.0 if row["recall"] >= 1.0 else 0.0] * max(1, row.get("repeat") or 1))
        if row["expected_source"] == "event_tree":
            key_event.append(1.0 if row["event_hit"] else 0.0)

    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    by_skill: dict[str, dict] = {}
    buckets: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "recall_sum": 0.0, "injected_recall_sum": 0.0, "with_expected": 0, "leaks": 0}
    )
    for row in rows:
        skill = row.get("skill") or "unknown"
        bucket = buckets[skill]
        bucket["n"] += 1
        if row["expected_memory_ids"]:
            bucket["with_expected"] += 1
            bucket["recall_sum"] += row["recall"]
            bucket["injected_recall_sum"] += row["injected_recall"]
        if row["leaked"]:
            bucket["leaks"] += 1
    for skill, bucket in sorted(buckets.items()):
        by_skill[skill] = {
            "n": bucket["n"],
            "recall_at_5": round(bucket["recall_sum"] / bucket["with_expected"], 4) if bucket["with_expected"] else None,
            "injected_recall_at_5": round(bucket["injected_recall_sum"] / bucket["with_expected"], 4)
            if bucket["with_expected"]
            else None,
            "leak_cases": bucket["leaks"],
        }
    return {
        "tenant_leak_count": tenant_leaks,
        "persona_leak_rate": round(persona_leaks / len(isolation), 4) if isolation else 0.0,
        "recall_at_5": round(sum(rec_vals) / len(rec_vals), 4) if rec_vals else 0.0,
        "injected_recall_at_5": round(sum(injected_rec_vals) / len(injected_rec_vals), 4)
        if injected_rec_vals
        else 0.0,
        "identity_consistency": round(sum(identity) / len(identity), 4) if identity else 1.0,
        "key_event_hit_rate": round(sum(key_event) / len(key_event), 4) if key_event else 0.0,
        "superseded_in_topk": superseded_in_topk,
        "n_cases": len(rows),
        "n_leaking_cases": sum(1 for r in rows if r["leaked"]),
        "profile_miss_count": sum(1 for r in rows if r["profile_miss"]),
        "latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "by_skill": by_skill,
    }


def thresholds_ok(metrics: dict, thresholds: dict) -> dict:
    retrieval = thresholds.get("retrieval", {})
    checks = {}
    leak = retrieval.get("tenant_leak_count", {})
    checks["tenant_leak_count"] = metrics["tenant_leak_count"] <= leak.get("max", 0)
    pl = retrieval.get("persona_leak_rate", {})
    checks["persona_leak_rate"] = metrics["persona_leak_rate"] <= pl.get("max", 0)
    rec = retrieval.get("recall_at_5", {})
    checks["recall_at_5"] = metrics["recall_at_5"] >= rec.get("min", 0)
    ident = retrieval.get("identity_consistency", {})
    checks["identity_consistency"] = metrics["identity_consistency"] >= ident.get("min", 0)
    sup = retrieval.get("superseded_in_topk", {})
    checks["superseded_in_topk"] = metrics["superseded_in_topk"] <= sup.get("max", 0)
    return checks
