from __future__ import annotations

from dataclasses import asdict

from arbor.application.evaluation.public_benchmarks.port import PublicBenchmarkResult


def aggregate_public_benchmark(
    *,
    benchmark_id: str,
    version: str,
    planner_kind: str,
    results: list[PublicBenchmarkResult],
    extra: dict | None = None,
) -> dict:
    total = len(results)
    if total == 0:
        return {
            "benchmark_id": benchmark_id,
            "version": version,
            "planner_kind": planner_kind,
            "case_count": 0,
            "function_match_rate": 0.0,
            "argument_match_rate": 0.0,
            "executable_rate": 0.0,
            "cases": [],
        }

    function_hits = sum(r.scores.get("function_match", 0.0) for r in results)
    argument_hits = sum(r.scores.get("argument_match", 0.0) for r in results)
    executable_hits = sum(r.scores.get("executable", 0.0) for r in results)
    success = sum(1 for r in results if r.ok)

    payload = {
        "benchmark_id": benchmark_id,
        "version": version,
        "planner_kind": planner_kind,
        "case_count": total,
        "task_success_rate": success / total,
        "function_match_rate": function_hits / total,
        "argument_match_rate": argument_hits / total,
        "executable_rate": executable_hits / total,
        "unauthorized_action_rate": 0.0,
        "approval_bypass_rate": 0.0,
        "cases": [
            {
                "id": r.case_id,
                "ok": r.ok,
                "scores": r.scores,
                "detail": r.detail,
                "security_violations": list(r.security_violations),
            }
            for r in results
        ],
    }
    if extra:
        payload.update(extra)
    return payload


def result_to_dict(result: PublicBenchmarkResult) -> dict:
    return asdict(result)


def _case_rows(results: list[PublicBenchmarkResult]) -> list[dict]:
    return [
        {
            "id": r.case_id,
            "ok": r.ok,
            "scores": r.scores,
            "detail": r.detail,
            "security_violations": list(r.security_violations),
        }
        for r in results
    ]


def aggregate_agentdojo(
    *,
    benchmark_id: str,
    version: str,
    planner_kind: str,
    results: list[PublicBenchmarkResult],
    extra: dict | None = None,
) -> dict:
    total = len(results)
    if total == 0:
        payload = {
            "benchmark_id": benchmark_id,
            "version": version,
            "planner_kind": planner_kind,
            "case_count": 0,
            "utility_success_rate": 0.0,
            "attack_success_rate": 0.0,
            "data_leak_rate": 0.0,
            "unauthorized_action_rate": 0.0,
            "cases": [],
        }
        if extra:
            payload.update(extra)
        return payload

    utility_results = [r for r in results if r.actual.get("kind") == "utility"]
    security_results = [r for r in results if r.actual.get("kind") == "security"]
    utility_hits = sum(r.scores.get("utility_success", 0.0) for r in utility_results)
    attack_hits = sum(r.scores.get("attack_success", 0.0) for r in security_results)
    data_leak = sum(r.scores.get("data_leak", 0.0) for r in results)
    unauthorized = sum(r.scores.get("unauthorized_action", 0.0) for r in results)
    success = sum(1 for r in results if r.ok)

    payload = {
        "benchmark_id": benchmark_id,
        "version": version,
        "planner_kind": planner_kind,
        "case_count": total,
        "task_success_rate": success / total,
        "utility_success_rate": utility_hits / max(len(utility_results), 1),
        "attack_success_rate": attack_hits / max(len(security_results), 1),
        "data_leak_rate": data_leak / total,
        "unauthorized_action_rate": unauthorized / total,
        "utility_cases": len(utility_results),
        "security_cases": len(security_results),
        "cases": _case_rows(results),
    }
    if extra:
        payload.update(extra)
    return payload


def aggregate_multihop(
    *,
    benchmark_id: str,
    version: str,
    planner_kind: str,
    results: list[PublicBenchmarkResult],
    extra: dict | None = None,
) -> dict:
    total = len(results)
    if total == 0:
        payload = {
            "benchmark_id": benchmark_id,
            "version": version,
            "planner_kind": planner_kind,
            "case_count": 0,
            "supporting_fact_recall": 0.0,
            "answer_em": 0.0,
            "answer_f1": 0.0,
            "citation_precision": 0.0,
            "citation_recall": 0.0,
            "faithfulness": 0.0,
            "tenant_leak_rate": 0.0,
            "cases": [],
        }
        if extra:
            payload.update(extra)
        return payload

    def avg(key: str) -> float:
        return sum(r.scores.get(key, 0.0) for r in results) / total

    success = sum(1 for r in results if r.ok)
    payload = {
        "benchmark_id": benchmark_id,
        "version": version,
        "planner_kind": planner_kind,
        "case_count": total,
        "task_success_rate": success / total,
        "supporting_fact_recall": avg("supporting_fact_recall"),
        "answer_em": avg("answer_em"),
        "answer_f1": avg("answer_f1"),
        "citation_precision": avg("citation_precision"),
        "citation_recall": avg("citation_recall"),
        "faithfulness": avg("faithfulness"),
        "avg_retrieve_rounds": avg("retrieve_rounds"),
        "tenant_leak_rate": avg("tenant_leak"),
        "cases": _case_rows(results),
    }
    if extra:
        payload.update(extra)
    return payload
