from __future__ import annotations

RAGAS_METRIC_KEYS: tuple[str, ...] = (
    "ragas_faithfulness",
    "ragas_context_recall",
    "ragas_context_precision",
    "ragas_answer_relevancy",
    "ragas_answer_correctness",
)


def injected_contexts(prompt_slots: dict) -> list[str]:
    contexts: list[str] = []
    profile = prompt_slots.get("profile") or {}
    if profile:
        contexts.append("档案: " + " ".join(f"{k}={v}" for k, v in profile.items() if v))
    summary = prompt_slots.get("thread_summary") or ""
    if summary:
        contexts.append("摘要: " + summary)
    for event in prompt_slots.get("event_hits") or []:
        if isinstance(event, dict):
            contexts.append(f"事件: {event.get('title', '')} {event.get('summary', '')}".strip())
        else:
            contexts.append(f"事件: {event}")
    for memory in prompt_slots.get("memory_hits") or []:
        if isinstance(memory, dict):
            text = str(memory.get("text") or "").strip()
            memory_id = memory.get("id")
            if text:
                if memory_id:
                    contexts.append(f"记忆 {memory_id}: {text}")
                else:
                    contexts.append(text)
        elif memory:
            contexts.append(str(memory))
    for turn in prompt_slots.get("recent_turns") or []:
        if isinstance(turn, dict):
            role = turn.get("role") or "user"
            content = (turn.get("content") or "").strip()
            if content:
                contexts.append(f"近期对话 {role}: {content}")
    return contexts


def _ngrams(text: str, size: int = 8) -> set[str]:
    compact = "".join(text.split())
    if len(compact) < size:
        return {compact} if compact else set()
    return {compact[i : i + size] for i in range(len(compact) - size + 1)}


def forbidden_text_leaked(answer: str, forbidden_texts: list[str], query: str) -> bool:
    if not answer:
        return False
    answer_grams = _ngrams(answer)
    query_grams = _ngrams(query)
    for text in forbidden_texts:
        private = _ngrams(text) - query_grams
        if private and private & answer_grams:
            return True
    return False


def score_generation_case(case: dict, result: dict, memories: dict[str, dict]) -> dict:
    injected = list(result.get("injected_memory_ids") or [])
    citations = list(result.get("citations") or [])
    subset = set(citations) <= set(injected)
    forbidden_ids = list(case.get("forbidden_memory_ids") or [])
    forbidden_texts = [memories[mid]["text"] for mid in forbidden_ids if mid in memories]
    text_leak = forbidden_text_leaked(result.get("text") or "", forbidden_texts, case.get("query") or "")
    retrieval_leak = bool(result.get("leak_ids"))
    leaked = text_leak or retrieval_leak
    behavior = case.get("expected_behavior")
    ragas_fields: dict[str, float | None] = {}
    for key in RAGAS_METRIC_KEYS:
        value = result.get(key)
        if leaked or behavior == "refuse":
            value = None
        ragas_fields[key] = value
    return {
        "id": case["id"],
        "behavior": behavior,
        "skill": case.get("skill"),
        "citation_subset": subset,
        "text_leak": text_leak,
        "retrieval_leak": retrieval_leak,
        "leaked": leaked,
        "ragas_faithfulness": ragas_fields.get("ragas_faithfulness"),
        **ragas_fields,
        "injected_memory_ids": injected,
        "citations": citations,
    }


def generation_p0_pass(metrics: dict) -> bool:
    """P0 for generation: no leaks and citation subset on answer/cite cases."""
    if metrics.get("n_leaking_cases", 0) != 0:
        return False
    if metrics.get("refuse_text_leak_count", 0) != 0:
        return False
    return metrics.get("citation_subset_rate", 1.0) >= 1.0


def _finite_scores(rows: list[dict], key: str) -> list[float]:
    import math

    out: list[float] = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            out.append(number)
    return out


def aggregate_generation(rows: list[dict]) -> dict:
    from arbor.env import judge_status

    cite_rows = [r for r in rows if r["behavior"] in {"answer", "cite"}]
    subset_rate = (
        sum(1 for r in cite_rows if r["citation_subset"]) / len(cite_rows) if cite_rows else 1.0
    )
    refuse_rows = [r for r in rows if r["behavior"] == "refuse"]
    ragas_vals = _finite_scores(rows, "ragas_faithfulness")
    metrics = {
        "n_cases": len(rows),
        "citation_subset_rate": round(subset_rate, 4),
        "refuse_text_leak_count": sum(1 for r in refuse_rows if r["text_leak"]),
        "n_leaking_cases": sum(1 for r in rows if r["leaked"]),
        "ragas_faithfulness": round(sum(ragas_vals) / len(ragas_vals), 4) if ragas_vals else None,
        "ragas_n": len(ragas_vals),
        "ragas_skipped": len(ragas_vals) == 0,
        "judge_status": judge_status(),
    }
    for key in RAGAS_METRIC_KEYS:
        short = key.removeprefix("ragas_")
        vals = _finite_scores(rows, key)
        metrics[key] = round(sum(vals) / len(vals), 4) if vals else None
        metrics[f"ragas_{short}_n"] = len(vals)
    if any(metrics.get(key) is not None for key in RAGAS_METRIC_KEYS):
        metrics["ragas_skipped"] = False
    metrics["generation_p0_pass"] = generation_p0_pass(metrics)
    return metrics
