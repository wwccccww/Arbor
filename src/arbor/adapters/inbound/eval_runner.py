from __future__ import annotations

from pathlib import Path

from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryEventGraphRepository,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryThreadRepository,
    InMemoryVectorIndex,
    ScriptedReasoner,
    SeqIdGenerator,
)
from arbor.application.conversation.send_message import SendMessage
from arbor.application.evaluation.generation import aggregate_generation, score_generation_case
from arbor.application.evaluation.runner import (
    comparison_row,
    evaluate_retrieval,
    load_suite_files,
    strategy_names,
)
from arbor.domain.conversation.thread import Thread
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.persona.persona import Persona, Profile
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId, UserId
from arbor.domain.shared.textvec import fixture_embed
from arbor.paths import repo_root

ROOT = repo_root()


def _status(raw: str) -> MemoryStatus:
    return MemoryStatus(raw)


def load_world(path: Path, stores: InMemoryStores) -> None:
    import json

    world = json.loads(path.read_text(encoding="utf-8"))
    for persona in world["personas"]:
        stores.personas[persona["id"]] = Persona(
            id=PersonaId(persona["id"]),
            tenant_id=TenantId(persona["tenant_id"]),
            skin=persona.get("skin", "companion"),
            profile=Profile(
                display_name=persona.get("display_name", ""),
                one_liner=persona.get("one_liner", ""),
                personality=persona.get("personality"),
                taboos=list(persona.get("taboos") or []),
                relationships=list(persona.get("relationships") or []),
            ),
            grants=[
                Grant(user_id=UserId(user["id"]), capabilities=list(Capability))
                for user in world.get("users", [])
                if user.get("tenant_id") == persona["tenant_id"]
            ]
            or (
                [Grant(user_id=UserId(persona["user_id"]), capabilities=list(Capability))]
                if persona.get("user_id")
                else []
            ),
        )
    for thread in world.get("threads", []):
        stores.threads[thread["id"]] = Thread(
            id=ThreadId(thread["id"]),
            tenant_id=TenantId(thread["tenant_id"]),
            persona_id=PersonaId(thread["persona_id"]),
            summary=thread.get("summary", ""),
        )
    for event in world.get("event_nodes") or world.get("events") or []:
        stores.events[event["id"]] = EventNode(
            id=EventId(event["id"]),
            tenant_id=TenantId(event["tenant_id"]),
            persona_id=PersonaId(event["persona_id"]),
            title=event.get("title", ""),
            summary=event.get("summary", ""),
            type=event.get("type", "daily"),
            importance=int(event.get("importance") or 3),
            happened_at=event.get("happened_at"),
        )
    for edge in world.get("event_edges", []):
        stores.edges.append(
            EventEdge(
                from_id=EventId(edge["from_id"]),
                to_id=EventId(edge["to_id"]),
                kind=edge["kind"],
                tenant_id=TenantId(edge["tenant_id"]),
                persona_id=PersonaId(edge["persona_id"]),
            )
        )
    if not stores.edges:
        v1_edges = ROOT / "eval" / "fixtures" / "suite-v1" / "world.json"
        if v1_edges.exists():
            import json

            v1 = json.loads(v1_edges.read_text(encoding="utf-8"))
            known = set(stores.events)
            for edge in v1.get("event_edges") or []:
                if edge["from_id"] in known and edge["to_id"] in known:
                    stores.edges.append(
                        EventEdge(
                            from_id=EventId(edge["from_id"]),
                            to_id=EventId(edge["to_id"]),
                            kind=edge["kind"],
                            tenant_id=TenantId(edge["tenant_id"]),
                            persona_id=PersonaId(edge["persona_id"]),
                        )
                    )
    mem_repo = InMemoryMemoryRepository(stores)
    index = InMemoryVectorIndex(stores, mem_repo)
    for raw in world["memories"]:
        item = MemoryItem(
            id=MemoryId(raw["id"]),
            tenant_id=TenantId(raw["tenant_id"]),
            persona_id=PersonaId(raw["persona_id"]),
            text=raw["text"],
            type=MemoryType(raw.get("type", "fact")),
            status=_status(raw.get("status", "active")),
            event_id=EventId(raw["event_id"]) if raw.get("event_id") else None,
            supersedes=MemoryId(raw["supersedes"]) if raw.get("supersedes") else None,
        )
        stores.memories[raw["id"]] = item
        if item.is_searchable():
            index.upsert(item.tenant_id, item.persona_id, item.id, fixture_embed(item.text), item.status)


