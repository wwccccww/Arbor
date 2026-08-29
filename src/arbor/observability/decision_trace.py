from __future__ import annotations

from datetime import UTC, datetime, timedelta

from arbor.observability.json_log import text_hash


def build_decision_trace_summary(
    *,
    retrieval_meta: dict,
    token_budget: int,
    token_estimate: int,
    injected_memory_ids: list[str],
    truncation_notes: list[str],
    reasoner_meta: dict | None,
    generation_meta: dict,
    sub_queries: list[dict] | None = None,
) -> dict:
    raw_subs = sub_queries or retrieval_meta.get("sub_queries") or []
    safe_subs = []
    for item in raw_subs:
        query = str(item.get("query") or "")
        safe_subs.append(
            {
                "intent": item.get("intent"),
                "query_hash": text_hash(query) if query else None,
            }
        )
    per_source = dict(retrieval_meta.get("per_source_counts") or {})
    hit_ids = list(retrieval_meta.get("hit_ids") or [])
    return {
        "retrieval": {
            "strategy": retrieval_meta.get("strategy"),
            "sub_queries": safe_subs,
            "candidate_count": len(hit_ids),
            "selected_count": len(injected_memory_ids),
            "per_source_counts": per_source,
            "hit_ids": hit_ids,
        },
        "context": {
            "token_budget": token_budget,
            "token_estimate": token_estimate,
            "injected_memory_ids": list(injected_memory_ids),
            "truncation_notes": list(truncation_notes),
        },
        "reasoner": reasoner_meta or {"called": False},
        "generation": generation_meta,
    }


def decision_trace_expires_at(retention_days: int) -> str:
    expires = datetime.now(UTC) + timedelta(days=max(1, retention_days))
    return expires.isoformat().replace("+00:00", "Z")
