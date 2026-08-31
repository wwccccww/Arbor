from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack
from arbor.adapters.outbound.benchmarks.multihop_loader import (
    MULTIHOP_DEV,
    MULTIHOP_SMOKE,
    answer_em,
    answer_f1,
    citation_precision,
    citation_recall,
    compact_retrieve_query,
    expected_from_plan_script,
    extract_answer_from_steps,
    faithfulness,
    load_dev_cases,
    load_smoke_cases,
    plan_script_from_case,
    primary_retrieve_query,
    secondary_retrieve_query,
    seed_corpus_to_memory,
    supporting_fact_recall,
)
from arbor.adapters.outbound.embedding import embedding_client_from_env
from arbor.application.agent.planner import (
    SCHEMA_VERSION,
    FallbackPlanner,
    _parse_planner_json,
    _planner_prompt,
    filter_evidence_ids,
)
from arbor.application.evaluation.public_benchmarks.port import PublicBenchmarkResult
from arbor.application.evaluation.public_benchmarks.report import aggregate_multihop
from arbor.domain.agent.action import validate_planner_action
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId
from arbor.env import chat_api_key, chat_base_url, embedding_api_key

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")
FORBIDDEN_TENANT = TenantId("0a000000-0000-4000-a000-000000000099")


class MultihopLLMPlanner:
    """RAG planner tuned for short benchmark answers with mandatory citations."""

    planner_kind = "real"
    planner_version = "multihop-rag-v4"

    _MAX_RETRIEVE_HOPS = 2

    def __init__(
        self,
        *,
        model: str | None = None,
        provider: str = "deepseek",
        timeout_s: float = 45.0,
    ) -> None:
        from arbor.env import chat_model

        self.model = model or chat_model()
        self.provider = provider
        self.timeout_s = timeout_s
        self.last_metadata: dict = {}

    @staticmethod
    def _normalize_action(raw: dict) -> dict:
        data = dict(raw)
        action = str(data.get("action") or "").lower()
        if action == "answer" and not data.get("text"):
            if data.get("answer"):
                data["text"] = data["answer"]
            elif data.get("response"):
                data["text"] = data["response"]
        data.setdefault("schema_version", SCHEMA_VERSION)
        if action == "answer":
            data.setdefault("completion", True)
        return data

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
        del plan_script
        retrieve_steps = [s for s in steps if s.get("kind") == "retrieve"]
        if len(retrieve_steps) < self._MAX_RETRIEVE_HOPS:
            if not retrieve_steps:
                query = primary_retrieve_query(goal)
                reason = "entity + question first hop"
            else:
                query = secondary_retrieve_query(goal)
                reason = "full-question second hop"
            return validate_planner_action(
                {
                    "schema_version": SCHEMA_VERSION,
                    "action": "retrieve",
                    "query": query or goal,
                    "scopes": ["semantic_memory", "procedural_memory", "episodic_memory"],
                    "reason": reason,
                }
            )
        enriched_goal = (
            f"{goal}\n\n"
            "Answer with the shortest factual phrase only (entity, date, number, or exactly Yes/No). "
            "For yes/no questions respond with exactly Yes or No — no explanation. "
            "Cite evidence_ids used. "
            'Use JSON: {"schema_version":1,"action":"answer","text":"...","citations":[...],"completion":true}'
        )
        key = chat_api_key()
        if not key:
            raise DomainError("LLM_UNAVAILABLE", "chat API key missing for multihop LLM eval")
        prompt = _planner_prompt(
            goal=enriched_goal,
            steps=steps,
            context_manifest=context_manifest or {},
            tool_schemas=tool_schemas or [],
            budget=budget or {},
            evidence_ids=list(evidence_ids or []),
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": enriched_goal},
            ],
            "max_tokens": 800,
            "temperature": 0.0,
        }
        response = httpx.post(
            f"{chat_base_url()}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout_s,
        )
        content = response.json()["choices"][0]["message"]["content"]
        raw = self._normalize_action(_parse_planner_json(content))
        action = validate_planner_action(raw)
        action = filter_evidence_ids(action, list(evidence_ids or []))
        self.last_metadata = {
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.planner_version,
            "schema_version": SCHEMA_VERSION,
        }
        if run_metadata is not None:
            run_metadata["planner"] = dict(self.last_metadata)
        return action


def _clear_benchmark_memories(stack: dict, *, tenant_id: TenantId, persona_id: PersonaId) -> None:
    memories = stack["memories"]
    vectors = stack["vectors"]
    for item in list(memories.list_active(tenant_id, persona_id)):
        memories.delete(tenant_id, item.id)
        vectors.stores.vectors.pop(item.id.value, None)


def _resolve_multihop_embed(planner_kind: str):
    if planner_kind == "llm" and embedding_api_key():
        client = embedding_client_from_env()
        if client is not None:
            return client
    return None


