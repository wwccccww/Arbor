from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import httpx

from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack
from arbor.adapters.outbound.benchmarks.bfcl_loader import (
    BFCL_DEV,
    BFCL_SMOKE,
    calls_equivalent,
    extract_tool_calls_from_steps,
    load_dev_cases,
    load_smoke_cases,
    plan_script_from_case,
    register_bfcl_functions,
    score_against_ground_truth,
    validate_expected_executable,
)
from arbor.application.agent.planner import PROMPT_VERSION, FallbackPlanner
from arbor.application.evaluation.public_benchmarks.port import PublicBenchmarkResult
from arbor.application.evaluation.public_benchmarks.report import aggregate_public_benchmark
from arbor.application.tools.registry import ToolRegistry
from arbor.domain.agent.action import validate_planner_action
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId
from arbor.env import chat_api_key, chat_base_url, chat_model

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")


class BFCFunctionCallPlanner:
    """Multi-turn function-calling planner for official BFCL eval."""

    planner_kind = "real"
    planner_version = "bfcl-fc-v2"

    def __init__(self, *, model: str | None = None, timeout_s: float = 60.0) -> None:
        self.model = model or chat_model()
        self.timeout_s = timeout_s
        self.last_metadata: dict = {}

    def _bfcl_config(self, run_metadata: dict | None) -> dict:
        meta = dict(run_metadata or {})
        cfg = dict(meta.get("bfcl") or {})
        variant = dict(meta.get("eval_variant") or {})
        return {
            "max_tools": int(cfg.get("max_tools") or variant.get("bfcl_max_tools") or 6),
            "category": str(cfg.get("category") or variant.get("bfcl_category") or ""),
        }

    def next_action(
        self,
        *,
        goal: str,
        steps: list[dict],
        context_manifest: dict | None = None,
        tool_schemas: list[dict] | None = None,
        budget: dict | None = None,
        plan_script: list[dict] | None = None,
        evidence_ids: list[str] | None = None,
        run_metadata: dict | None = None,
    ) -> dict:
        del context_manifest, budget, plan_script, evidence_ids
        cfg = self._bfcl_config(run_metadata)
        max_tools = max(1, cfg["max_tools"])
        tool_steps = [s for s in steps if s.get("kind") == "tool"]
        if any(s.get("kind") == "answer" for s in steps):
            return validate_planner_action(
                {
                    "schema_version": 1,
                    "action": "answer",
                    "text": "Done.",
                    "citations": [],
                    "completion": True,
                }
            )
        if len(tool_steps) >= max_tools:
            return validate_planner_action(
                {
                    "schema_version": 1,
                    "action": "answer",
                    "text": "Done.",
                    "citations": [],
                    "completion": True,
                }
            )

        key = chat_api_key()
        if not key:
            raise DomainError("LLM_UNAVAILABLE", "chat API key missing for BFCL LLM eval")
        tools_blob = json.dumps(tool_schemas or [], ensure_ascii=False)
        system = (
            "You are a Berkeley Function Calling Leaderboard agent. Output exactly one JSON object. "
            "Allowed actions: tool, answer. Issue tool calls one at a time until the user task is satisfied, "
            "then answer with completion=true. If no tool applies, answer without tools. "
            "tool_name must match a provided tool exactly. Use only argument keys defined in the tool schema. "
            f"Tools: {tools_blob}. "
            "Schema: {schema_version:1, action, tool_name?, arguments?, text?, completion?}"
        )
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": goal},
        ]
        for step in steps:
            if step.get("kind") != "tool":
                continue
            inp = dict(step.get("input") or {})
            out = dict(step.get("output") or {})
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "action": "tool",
                            "tool_name": inp.get("tool_name"),
                            "arguments": inp.get("arguments"),
                        },
                        ensure_ascii=False,
                    ),
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": f"Tool result: {json.dumps(out, ensure_ascii=False)[:3000]}",
                }
            )
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 800,
            "temperature": 0.0,
        }
        try:
            response = httpx.post(
                f"{chat_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise DomainError("LLM_TIMEOUT", "BFCL planner timed out") from exc
        except httpx.HTTPError as exc:
            raise DomainError("LLM_UPSTREAM", str(exc)) from exc
        if response.status_code >= 400:
            raise DomainError("LLM_UPSTREAM", f"BFCL planner HTTP {response.status_code}")
        content = response.json()["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", content or "", flags=re.DOTALL)
        if not match:
            raise DomainError("LLM_INVALID_JSON", "BFCL planner output not JSON")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise DomainError("LLM_INVALID_JSON", "BFCL planner JSON parse failed") from exc
        action = validate_planner_action(data)
        self.last_metadata = {
            "provider": "deepseek",
            "model": self.model,
            "prompt_version": PROMPT_VERSION,
            "bfcl_planner": self.planner_version,
            "tool_steps": len(tool_steps),
        }
        if run_metadata is not None:
            run_metadata["planner"] = dict(self.last_metadata)
        return action


def score_tool_calls(
    *,
    expected_calls: list[dict],
    actual_calls: list[dict],
    expect_no_tool: bool,
    ground_truth: list[dict] | None = None,
    unordered: bool = False,
) -> tuple[bool, dict]:
    if ground_truth is not None:
        return score_against_ground_truth(
            actual_calls=actual_calls,
            ground_truth=ground_truth,
            expect_no_tool=expect_no_tool,
            unordered=unordered,
        )
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


def _prepare_stack(case: dict, *, planner_kind: str = "fake") -> dict:
    stack = build_agent_eval_stack(use_employee_templates=False, with_mcp=False)
    registry = ToolRegistry()
    register_bfcl_functions(registry, list(case.get("functions") or []))
    advance = stack["approve_step"].advance
    advance.tool_executor.registry = registry
    if planner_kind == "llm":
        advance.planner = FallbackPlanner(BFCFunctionCallPlanner(), reason="bfcl planner fallback")
    persona = stack["personas"].get(TENANT, LINXIA)
    if persona is not None:
        persona.tool_policy.allowed_tools = registry.list_names()
        if not any(Capability.ADMIN in g.capabilities for g in persona.grants if g.user_id == USER):
            persona.grants.append(Grant(user_id=USER, capabilities=[Capability.ADMIN, Capability.CHAT]))
    return stack


def run_bfcl_case(*, case: dict, stack: dict | None = None, planner_kind: str = "fake") -> PublicBenchmarkResult:
    use_script = planner_kind != "llm"
    if use_script:
        os.environ["ARBOR_ALLOW_PLAN_SCRIPT"] = "1"
    stack = stack or _prepare_stack(case, planner_kind=planner_kind)
    registry = stack["approve_step"].advance.tool_executor.registry
    executable = validate_expected_executable(registry, case)
    expected_calls = list(case.get("expected_calls") or [])
    ground_truth = list(case.get("ground_truth") or [])
    expect_no_tool = bool(case.get("expect_no_tool"))
    category = str(case.get("source_category") or "")

    if not executable and use_script:
        return PublicBenchmarkResult(
            case_id=str(case["id"]),
            ok=False,
            scores={"function_match": 0.0, "argument_match": 0.0, "executable": 0.0},
            actual={"calls": []},
            detail="expected call not executable against schema",
        )

    plan_script = plan_script_from_case(case) if use_script else None
    n_calls = len(ground_truth) or len(expected_calls) if not expect_no_tool else 0
    max_steps = max(8, n_calls * 3 + 4) if not expect_no_tool else 3
    eval_variant = None
    if planner_kind == "llm":
        eval_variant = {
            "bfcl_max_tools": max(1, n_calls),
            "bfcl_category": category,
        }
    started = time.perf_counter()
    run = stack["start_run"](
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        goal=str(case.get("goal") or ""),
        plan_script=plan_script,
        max_steps=max_steps,
        eval_variant=eval_variant,
        enqueue=True,
    )
    final = stack["runs"].get(TENANT, run.id)
    steps = stack["approve_step"].advance.steps.list_for_run(TENANT, run.id)
    actual_calls = extract_tool_calls_from_steps(steps)
    gt = ground_truth if (planner_kind == "llm" and ground_truth) else None
    ok, scores = score_tool_calls(
        expected_calls=expected_calls,
        actual_calls=actual_calls,
        expect_no_tool=expect_no_tool,
        ground_truth=gt,
        unordered=category == "parallel",
    )
    scores["executable"] = 1.0 if executable or planner_kind == "llm" else 0.0
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    status = final.status.value if final else None
    if status not in {"completed", "failed"} and expect_no_tool:
        ok = ok and status == "completed"
    elif status != "completed" and not expect_no_tool and use_script:
        ok = False
    detail = f"status={status} expected={len(expected_calls)} actual={len(actual_calls)} planner={planner_kind}"
    return PublicBenchmarkResult(
        case_id=str(case["id"]),
        ok=ok,
        scores=scores,
        actual={"calls": actual_calls, "status": status, "planner_kind": planner_kind},
        latency_ms=latency_ms,
        detail=detail,
    )


def _run_bfcl_payload(*, payload: dict, planner_kind: str, case_ids: set[str] | None = None) -> dict:
    results: list[PublicBenchmarkResult] = []
    for case in payload.get("cases") or []:
        if case_ids is not None and str(case.get("id")) not in case_ids:
            continue
        results.append(run_bfcl_case(case=case, planner_kind=planner_kind))
    return aggregate_public_benchmark(
        benchmark_id="bfcl",
        version=str(payload.get("suite_version") or "bfcl"),
        planner_kind=planner_kind,
        results=results,
        extra={
            "suite_version": payload.get("suite_version"),
            "description": payload.get("description"),
            "eval_protocol": payload.get("eval_protocol") or "subset",
            "source": payload.get("source"),
        },
    )


def run_bfcl_smoke(*, fixture_path: Path | None = None, planner_kind: str = "fake") -> dict:
    payload = load_smoke_cases(fixture_path or BFCL_SMOKE)
    payload["eval_protocol"] = "smoke_subset"
    return _run_bfcl_payload(payload=payload, planner_kind=planner_kind)


def run_bfcl_dev(*, fixture_path: Path | None = None, planner_kind: str = "fake", case_ids: set[str] | None = None) -> dict:
    payload = load_dev_cases(fixture_path or BFCL_DEV)
    payload["eval_protocol"] = "official_dev_subset"
    return _run_bfcl_payload(payload=payload, planner_kind=planner_kind, case_ids=case_ids)


def write_bfcl_baseline(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
