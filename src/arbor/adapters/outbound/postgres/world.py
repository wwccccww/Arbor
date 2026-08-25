from __future__ import annotations

import json
from pathlib import Path

import yaml

from arbor.adapters.outbound.inmemory import FixtureEmbeddingClient
from arbor.domain.auth.credentials import hash_password
from arbor.domain.conversation.thread import Thread
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import Capability, Grant, Persona, Profile
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId, UserId
from arbor.paths import repo_root

ROOT = repo_root()


def _read_world(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def load_world(session, path: Path) -> None:
    world = _read_world(path)
    _ensure_tenants(session, world)
    _load_users(session, world)
    _load_personas(session, world)
    _load_threads(session, world)
    _load_events(session, world)
    _load_memories(session, world)


def load_mini_world(session) -> None:
    load_world(session, ROOT / "tests" / "fixtures" / "mini-world.yaml")


def _ensure_tenants(session, world: dict) -> None:
    seen: set[str] = set()
    for tenant in world.get("tenants") or []:
        session.conn.execute(
            """
            INSERT INTO tenants (id, name) VALUES (%s::uuid, %s)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
            """,
            (tenant["id"], tenant.get("name") or ""),
        )
        seen.add(tenant["id"])
    for persona in world.get("personas") or []:
        tid = persona["tenant_id"]
        if tid in seen:
            continue
        session.conn.execute(
            "INSERT INTO tenants (id, name) VALUES (%s::uuid, %s) ON CONFLICT (id) DO NOTHING",
            (tid, tid),
        )
        seen.add(tid)


_DEMO_PASSWORDS = {
    "demo-a@arbor.eval": "arbor-owner",
    "member-a@arbor.eval": "arbor-member",
    "demo-b@arbor.eval": "arbor-owner",
}


def _load_users(session, world: dict) -> None:
    for user in world.get("users") or []:
        email = (user.get("email") or "").strip().lower()
        password_hash = hash_password(_DEMO_PASSWORDS.get(email, "")) if email in _DEMO_PASSWORDS else None
        session.conn.execute(
            """
            INSERT INTO users (id, email, password_hash)
            VALUES (%s::uuid, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                email = EXCLUDED.email,
                password_hash = COALESCE(EXCLUDED.password_hash, users.password_hash)
            """,
            (user["id"], user.get("email"), password_hash),
        )
        if user.get("tenant_id"):
            session.conn.execute(
                """
                INSERT INTO memberships (tenant_id, user_id, role)
                VALUES (%s::uuid, %s::uuid, %s)
                ON CONFLICT (tenant_id, user_id) DO UPDATE SET role = EXCLUDED.role
                """,
                (user["tenant_id"], user["id"], user.get("role") or "member"),
            )


def _grants_for(persona: dict, world: dict) -> list[Grant]:
    grants = [
        Grant(user_id=UserId(user["id"]), capabilities=list(Capability))
        for user in world.get("users", [])
        if user.get("tenant_id") == persona["tenant_id"]
    ]
    if grants:
        return grants
    if persona.get("user_id"):
        return [Grant(user_id=UserId(persona["user_id"]), capabilities=list(Capability))]
    return []


def _load_personas(session, world: dict) -> None:
    for persona in world.get("personas") or []:
        session.personas.save(
            Persona(
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
                grants=_grants_for(persona, world),
            )
        )


def _load_threads(session, world: dict) -> None:
    for thread in world.get("threads") or []:
        session.threads.save(
            Thread(
                id=ThreadId(thread["id"]),
                tenant_id=TenantId(thread["tenant_id"]),
                persona_id=PersonaId(thread["persona_id"]),
                summary=thread.get("summary", ""),
            )
        )


def _load_events(session, world: dict) -> None:
    for event in world.get("event_nodes") or world.get("events") or []:
        session.events.save_node(
            EventNode(
                id=EventId(event["id"]),
                tenant_id=TenantId(event["tenant_id"]),
                persona_id=PersonaId(event["persona_id"]),
                title=event.get("title", ""),
                summary=event.get("summary", ""),
                type=event.get("type", "daily"),
                importance=int(event.get("importance") or 3),
                happened_at=event.get("happened_at"),
            )
        )
    edges = list(world.get("event_edges") or [])
    if not edges:
        v1_path = ROOT / "eval" / "fixtures" / "suite-v1" / "world.json"
        if v1_path.exists():
            known = {str(row["id"]) for row in session.conn.execute("SELECT id FROM event_nodes").fetchall()}
            v1 = json.loads(v1_path.read_text(encoding="utf-8"))
            for edge in v1.get("event_edges") or []:
                if edge["from_id"] in known and edge["to_id"] in known:
                    edges.append(edge)
    for edge in edges:
        session.events.add_edge(
            EventEdge(
                from_id=EventId(edge["from_id"]),
                to_id=EventId(edge["to_id"]),
                kind=edge["kind"],
                tenant_id=TenantId(edge["tenant_id"]),
                persona_id=PersonaId(edge["persona_id"]),
            )
        )


def _load_memories(session, world: dict) -> None:
    embed = getattr(session, "embed", None) or FixtureEmbeddingClient()
    for raw in world.get("memories") or []:
        item = MemoryItem(
            id=MemoryId(raw["id"]),
            tenant_id=TenantId(raw["tenant_id"]),
            persona_id=PersonaId(raw["persona_id"]),
            text=raw["text"],
            type=MemoryType(raw.get("type", "fact")),
            status=MemoryStatus(raw.get("status", "active")),
            event_id=EventId(raw["event_id"]) if raw.get("event_id") else None,
            supersedes=MemoryId(raw["supersedes"]) if raw.get("supersedes") else None,
        )
        session.memories.save(item)
        if item.is_searchable():
            session.vectors.upsert(
                item.tenant_id,
                item.persona_id,
                item.id,
                embed.embed(item.text),
                item.status,
            )