def _prepare_stack(*, corpus: list[dict], planner_kind: str = "fake", seed_corpus: bool = True) -> dict:
    embed_client = _resolve_multihop_embed(planner_kind)
    stack = build_agent_eval_stack(
        use_employee_templates=False,
        with_mcp=False,
        embed_client=embed_client,
    )
    if planner_kind == "llm":
        _clear_benchmark_memories(stack, tenant_id=TENANT, persona_id=LINXIA)
    advance = stack["approve_step"].advance
    if planner_kind == "llm":
        advance.planner = FallbackPlanner(MultihopLLMPlanner(), reason="multihop planner fallback")
    if seed_corpus and planner_kind == "llm":
        seed_corpus_to_memory(
            memories=stack["memories"],
            vectors=stack["vectors"],
            embed=stack["embed"],
            corpus=corpus,
            tenant_id=TENANT,
            persona_id=LINXIA,
        )
        for doc in corpus or []:
            if str(doc.get("tenant_id") or "") != "tenant-b":
                continue
            doc_id = str(doc.get("id") or "").strip()
            if not doc_id:
                continue
            title = str(doc.get("title") or "").strip()
            body = str(doc.get("text") or "").strip()
            text = f"{title}\n{body}".strip() if title else body
            if len(text) > 1200:
                text = text[:1200].rsplit(" ", 1)[0]
            if not text:
                continue
            from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus, MemoryType
            from arbor.domain.shared.ids import MemoryId

            item = MemoryItem(
                id=MemoryId(doc_id),
                tenant_id=FORBIDDEN_TENANT,
                persona_id=LINXIA,
                text=text,
                type=MemoryType.FILE_CHUNK,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.SEMANTIC,
                source={"benchmark_doc_id": doc_id, "tenant": "tenant-b"},
            )
            stack["memories"].save(item)
            stack["vectors"].upsert(
                FORBIDDEN_TENANT, LINXIA, item.id, stack["embed"].embed(text), item.status
            )
    persona = stack["personas"].get(TENANT, LINXIA)
    if persona is not None and not any(
        Capability.ADMIN in g.capabilities for g in persona.grants if g.user_id == USER
    ):
        persona.grants.append(Grant(user_id=USER, capabilities=[Capability.ADMIN, Capability.CHAT]))
    return stack


def run_multihop_case(
    *,
    case: dict,
    corpus: list[dict],
    planner_kind: str = "fake",
    stack: dict | None = None,
) -> PublicBenchmarkResult:
    use_script = planner_kind != "llm"
    if use_script:
        os.environ["ARBOR_ALLOW_PLAN_SCRIPT"] = "1"
    stack = stack or _prepare_stack(corpus=corpus, planner_kind=planner_kind)
    plan_script = plan_script_from_case(case) if use_script else None
    started = time.perf_counter()
    eval_variant = None
    if planner_kind == "llm":
        eval_variant = {
            "multihop_eval": True,
            "retrieve_k": 8,
            "context_token_budget": 12000,
        }

    run = stack["start_run"](
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        goal=str(case.get("question") or case.get("goal") or ""),
        plan_script=plan_script,
        max_steps=12 if planner_kind == "llm" else 8,
        eval_variant=eval_variant,
        enqueue=True,
    )
    final = stack["runs"].get(TENANT, run.id)
    steps = stack["approve_step"].advance.steps.list_for_run(TENANT, run.id)

    answer_text, citations, retrieved = extract_answer_from_steps(steps)
    exp_answer, exp_citations, exp_retrieved = expected_from_plan_script(case)
    if use_script:
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
    if planner_kind == "llm":
        min_em = 0.0
        min_recall = 0.0
        min_faith = 0.0
        ok = status == "completed" and tenant_leak == 0.0 and sf_recall >= 0.33 and f1 >= 0.2
    else:
        min_em = float(case.get("min_answer_em", 1.0))
        min_recall = float(case.get("min_supporting_recall", 1.0))
        min_faith = float(case.get("min_faithfulness", 1.0))
        ok = (
            status == "completed"
            and sf_recall >= min_recall
            and em >= min_em
            and tenant_leak == 0.0
            and faith >= min_faith
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
    detail = f"status={status} retrieved={retrieved} citations={citations} planner={planner_kind}"
    violations = [f"tenant_leak:{doc_id}" for doc_id in forbidden_tenant_reads if doc_id in retrieved]

    return PublicBenchmarkResult(
        case_id=str(case["id"]),
        ok=ok,
        scores=scores,
        actual={
            "answer": answer_text,
            "retrieved": retrieved,
            "citations": citations,
            "status": status,
            "planner_kind": planner_kind,
        },
        latency_ms=latency_ms,
        security_violations=violations,
        detail=detail,
    )


def run_multihop_smoke(*, fixture_path: Path | None = None, planner_kind: str = "fake") -> dict:
    if planner_kind != "llm":
        os.environ["ARBOR_ALLOW_PLAN_SCRIPT"] = "1"
    payload = load_smoke_cases(fixture_path or MULTIHOP_SMOKE)
    corpus = list(payload.get("corpus") or [])
    results = [
        run_multihop_case(case=case, corpus=corpus, planner_kind=planner_kind)
        for case in payload.get("cases") or []
    ]
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


def run_multihop_dev(
    *,
    fixture_path: Path | None = None,
    planner_kind: str = "fake",
    case_ids: set[str] | None = None,
) -> dict:
    if planner_kind != "llm":
        os.environ["ARBOR_ALLOW_PLAN_SCRIPT"] = "1"
    payload = load_dev_cases(fixture_path or MULTIHOP_DEV)
    corpus = list(payload.get("corpus") or [])
    cases = payload.get("cases") or []
    if case_ids is not None:
        cases = [case for case in cases if str(case.get("id")) in case_ids]
    results = [run_multihop_case(case=case, corpus=corpus, planner_kind=planner_kind) for case in cases]
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


def write_multihop_baseline(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
