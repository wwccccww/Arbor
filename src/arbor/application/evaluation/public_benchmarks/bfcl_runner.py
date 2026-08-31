from __future__ import annotations

import json
import os
import time
from pathlib import Path

from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack
from arbor.adapters.outbound.benchmarks.bfcl_loader import (
    BFCL_SMOKE,
    calls_equivalent,
    extract_tool_calls_from_steps,
    load_smoke_cases,
    plan_script_from_case,
    register_bfcl_functions,
    validate_expected_executable,
)
from arbor.application.evaluation.public_benchmarks.port import PublicBenchmarkResult
from arbor.application.evaluation.public_benchmarks.report import aggregate_public_benchmark
from arbor.application.tools.registry import ToolRegistry
from arbor.domain.persona.authorization import Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def score_tool_calls(*, expected_calls: list[dict], actual_calls: list[dict], expect_no_tool: bool) -> tuple[bool, dict]:
    if expect_no_tool:
        ok = len(actual_calls) == 0
        return ok, {
            "function_match": 1.0 if ok else 0.0,
            "argument_match": 1.0 if ok else 0.0,
            "executable": 1.0,
        }

    if len(expected_calls) != len(actual_calls):
        fn_rate = 0.0
        arg_rate = 0.0
        if expected_calls and actual_calls:
            fn_hits = 0
            arg_hits = 0
            for exp, act in zip(expected_calls, actual_calls, strict=False):
                fn_ok, arg_ok = calls_equivalent(exp, act)
                fn_hits += int(fn_ok)
                arg_hits += int(arg_ok)
            n = max(len(expected_calls), len(actual_calls))
            fn_rate = fn_hits / n
            arg_rate = arg_hits / n
        return False, {
            "function_match": fn_rate,
            "argument_match": arg_rate,
            "executable": 1.0,
        }

    fn_hits = 0
    arg_hits = 0
    for exp, act in zip(expected_calls, actual_calls, strict=True):
        fn_ok, arg_ok = calls_equivalent(exp, act)
        fn_hits += int(fn_ok)
        arg_hits += int(arg_ok)
    n = len(expected_calls) or 1
    scores = {
        "function_match": fn_hits / n,
        "argument_match": arg_hits / n,
        "executable": 1.0,
    }
    ok = fn_hits == n and arg_hits == n
    return ok, scores


def _prepare_stack(case: dict) -> dict:
    stack = build_agent_eval_stack(use_employee_templates=False, with_mcp=False)
    registry = ToolRegistry()
    register_bfcl_functions(registry, list(case.get("functions") or []))
    advance = stack["approve_step"].advance
    advance.tool_executor.registry = registry
    persona = stack["personas"].get(TENANT, LINXIA)
    if persona is not None:
        persona.tool_policy.allowed_tools = registry.list_names()
        if not any(Capability.ADMIN in g.capabilities for g in persona.grants if g.user_id == USER):
            persona.grants.append(Grant(user_id=USER, capabilities=[Capability.ADMIN, Capability.CHAT]))
    return stack


def run_bfcl_case(*, case: dict, stack: dict | None = None) -> PublicBenchmarkResult:
    os.environ["ARBOR_ALLOW_PLAN_SCRIPT"] = "1"
    stack = stack or _prepare_stack(case)
    registry = stack["approve_step"].advance.tool_executor.registry
    executable = validate_expected_executable(registry, case)
    expected_calls = list(case.get("expected_calls") or [])
    expect_no_tool = bool(case.get("expect_no_tool"))

    if not executable:
        return PublicBenchmarkResult(
            case_id=str(case["id"]),
            ok=False,
            scores={"function_match": 0.0, "argument_match": 0.0, "executable": 0.0},
            actual={"calls": []},
            detail="expected call not executable against schema",
        )

    plan_script = plan_script_from_case(case)
    started = time.perf_counter()
    run = stack["start_run"](
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        goal=str(case.get("goal") or ""),
        plan_script=plan_script,
        enqueue=True,
    )
    final = stack["runs"].get(TENANT, run.id)
    steps = stack["approve_step"].advance.steps.list_for_run(TENANT, run.id)
    actual_calls = extract_tool_calls_from_steps(steps)
    ok, scores = score_tool_calls(
        expected_calls=expected_calls,
        actual_calls=actual_calls,
        expect_no_tool=expect_no_tool,
    )
    scores["executable"] = 1.0 if executable else 0.0
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    status = final.status.value if final else None
    if status not in {"completed", "failed"} and expect_no_tool:
        ok = ok and status == "completed"
    elif status != "completed" and not expect_no_tool:
        ok = False
    detail = f"status={status} expected={len(expected_calls)} actual={len(actual_calls)}"
    return PublicBenchmarkResult(
        case_id=str(case["id"]),
        ok=ok,
        scores=scores,
        actual={"calls": actual_calls, "status": status},
        latency_ms=latency_ms,
        detail=detail,
    )


def run_bfcl_smoke(*, fixture_path: Path | None = None, planner_kind: str = "fake") -> dict:
    os.environ["ARBOR_ALLOW_PLAN_SCRIPT"] = "1"
    payload = load_smoke_cases(fixture_path or BFCL_SMOKE)
    results: list[PublicBenchmarkResult] = []
    for case in payload.get("cases") or []:
        results.append(run_bfcl_case(case=case))
    report = aggregate_public_benchmark(
        benchmark_id="bfcl",
        version=str(payload.get("suite_version") or "bfcl-smoke-v1"),
        planner_kind=planner_kind,
        results=results,
        extra={
            "suite_version": payload.get("suite_version"),
            "description": payload.get("description"),
            "eval_protocol": "smoke_subset",
        },
    )
    return report


def write_bfcl_baseline(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
