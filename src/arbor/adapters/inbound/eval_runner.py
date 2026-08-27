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
from arbor.domain.identity.tenant import Membership, Role, Tenant
from arbor.domain.identity.user import User
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.persona.persona import Persona, Profile
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId, UserId
from arbor.env import database_url
from arbor.paths import repo_root

ROOT = repo_root()


def _status(raw: str) -> MemoryStatus:
    return MemoryStatus(raw)


def load_world(path: Path, stores: InMemoryStores, embed_client=None) -> None:
    import json

    world = json.loads(path.read_text(encoding="utf-8"))
    for tenant in world.get("tenants") or []:
        stores.tenants[tenant["id"]] = Tenant(
            id=TenantId(tenant["id"]),
            name=tenant.get("name") or "",
        )
    for user in world.get("users") or []:
        stores.users[user["id"]] = User(id=UserId(user["id"]), email=user.get("email") or "")
        tenant_id = user.get("tenant_id")
        tenant = stores.tenants.get(tenant_id) if tenant_id else None
        if tenant is not None:
            role = user.get("role") or "member"
            tenant.memberships.append(
                Membership(
                    tenant_id=TenantId(tenant_id),
                    user_id=UserId(user["id"]),
                    role=Role(role),
                )
            )
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
            confidence=float(event["confidence"]) if event.get("confidence") is not None else None,
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
    embed_fn = (embed_client or FixtureEmbeddingClient()).embed
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
            index.upsert(item.tenant_id, item.persona_id, item.id, embed_fn(item.text), item.status)


def resolve_embed(embed: str = "fixture"):
    if embed == "bge":
        from arbor.adapters.outbound.embedding import HttpEmbeddingClient

        client = HttpEmbeddingClient()
        return client, client.label
    return FixtureEmbeddingClient(), "fixture_embed (deterministic hash, not bge-m3)"


def resolve_backend(backend: str = "auto") -> str:
    if backend == "auto":
        return "postgres" if database_url() else "memory"
    if backend not in {"memory", "postgres"}:
        raise ValueError(backend)
    if backend == "postgres" and not database_url():
        raise RuntimeError("postgres backend needs DATABASE_URL")
    return backend


def _ports(stores: InMemoryStores, embed_client=None):
    memories = InMemoryMemoryRepository(stores)
    events = InMemoryEventGraphRepository(stores)
    threads = InMemoryThreadRepository(stores)
    index = InMemoryVectorIndex(stores, memories)
    embed = embed_client or FixtureEmbeddingClient()

    def summary_for(persona_id: PersonaId) -> str:
        for thread in stores.threads.values():
            if thread.persona_id == persona_id:
                return thread.summary
        return ""

    return memories, events, threads, index, embed, summary_for


def _open_postgres(world_path: Path, embed_client=None):
    from arbor.adapters.outbound.postgres import PostgresSession

    session = PostgresSession.connect(database_url(), embed=embed_client)
    session.reset()
    session.load_world(world_path)
    return session


def _postgres_ports(session):
    def summary_for(persona_id: PersonaId) -> str:
        return session.threads.summary_for(persona_id)

    return session.memories, session.events, session.threads, session.vectors, session.embed, summary_for


def run_suite(
    *,
    suite_dir: Path,
    strategy: str,
    k: int | None = None,
    backend: str = "auto",
    session=None,
    embed: str = "fixture",
) -> dict:
    world, cases_doc, _thresholds, default_k, world_path = load_suite_files(suite_dir)
    backend = resolve_backend(backend)
    owns = False
    stores = None
    embed_client, _embed_label = resolve_embed(embed)
    if backend == "postgres":
        if session is None:
            session = _open_postgres(world_path, embed_client=embed_client)
            owns = True
        memories, events, _threads, index, embed, summary_for = _postgres_ports(session)
        lexical_search = getattr(index, "lexical_search", None)
    else:
        stores = InMemoryStores()
        load_world(world_path, stores, embed_client=embed_client)
        memories, events, _threads, index, embed, summary_for = _ports(stores, embed_client=embed_client)
        lexical_search = None
    try:
        report = evaluate_retrieval(
            strategy=strategy,
            cases_doc=cases_doc,
            world=world,
            k=k or default_k,
            list_active=memories.list_active,
            list_events=events.list_nodes,
            list_edges=events.list_edges,
            summary_for=summary_for,
            vector_search=index.search,
            embed=embed.embed,
            lexical_search=lexical_search,
        )
        report["backend"] = backend
        return report
    finally:
        if owns and session is not None:
            session.close()


def run_all_strategies(suite_dir: Path, backend: str = "auto", embed: str = "fixture") -> dict:
    backend = resolve_backend(backend)
    session = None
    world_path = None
    embed_client, _ = resolve_embed(embed)
    if backend == "postgres":
        from arbor.application.evaluation.runner import resolve_world_path

        world_path = resolve_world_path(suite_dir)
        session = _open_postgres(world_path, embed_client=embed_client)
    try:
        table = {}
        reports = {}
        for name in strategy_names():
            report = run_suite(
                suite_dir=suite_dir,
                strategy=name,
                backend=backend,
                session=session,
                embed=embed,
            )
            reports[name] = report
            table[name] = comparison_row(report)
        return {"strategies": table, "reports": reports, "backend": backend}
    finally:
        if session is not None:
            session.close()


def run_generation(
    *,
    suite_dir: Path,
    strategy: str = "layered_tree",
    llm=None,
    scorer=None,
    backend: str = "auto",
) -> dict:
    from arbor.adapters.outbound.deepseek import DeepSeekChatLLM
    from arbor.adapters.outbound.ragas_scorer import RagasFaithfulnessScorer

    world, cases_doc, _thresholds, _k, world_path = load_suite_files(suite_dir)
    backend = resolve_backend(backend)
    session = None
    stores = None
    if backend == "postgres":
        session = _open_postgres(world_path)
        memories, events, threads, index, embed, _summary = _postgres_ports(session)
        personas = session.personas
        inbox = session.inbox
    else:
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
    try:
        for case in cases_doc["cases"]:
            actor = case["actor"]
            tenant_id = TenantId(actor["tenant_id"])
            persona_id = PersonaId(actor["persona_id"])
            if stores is not None:
                thread = next((item for item in stores.threads.values() if item.persona_id == persona_id), None)
            else:
                thread = threads.get_by_persona(tenant_id, persona_id)
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
    finally:
        if session is not None:
            session.close()
    metrics = aggregate_generation(rows)
    return {
        "suite_version": cases_doc.get("suite_version") or world.get("suite_version"),
        "strategy": strategy,
        "mode": "generation",
        "backend": backend,
        "metrics": metrics,
        "cases": rows,
    }
