"""RAGAS official tuning: retrieval presets, stratified metrics, ablation helpers."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from arbor.application.evaluation.generation import RAGAS_METRIC_KEYS, aggregate_generation
from arbor.application.retrieval_config import RetrievalConfig

EVOLUTION_SINGLE = "single_hop_specifc_query_synthesizer"
EVOLUTION_MULTI = "multi_hop_specific_query_synthesizer"
EVOLUTION_LABELS = {
    EVOLUTION_SINGLE: "single_hop",
    EVOLUTION_MULTI: "multi_hop",
}

PRIMARY_RAGAS_METRICS: tuple[str, ...] = (
    "ragas_faithfulness",
    "ragas_context_recall",
    "ragas_context_precision",
    "ragas_answer_correctness",
)
REFERENCE_RAGAS_METRICS: tuple[str, ...] = ("ragas_answer_relevancy",)

RETRIEVAL_PRESET_ENV: dict[str, dict[str, str]] = {
    "default": {},
    "tuned": {
        "ARBOR_RETRIEVAL_PROMPT_K": "3",
        "ARBOR_RETRIEVAL_MMR_LAMBDA": "0.85",
        "ARBOR_RETRIEVAL_RERANK_K": "4",
        "ARBOR_RETRIEVAL_POOL_K": "20",
    },
}


def resolve_retrieval_config(preset: str | None) -> RetrievalConfig:
    if preset in {None, "", "default"}:
        return RetrievalConfig.from_env()
    if preset == "tuned":
        return RetrievalConfig.ragas_tuned()
    raise ValueError(f"unknown ragas retrieval preset: {preset}")


@contextmanager
def apply_retrieval_preset(preset: str) -> Iterator[None]:
    """Temporarily set env vars for retrieval ablation arms."""
    overrides = RETRIEVAL_PRESET_ENV.get(preset, {})
    if not overrides:
        yield
        return
    saved = {key: os.environ.get(key) for key in overrides}
    try:
        os.environ.update(overrides)
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def cases_by_id(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(case["id"]): case for case in cases}


def enrich_rows_with_case_meta(rows: list[dict[str, Any]], case_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        case = case_index.get(str(row.get("id") or row.get("case_id") or "")) or {}
        evolution = case.get("evolution_type")
        item = dict(row)
        item["evolution_type"] = evolution
        item["evolution_label"] = EVOLUTION_LABELS.get(str(evolution or ""), "other")
        item["query"] = item.get("query") or case.get("query")
        item["reference"] = item.get("reference") or case.get("reference")
        enriched.append(item)
    return enriched


def aggregate_generation_by_evolution(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        label = str(row.get("evolution_label") or "other")
        buckets.setdefault(label, []).append(row)
    return {label: aggregate_generation(bucket_rows) for label, bucket_rows in sorted(buckets.items())}


def _row_ragas_score(row: dict[str, Any]) -> float:
    values: list[float] = []
    for key in PRIMARY_RAGAS_METRICS:
        raw = row.get(key)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not values:
        return 0.0
    return sum(values) / len(values)


def worst_ragas_cases(rows: list[dict[str, Any]], *, limit: int = 20) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        if row.get("leaked"):
            continue
        scored.append((_row_ragas_score(row), row))
    scored.sort(key=lambda item: item[0])
    worst: list[dict[str, Any]] = []
    for avg, row in scored[:limit]:
        worst.append(
            {
                "id": row.get("id") or row.get("case_id"),
                "evolution_label": row.get("evolution_label"),
                "query": row.get("query"),
                "reference": row.get("reference"),
                "text": row.get("text"),
                "avg_primary_ragas": round(avg, 4),
                **{key: row.get(key) for key in RAGAS_METRIC_KEYS},
            }
        )
    return worst


def run_ragas_retrieval_ablation(
    *,
    backend: str = "memory",
    embed: str = "fixture",
    strategy: str = "layered_tree",
) -> dict[str, dict[str, Any]]:
    """Compare default vs tuned retrieval on frozen ragas-official cases (no LLM)."""
    from arbor.adapters.inbound.eval_runner import ROOT, run_suite

    suite_dir = ROOT / "eval" / "fixtures" / "suite-ragas-official"
    results: dict[str, dict[str, Any]] = {}
    for preset in ("default", "tuned"):
        with apply_retrieval_preset(preset):
            report = run_suite(suite_dir=suite_dir, strategy=strategy, backend=backend, embed=embed)
            metrics = dict(report.get("metrics") or {})
            results[preset] = {
                "recall_at_5": metrics.get("recall_at_5"),
                "mrr_at_5": metrics.get("mrr_at_5"),
                "tenant_leak_count": metrics.get("tenant_leak_count"),
                "n_cases": metrics.get("n_cases"),
            }
    return results


def build_ragas_report_extras(
    rows: list[dict[str, Any]],
    *,
    case_index: dict[str, dict[str, Any]],
    worst_n: int = 20,
) -> dict[str, Any]:
    enriched = enrich_rows_with_case_meta(rows, case_index)
    return {
        "by_evolution": aggregate_generation_by_evolution(enriched),
        "worst_cases": worst_ragas_cases(enriched, limit=worst_n),
        "primary_metrics": list(PRIMARY_RAGAS_METRICS),
        "reference_metrics": list(REFERENCE_RAGAS_METRICS),
    }
