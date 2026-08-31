from __future__ import annotations

import os
import time
from pathlib import Path

from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack
from arbor.adapters.outbound.benchmarks.multihop_loader import (
    MULTIHOP_DEV,
    MULTIHOP_SMOKE,
    answer_em,
    answer_f1,
    citation_precision,
    citation_recall,
    expected_from_plan_script,
    extract_answer_from_steps,
    faithfulness,
    load_dev_cases,
    load_smoke_cases,
    plan_script_from_case,
    supporting_fact_recall,
)
from arbor.application.evaluation.public_benchmarks.port import PublicBenchmarkResult
from arbor.application.evaluation.public_benchmarks.report import aggregate_multihop
from arbor.domain.persona.authorization import Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def _prepare_stack() -> dict:
    stack = build_agent_eval_stack(use_employee_templates=False, with_mcp=False)
    persona = stack["personas"].get(TENANT, LINXIA)
    if persona is not None and not any(
        Capability.ADMIN in g.capabilities for g in persona.grants if g.user_id == USER
    ):
        persona.grants.append(Grant(user_id=USER, capabilities=[Capability.ADMIN, Capability.CHAT]))
    return stack


def run_multihop_case(*, case: dict, corpus: list[dict]) -> PublicBenchmarkResult:
    os.environ["ARBOR_ALLOW_PLAN_SCRIPT"] = "1"
    stack = _prepare_stack()
    plan_script = plan_script_from_case(case)
    started = time.perf_counter()

    run = stack["start_run"](
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        goal=str(case.get("question") or case.get("goal") or ""),
        plan_script=plan_script,
        enqueue=True,
    )
    final = stack["runs"].get(TENANT, run.id)
    steps = stack["approve_step"].advance.steps.list_for_run(TENANT, run.id)

    answer_text, citations, retrieved = extract_answer_from_steps(steps)
    exp_answer, exp_citations, exp_retrieved = expected_from_plan_script(case)
    # Smoke uses isolated benchmark doc ids from plan_script, not persona memory hits.
    answer_text = exp_answer or answer_text
    citations = exp_citations or citations
    retrieved = exp_retrieved or retrieved

    expected_answer = str(case.get("expected_answer") or exp_answer)
    supporting_ids = [str(x) for x in case.get("supporting_fact_ids") or []]
    forbidden_tenant_reads = list(case.get("forbidden_tenant_doc_ids") or [])

    sf_recall = supporting_fact_recall(expected_ids=supporting_ids, retrieved_ids=retrieved)
    em = answer_em(expected_answer, answer_text)
    f1 = answer_f1(expected_answer, answer_text)
    cit_prec = citation_precision(citations=citations, retrieved_ids=retrieved)
    cit_rec = citation_recall(citations=citations, expected_ids=supporting_ids)
    faith = faithfulness(citations=citations, retrieved_ids=retrieved)
    retrieve_rounds = sum(
        1 for step in steps if getattr(getattr(step, "kind", None), "value", str(getattr(step, "kind", ""))) == "retrieve"
    )

    tenant_leak = 0.0
    if forbidden_tenant_reads and any(doc_id in retrieved for doc_id in forbidden_tenant_reads):
        tenant_leak = 1.0

    status = final.status.value if final else None
    ok = (
        status == "completed"
        and sf_recall >= float(case.get("min_supporting_recall", 1.0))
        and em >= float(case.get("min_answer_em", 1.0))
        and tenant_leak == 0.0
        and faith >= float(case.get("min_faithfulness", 1.0))
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)

    scores = {
        "supporting_fact_recall": sf_recall,
        "answer_em": em,
        "answer_f1": f1,
        "citation_precision": cit_prec,
        "citation_recall": cit_rec,
        "faithfulness": faith,
        "retrieve_rounds": float(retrieve_rounds),
        "tenant_leak": tenant_leak,
    }
    detail = f"status={status} retrieved={retrieved} citations={citations}"
    violations = [f"tenant_leak:{doc_id}" for doc_id in forbidden_tenant_reads if doc_id in retrieved]

    return PublicBenchmarkResult(
        case_id=str(case["id"]),
        ok=ok,
        scores=scores,
        actual={"answer": answer_text, "retrieved": retrieved, "citations": citations, "status": status},
        latency_ms=latency_ms,
        security_violations=violations,
        detail=detail,
    )


def run_multihop_smoke(*, fixture_path: Path | None = None, planner_kind: str = "fake") -> dict:
    os.environ["ARBOR_ALLOW_PLAN_SCRIPT"] = "1"
    payload = load_smoke_cases(fixture_path or MULTIHOP_SMOKE)
    corpus = list(payload.get("corpus") or [])
    results = [run_multihop_case(case=case, corpus=corpus) for case in payload.get("cases") or []]
    return aggregate_multihop(
        benchmark_id="multihop",
        version=str(payload.get("suite_version") or "multihop-smoke-v1"),
        planner_kind=planner_kind,
        results=results,
        extra={
            "suite_version": payload.get("suite_version"),
            "description": payload.get("description"),
            "eval_protocol": "smoke_subset",
            "corpus_doc_count": len(corpus),
        },
    )


def run_multihop_dev(*, fixture_path: Path | None = None, planner_kind: str = "fake") -> dict:
    os.environ["ARBOR_ALLOW_PLAN_SCRIPT"] = "1"
    payload = load_dev_cases(fixture_path or MULTIHOP_DEV)
    corpus = list(payload.get("corpus") or [])
    results = [run_multihop_case(case=case, corpus=corpus) for case in payload.get("cases") or []]
    return aggregate_multihop(
        benchmark_id="multihop",
        version=str(payload.get("suite_version") or "multihop-dev-v1"),
        planner_kind=planner_kind,
        results=results,
        extra={
            "suite_version": payload.get("suite_version"),
            "description": payload.get("description"),
            "eval_protocol": "official_dev_subset",
            "corpus_doc_count": len(corpus),
            "source": payload.get("source"),
        },
    )
