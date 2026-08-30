from __future__ import annotations

import json
from pathlib import Path

from arbor.application.memory.consolidate_episodes import ConsolidateEpisodicMemories
from arbor.application.memory.consolidation import is_consolidation
from arbor.application.memory.delete_memory import DeleteMemory
from arbor.application.memory.validity import is_memory_searchable
from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import Capability, Grant
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId, UserId


def run_memory_smoke(
    *,
    fixture_path: Path,
    memories,
    vectors,
    embed,
    personas,
    ids,
    consolidate: ConsolidateEpisodicMemories | None = None,
    delete: DeleteMemory | None = None,
) -> dict:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    results: list[dict] = []
    duplicate_pairs = 0
    stale_injections = 0

    for case in payload.get("cases") or []:
        tenant_id = TenantId(str(case["tenant_id"]))
        persona_id = PersonaId(str(case["persona_id"]))
        action = str(case.get("action") or "")
        ok = False

        if action == "search_excludes_expired":
            item = MemoryItem(
                id=MemoryId(str(case["memory_id"])),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("text") or ""),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
                source={"valid_until": str(case.get("valid_until") or "")},
            )
            memories.save(item)
            vectors.upsert(tenant_id, persona_id, item.id, embed.embed(item.text), item.status)
            hits = vectors.search(tenant_id, persona_id, embed.embed(str(case.get("query") or "")), 5)
            ok = not any(hit.id == item.id for hit, _ in hits)
            if not ok:
                stale_injections += 1

        elif action == "search_excludes_superseded":
            active = MemoryItem(
                id=MemoryId(str(case["active_id"])),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("active_text") or ""),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
            )
            superseded = MemoryItem(
                id=MemoryId(str(case["superseded_id"])),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("superseded_text") or ""),
                type=MemoryType.FACT,
                status=MemoryStatus.SUPERSEDED,
            )
            memories.save(active)
            memories.save(superseded)
            vectors.upsert(tenant_id, persona_id, active.id, embed.embed(active.text), active.status)
            hits = vectors.search(tenant_id, persona_id, embed.embed(str(case.get("query") or "")), 5)
            hit_ids = {hit.id.value for hit, _ in hits}
            ok = active.id.value in hit_ids and superseded.id.value not in hit_ids
            if superseded.id.value in hit_ids:
                stale_injections += 1

        elif action == "delete_removes_vector" and delete is not None:
            item = MemoryItem(
                id=MemoryId(str(case["memory_id"])),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("text") or ""),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
            )
            memories.save(item)
            vectors.upsert(tenant_id, persona_id, item.id, embed.embed(item.text), item.status)
            user_id = UserId(str(case.get("user_id") or "0a000000-0000-4000-a000-000000000002"))
            delete(
                tenant_id=tenant_id,
                user_id=user_id,
                persona_id=persona_id,
                memory_id=item.id,
                capabilities=list(Capability),
            )
            hits = vectors.search(tenant_id, persona_id, embed.embed(str(case.get("query") or "")), 5)
            stored = memories.get(tenant_id, item.id)
            ok = stored is not None and stored.status == MemoryStatus.DELETED
            ok = ok and not any(hit.id == item.id for hit, _ in hits)

        elif action == "consolidate_episodic" and consolidate is not None:
            user_id = UserId(str(case.get("user_id") or "0a000000-0000-4000-a000-000000000002"))
            persona = personas.get(tenant_id, persona_id)
            if persona is not None:
                persona.grants.append(Grant(user_id=user_id, capabilities=list(Capability)))
            for ep in case.get("episodes") or []:
                item = MemoryItem(
                    id=MemoryId(str(ep["id"])),
                    tenant_id=tenant_id,
                    persona_id=persona_id,
                    text=str(ep.get("text") or ""),
                    type=MemoryType.EPISODE_SUMMARY,
                    status=MemoryStatus.ACTIVE,
                    memory_class=MemoryClass.EPISODIC,
                )
                memories.save(item)
                vectors.upsert(tenant_id, persona_id, item.id, embed.embed(item.text), item.status)
            duplicate_pairs += 1
            consolidate(
                tenant_id=tenant_id,
                user_id=user_id,
                persona_id=persona_id,
                capabilities=list(Capability),
            )
            episodic_active = [
                m
                for m in memories.list_active(tenant_id, persona_id)
                if (m.memory_class == MemoryClass.EPISODIC or m.type == MemoryType.EPISODE_SUMMARY)
                and is_memory_searchable(m)
            ]
            consolidations = [m for m in episodic_active if is_consolidation(m)]
            ok = len(consolidations) == 1 and len(episodic_active) == 1

        results.append({"id": case["id"], "ok": ok})

    passed = sum(1 for row in results if row.get("ok"))
    total = len(results)
    duplicate_rate = duplicate_pairs / total if total else 0.0
    stale_rate = stale_injections / total if total else 0.0
    return {
        "suite_version": payload.get("suite_version"),
        "gate_pass_rate": passed / total if total else 0.0,
        "duplicate_memory_rate": duplicate_rate,
        "stale_memory_injection_rate": stale_rate,
        "deletion_completeness_rate": 1.0 if all(
            row.get("ok") for row in results if row.get("id") == "delete-completeness"
        ) else 0.0,
        "cases": results,
    }