def _ports(stores: InMemoryStores):
    memories = InMemoryMemoryRepository(stores)
    events = InMemoryEventGraphRepository(stores)
    threads = InMemoryThreadRepository(stores)
    index = InMemoryVectorIndex(stores, memories)
    embed = FixtureEmbeddingClient()

    def summary_for(persona_id: PersonaId) -> str:
        for thread in stores.threads.values():
            if thread.persona_id == persona_id:
                return thread.summary
        return ""

    return memories, events, threads, index, embed, summary_for


def run_suite(*, suite_dir: Path, strategy: str, k: int | None = None) -> dict:
    world, cases_doc, _thresholds, default_k, world_path = load_suite_files(suite_dir)
    stores = InMemoryStores()
    load_world(world_path, stores)
    memories, events, _threads, index, embed, summary_for = _ports(stores)
    return evaluate_retrieval(
        strategy=strategy,
        cases_doc=cases_doc,
        world=world,
        k=k or default_k,
        list_active=memories.list_active,
        list_events=events.list_nodes,
        summary_for=summary_for,
        vector_search=index.search,
        embed=embed.embed,
    )


def run_all_strategies(suite_dir: Path) -> dict:
    table = {}
    reports = {}
    for name in strategy_names():
        report = run_suite(suite_dir=suite_dir, strategy=name)
        reports[name] = report
        table[name] = comparison_row(report)
    return {"strategies": table, "reports": reports}


def run_generation(
    *,
    suite_dir: Path,
    strategy: str = "layered_tree",
    llm=None,
    scorer=None,
) -> dict:
    from arbor.adapters.outbound.deepseek import DeepSeekChatLLM
    from arbor.adapters.outbound.ragas_scorer import RagasFaithfulnessScorer

    world, cases_doc, _thresholds, _k, world_path = load_suite_files(suite_dir)
    stores = InMemoryStores()
    load_world(world_path, stores)
    memories, events, threads, index, embed, _summary = _ports(stores)
    personas = InMemoryPersonaRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    send = SendMessage(
        personas=personas,
        memories=memories,
        threads=threads,
        events=events,
        inbox=inbox,
        vectors=index,
        llm=llm or DeepSeekChatLLM(),
        reasoner=ScriptedReasoner(),
        embed=embed,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
        strategy=strategy,
    )
    scorer = scorer if scorer is not None else RagasFaithfulnessScorer()
    mem_index = {item["id"]: item for item in world["memories"]}
    rows = []
    for case in cases_doc["cases"]:
        actor = case["actor"]
        tenant_id = TenantId(actor["tenant_id"])
        persona_id = PersonaId(actor["persona_id"])
        thread = next((item for item in stores.threads.values() if item.persona_id == persona_id), None)
        thread_id = thread.id if thread else ThreadId(f"eval-{persona_id.value}")
        result = send(
            tenant_id=tenant_id,
            user_id=UserId(actor["user_id"]),
            thread_id=thread_id,
            persona_id=persona_id,
            text=case["query"],
            capabilities=list(Capability),
        )
        leak_ids = [mid for mid in result["injected_memory_ids"] if mid in (case.get("forbidden_memory_ids") or [])]
        result["leak_ids"] = leak_ids
        contexts = [ctx for ctx in result.get("injected_contexts") or [] if ctx]
        ragas = None
        if case.get("expected_behavior") in {"answer", "cite"} and not leak_ids:
            ragas = scorer.score(case["query"], result.get("text") or "", contexts)
        result["ragas_faithfulness"] = ragas
        row = score_generation_case(case, result, mem_index)
        row["query"] = case["query"]
        row["text"] = result.get("text") or ""
        rows.append(row)
    metrics = aggregate_generation(rows)
    return {
        "suite_version": cases_doc.get("suite_version") or world.get("suite_version"),
        "strategy": strategy,
        "mode": "generation",
        "metrics": metrics,
        "cases": rows,
    }
