from __future__ import annotations

import json
from pathlib import Path

from arbor.application.memory.conflict_detection import enrich_inbox_extract
from arbor.application.memory.consolidate_episodes import ConsolidateEpisodicMemories
from arbor.application.memory.consolidation import derived_from_ids, is_consolidation
from arbor.application.memory.delete_memory import DeleteMemory
from arbor.application.memory.procedural_memory import agent_may_write_procedural
from arbor.application.memory.validity import is_memory_searchable
from arbor.application.memory.working_memory import clear_working_memory_for_run
from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import InboxItem, MemoryClass, MemoryItem, MemoryStatus, MemoryType
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
    confirm=None,
    inbox=None,
) -> dict:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    results: list[dict] = []
    duplicate_pairs = 0
    stale_injections = 0
    conflict_injections = 0
    writes_attempted = 0
    writes_correct = 0
    helpful_queries = 0
    helpful_hits = 0

    for case in payload.get("cases") or []:
        tenant_id = TenantId(str(case["tenant_id"]))
        persona_id = PersonaId(str(case["persona_id"]))
        action = str(case.get("action") or "")
        ok = False

        if action == "search_excludes_decayed_episodic":
            source = {"recorded_at": str(case.get("recorded_at") or "")}
            if case.get("decay_after_days") is not None:
                source["decay_after_days"] = int(case["decay_after_days"])
            item = MemoryItem(
                id=MemoryId(str(case["memory_id"])),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("text") or ""),
                type=MemoryType.EPISODE_SUMMARY,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.EPISODIC,
                source=source,
            )
            memories.save(item)
            vectors.upsert(tenant_id, persona_id, item.id, embed.embed(item.text), item.status)
            hits = vectors.search(tenant_id, persona_id, embed.embed(str(case.get("query") or "")), 5)
            ok = not any(hit.id == item.id for hit, _ in hits)
            if not ok:
                stale_injections += 1

        elif action == "search_excludes_expired":
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
            expected_ids = {str(ep["id"]) for ep in case.get("episodes") or []}
            ok = any(expected_ids.issubset(set(derived_from_ids(c))) for c in consolidations)

        elif action == "confirm_inbox_write" and confirm is not None and inbox is not None:
            user_id = UserId(str(case.get("user_id") or "0a000000-0000-4000-a000-000000000002"))
            persona = personas.get(tenant_id, persona_id)
            if persona is not None:
                persona.grants.append(Grant(user_id=user_id, capabilities=list(Capability)))
            text = str(case.get("text") or "")
            inbox_id = str(case.get("inbox_id") or ids.new_id())
            inbox.add(
                InboxItem(
                    id=inbox_id,
                    tenant_id=tenant_id,
                    persona_id=persona_id,
                    kind="extract",
                    payload={"text": text, "memory_type": "fact"},
                    status="pending",
                )
            )
            confirm(
                tenant_id=tenant_id,
                user_id=user_id,
                persona_id=persona_id,
                inbox_id=inbox_id,
                capabilities=list(Capability),
            )
            writes_attempted += 1
            hits = vectors.search(tenant_id, persona_id, embed.embed(str(case.get("query") or text)), 5)
            ok = any(hit.text == text for hit, _ in hits)
            if ok:
                writes_correct += 1

        elif action == "detect_inbox_conflict":
            active = MemoryItem(
                id=MemoryId(str(case.get("active_id") or "mem-conflict-active")),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("active_text") or ""),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
            )
            memories.save(active)
            enriched = enrich_inbox_extract(
                {"text": str(case.get("proposed_text") or "")},
                [active],
            )
            ok = enriched.get("conflicts_with") == active.id.value
            if not ok:
                conflict_injections += 1

        elif action == "confirm_conflict_supersedes" and confirm is not None and inbox is not None:
            user_id = UserId(str(case.get("user_id") or "0a000000-0000-4000-a000-000000000002"))
            persona = personas.get(tenant_id, persona_id)
            if persona is not None:
                persona.grants.append(Grant(user_id=user_id, capabilities=list(Capability)))
            active = MemoryItem(
                id=MemoryId(str(case.get("active_id") or "mem-conflict-old")),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("active_text") or ""),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
            )
            memories.save(active)
            vectors.upsert(tenant_id, persona_id, active.id, embed.embed(active.text), active.status)
            proposed = str(case.get("proposed_text") or "")
            inbox_id = str(case.get("inbox_id") or ids.new_id())
            inbox.add(
                InboxItem(
                    id=inbox_id,
                    tenant_id=tenant_id,
                    persona_id=persona_id,
                    kind="conflict",
                    payload={
                        "text": proposed,
                        "memory_type": "fact",
                        "conflicts_with": active.id.value,
                    },
                    status="pending",
                    conflicts_with=active.id,
                )
            )
            confirm(
                tenant_id=tenant_id,
                user_id=user_id,
                persona_id=persona_id,
                inbox_id=inbox_id,
                capabilities=list(Capability),
            )
            stored_old = memories.get(tenant_id, active.id)
            hits = vectors.search(tenant_id, persona_id, embed.embed(str(case.get("query") or proposed)), 5)
            hit_texts = [hit.text for hit, _ in hits]
            ok = (
                stored_old is not None
                and stored_old.status == MemoryStatus.SUPERSEDED
                and proposed in hit_texts
                and str(case.get("active_text") or "") not in hit_texts
            )
            if str(case.get("active_text") or "") in hit_texts:
                conflict_injections += 1

        elif action == "retrieval_helpfulness":
            item = MemoryItem(
                id=MemoryId(str(case.get("memory_id") or ids.new_id())),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("text") or ""),
                type=MemoryType.EPISODE_SUMMARY,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.EPISODIC,
            )
            memories.save(item)
            vectors.upsert(tenant_id, persona_id, item.id, embed.embed(item.text), item.status)
            helpful_queries += 1
            hits = vectors.search(tenant_id, persona_id, embed.embed(str(case.get("query") or "")), 5)
            ok = any(hit.id == item.id for hit, _ in hits)
            if ok:
                helpful_hits += 1

        elif action == "working_memory_run_scoped":
            run_id = str(case.get("run_id") or "run-a")
            other_run = str(case.get("other_run_id") or "run-b")
            scoped = MemoryItem(
                id=MemoryId(str(case.get("memory_id") or "mem-working-a")),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("text") or "run scoped note"),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.WORKING,
                source={"run_id": run_id, "expires_at": "2099-01-01T00:00:00Z"},
            )
            foreign = MemoryItem(
                id=MemoryId(str(case.get("foreign_id") or "mem-working-b")),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("foreign_text") or "foreign note"),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.WORKING,
                source={"run_id": other_run, "expires_at": "2099-01-01T00:00:00Z"},
            )
            memories.save(scoped)
            memories.save(foreign)
            vectors.upsert(tenant_id, persona_id, scoped.id, embed.embed(scoped.text), scoped.status)
            vectors.upsert(tenant_id, persona_id, foreign.id, embed.embed(foreign.text), foreign.status)
            ok = is_memory_searchable(scoped, run_id=run_id) and not is_memory_searchable(
                foreign, run_id=run_id
            )

        elif action == "working_memory_expired_excluded":
            item = MemoryItem(
                id=MemoryId(str(case.get("memory_id") or "mem-working-expired")),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("text") or "expired working"),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.WORKING,
                source={
                    "run_id": str(case.get("run_id") or "run-a"),
                    "expires_at": str(case.get("expires_at") or "2020-01-01T00:00:00Z"),
                },
            )
            memories.save(item)
            vectors.upsert(tenant_id, persona_id, item.id, embed.embed(item.text), item.status)
            ok = not is_memory_searchable(item, run_id=str(case.get("run_id") or "run-a"))

        elif action == "working_memory_cleared_on_complete":
            run_id = str(case.get("run_id") or "run-complete")
            item = MemoryItem(
                id=MemoryId(str(case.get("memory_id") or "mem-working-clear")),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("text") or "clear on complete"),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.WORKING,
                source={"run_id": run_id},
            )
            memories.save(item)
            cleared = clear_working_memory_for_run(memories, tenant_id, persona_id, run_id)
            stored = memories.get(tenant_id, item.id)
            ok = cleared == 1 and stored is not None and stored.status == MemoryStatus.DELETED

        elif action == "procedural_draft_excluded":
            draft = MemoryItem(
                id=MemoryId(str(case.get("memory_id") or "mem-proc-draft")),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("text") or "draft SOP"),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.PROCEDURAL,
                source={"draft": True, "version": "v-next"},
            )
            published = MemoryItem(
                id=MemoryId(str(case.get("published_id") or "mem-proc-pub")),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text=str(case.get("published_text") or "published SOP"),
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.PROCEDURAL,
                source={"published": True, "version": "v1"},
            )
            memories.save(draft)
            memories.save(published)
            vectors.upsert(tenant_id, persona_id, draft.id, embed.embed(draft.text), draft.status)
            vectors.upsert(tenant_id, persona_id, published.id, embed.embed(published.text), published.status)
            ok = not is_memory_searchable(draft) and is_memory_searchable(published)

        elif action == "procedural_pinned_version":
            v1 = MemoryItem(
                id=MemoryId("mem-proc-v1"),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text="SOP v1",
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.PROCEDURAL,
                source={"published": True, "version": "v1"},
            )
            v2 = MemoryItem(
                id=MemoryId("mem-proc-v2"),
                tenant_id=tenant_id,
                persona_id=persona_id,
                text="SOP v2",
                type=MemoryType.FACT,
                status=MemoryStatus.ACTIVE,
                memory_class=MemoryClass.PROCEDURAL,
                source={"published": True, "version": "v2"},
            )
            memories.save(v1)
            memories.save(v2)
            ok = is_memory_searchable(v1, pinned_procedural_version="v1") and not is_memory_searchable(
                v2, pinned_procedural_version="v1"
            )

        elif action == "procedural_agent_write_blocked" and confirm is not None and inbox is not None:
            user_id = UserId(str(case.get("user_id") or "0a000000-0000-4000-a000-000000000002"))
            persona = personas.get(tenant_id, persona_id)
            if persona is not None:
                persona.grants.append(Grant(user_id=user_id, capabilities=list(Capability)))
            inbox_id = str(case.get("inbox_id") or ids.new_id())
            payload = {
                "text": str(case.get("text") or "agent SOP override"),
                "memory_type": "fact",
                "memory_class": "procedural",
                "source_run_id": str(case.get("run_id") or "run-agent"),
            }
            inbox.add(
                InboxItem(
                    id=inbox_id,
                    tenant_id=tenant_id,
                    persona_id=persona_id,
                    kind="extract",
                    payload=payload,
                    status="pending",
                )
            )
            blocked = False
            try:
                confirm(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    persona_id=persona_id,
                    inbox_id=inbox_id,
                    capabilities=list(Capability),
                )
            except DomainError:
                blocked = True
            ok = blocked and not agent_may_write_procedural(payload)

        results.append({"id": case["id"], "ok": ok})

    passed = sum(1 for row in results if row.get("ok"))
    total = len(results)
    duplicate_rate = duplicate_pairs / total if total else 0.0
    stale_rate = stale_injections / total if total else 0.0
    write_precision = writes_correct / writes_attempted if writes_attempted else 1.0
    conflict_rate = conflict_injections / total if total else 0.0
    helpfulness_rate = helpful_hits / helpful_queries if helpful_queries else 1.0
    return {
        "suite_version": payload.get("suite_version"),
        "gate_pass_rate": passed / total if total else 0.0,
        "duplicate_memory_rate": duplicate_rate,
        "stale_memory_injection_rate": stale_rate,
        "conflict_injection_rate": conflict_rate,
        "memory_write_precision": write_precision,
        "memory_helpfulness_rate": helpfulness_rate,
        "deletion_completeness_rate": 1.0 if all(
            row.get("ok") for row in results if row.get("id") == "delete-completeness"
        ) else 0.0,
        "cases": results,
    }
