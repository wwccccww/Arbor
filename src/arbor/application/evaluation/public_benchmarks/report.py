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
