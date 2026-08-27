from __future__ import annotations

from dataclasses import dataclass, field

from arbor.application.conversation.context_budget import (
    estimate_prompt_slots_tokens,
    estimate_tokens,
    trim_recent_turn,
    truncate_text,
)
from arbor.application.conversation.context_injection import (
    detect_context_conflicts,
    memory_hit_payload,
)
from arbor.application.evaluation.generation import injected_contexts
from arbor.application.retrieval import retrieve
from arbor.application.retrieval_config import RetrievalConfig
from arbor.application.tools.run_tools import allowed_tool_names
from arbor.domain.conversation.context_policy import ContextPolicy, ContextSlots
from arbor.domain.conversation.thread import Thread
from arbor.domain.eventgraph.graph import EventEdge
from arbor.domain.memory.memory import MemoryItem
from arbor.domain.persona.authorization import Capability
from arbor.domain.persona.persona import Persona
from arbor.domain.shared.ids import PersonaId, TenantId
from arbor.env import (
    context_max_output_tokens,
    context_recent_k,
    context_system_overhead_tokens,
    context_window_tokens,
    retrieval_prompt_k,
    tool_mode,
)


@dataclass
class CompiledContext:
    slots: ContextSlots
    prompt_slots: dict
    hits: list[MemoryItem]
    injected_memory_ids: list[str]
    injected_contexts: list[str]
    token_budget: int
    token_estimate: int
    truncation_notes: list[str] = field(default_factory=list)
    retrieval_meta: dict = field(default_factory=dict)


class ContextCompiler:
    """Compile persona/thread state into LLM prompt slots with token budgeting."""

    def __init__(
        self,
        *,
        policy: ContextPolicy | None = None,
        strategy: str = "layered_tree",
        context_window: int | None = None,
        reserved_output: int | None = None,
        system_overhead: int | None = None,
        recent_k: int | None = None,
        retrieval_config: RetrievalConfig | None = None,
    ) -> None:
        self.policy = policy or ContextPolicy()
        self.strategy = strategy
        self.context_window = context_window if context_window is not None else context_window_tokens()
        self.reserved_output = reserved_output if reserved_output is not None else context_max_output_tokens()
        self.system_overhead = system_overhead if system_overhead is not None else context_system_overhead_tokens()
        self.recent_k = recent_k if recent_k is not None else context_recent_k()
        self.retrieval_config = retrieval_config or RetrievalConfig.from_env()

    def compile(
        self,
        *,
        persona: Persona,
        thread: Thread,
        query: str,
        capabilities: list[Capability],
        tenant_id: TenantId,
        persona_id: PersonaId,
        memories: list[MemoryItem],
        event_nodes: list,
        vector_search,
        embed,
        user_text: str,
        tool_results: list | None = None,
        event_edges: list[EventEdge] | None = None,
        lexical_search=None,
    ) -> CompiledContext:
        retrieval_strategy = self.strategy if Capability.READ_MEMORY in capabilities else "summary_only"
        prompt_k = retrieval_prompt_k()
        retrieved = retrieve(
            strategy=retrieval_strategy,
            query=query,
            tenant_id=tenant_id,
            persona_id=persona_id,
            k=prompt_k,
            memories=memories,
            events=event_nodes,
            edges=event_edges,
            summary=thread.summary,
            vector_search=vector_search,
            embed=embed,
            config=self.retrieval_config,
            lexical_search=lexical_search,
        )
        hit_scores = dict(retrieved.get("hit_scores") or {})
        trim_priority = list(retrieved.get("trim_priority") or [])
        sources = dict(retrieved.get("sources") or {})

        hits: list[MemoryItem] = []
        conflict_notes: list[str] = []
        if Capability.READ_MEMORY not in capabilities:
            slots = self.policy.build_without_memory(persona.profile, summary="")
            event_payload: list[dict] = []
        else:
            hits = list(retrieved["hits"])
            event_payload = [
                {"id": e.id.value, "title": e.title, "summary": e.summary} for e in retrieved["event_nodes"]
            ]
            slots = self.policy.assemble(
                profile=persona.profile,
                capabilities=capabilities,
                summary=thread.summary,
                event_hits=event_payload,
                memory_hits=hits,
                tool_policy=persona.tool_policy,
            )
            for item in hits:
                mid = item.id.value
                if mid not in slots.injected_memory_ids:
                    slots.injected_memory_ids.append(mid)
            conflict_notes = detect_context_conflicts(slots.profile, slots.memory_hits)

        recent_turns = self._recent_turns(thread)
        slots.recent_turns = recent_turns

        memory_payloads = [
            memory_hit_payload(
                item,
                source=sources.get(item.id.value, ""),
                score=hit_scores.get(item.id.value),
            )
            for item in slots.memory_hits
        ]

        prompt_slots = {
            "profile": slots.profile,
            "tool_policy": slots.tool_policy,
            "tool_results": list(tool_results or []),
            "thread_summary": slots.thread_summary,
            "recent_turns": list(slots.recent_turns),
            "event_hits": slots.event_hits,
            "memory_hits": memory_payloads,
            "llm_tool_calls_enabled": tool_mode() in {"llm", "both"},
            "allowed_tool_names": sorted(allowed_tool_names(persona.tool_policy)),
        }

        budget = self._slot_budget(user_text)
        notes: list[str] = []
        if conflict_notes:
            notes.extend(conflict_notes)
        prompt_slots, slots, notes = self._fit_budget(
            prompt_slots,
            slots,
            budget,
            notes,
            trim_priority=trim_priority,
            hit_scores=hit_scores,
        )

        retrieval_meta = {
            "strategy": retrieved.get("strategy"),
            "hit_ids": list(retrieved.get("hit_ids") or []),
            "sources": sources,
            "hit_scores": hit_scores,
            "trim_priority": trim_priority,
            "per_source_counts": dict(retrieved.get("per_source_counts") or {}),
            "sub_queries": list(retrieved.get("sub_queries") or []),
        }

        injected_contexts_list = injected_contexts(prompt_slots)
        return CompiledContext(
            slots=slots,
            prompt_slots=prompt_slots,
            hits=hits,
            injected_memory_ids=list(slots.injected_memory_ids),
            injected_contexts=injected_contexts_list,
            token_budget=budget,
            token_estimate=estimate_prompt_slots_tokens(prompt_slots) + self.system_overhead,
            truncation_notes=notes,
            retrieval_meta=retrieval_meta,
        )

    def apply_tool_results(self, compiled: CompiledContext, tool_results: list) -> CompiledContext:
        compiled.prompt_slots["tool_results"] = list(tool_results)
        budget = compiled.token_budget
        notes = list(compiled.truncation_notes)
        prompt_slots, slots, notes = self._fit_budget(
            compiled.prompt_slots,
            compiled.slots,
            budget,
            notes,
            trim_priority=compiled.retrieval_meta.get("trim_priority") or [],
            hit_scores=dict(compiled.retrieval_meta.get("hit_scores") or {}),
        )
        compiled.slots = slots
        compiled.prompt_slots = prompt_slots
        compiled.injected_memory_ids = list(slots.injected_memory_ids)
        compiled.injected_contexts = injected_contexts(prompt_slots)
        compiled.truncation_notes = notes
        compiled.token_estimate = estimate_prompt_slots_tokens(prompt_slots) + self.system_overhead
        return compiled

    def _slot_budget(self, user_text: str) -> int:
        user_reserve = estimate_tokens(user_text) + 32
        return max(
            256,
            self.context_window - self.reserved_output - self.system_overhead - user_reserve,
        )

    def _recent_turns(self, thread: Thread) -> list[dict]:
        if self.recent_k <= 0:
            return []
        messages = [m for m in thread.messages if (m.content or "").strip()]
        tail = messages[-self.recent_k:]
        turns: list[dict] = []
        for msg in tail:
            role = (msg.role or "user").strip()
            content = (msg.content or "").strip()
            if not content:
                continue
            turns.append({"role": role, "content": content})
        return turns

    def _fit_budget(
        self,
        prompt_slots: dict,
        slots: ContextSlots,
        budget: int,
        notes: list[str],
        *,
        trim_priority: list[str],
        hit_scores: dict[str, float],
    ) -> tuple[dict, ContextSlots, list[str]]:
        guard = 0
        while estimate_prompt_slots_tokens(prompt_slots) > budget and guard < 64:
            guard += 1
            if self._trim_tool_results(prompt_slots, notes):
                continue
            if self._trim_memory_hits(prompt_slots, slots, notes, trim_priority, hit_scores):
                continue
            if self._trim_event_hits(prompt_slots, slots, notes):
                continue
            if self._trim_recent_turns(prompt_slots, slots, notes):
                continue
            if self._trim_summary(prompt_slots, slots, notes):
                continue
            break
        return prompt_slots, slots, notes

    def _trim_tool_results(self, prompt_slots: dict, notes: list[str]) -> bool:
        results = prompt_slots.get("tool_results") or []
        if not results:
            return False
        prompt_slots["tool_results"] = results[:-1]
        notes.append("trim_tool_results")
        return True

    def _trim_memory_hits(
        self,
        prompt_slots: dict,
        slots: ContextSlots,
        notes: list[str],
        trim_priority: list[str],
        hit_scores: dict[str, float],
    ) -> bool:
        payloads = list(prompt_slots.get("memory_hits") or [])
        if not payloads or not slots.memory_hits:
            return False
        remove_id = self._lowest_score_memory_id(slots.memory_hits, trim_priority, hit_scores)
        if remove_id is None:
            removed_item = slots.memory_hits[-1]
        else:
            removed_item = next(
                (m for m in slots.memory_hits if m.id.value == remove_id),
                slots.memory_hits[-1],
            )
        prompt_slots["memory_hits"] = [p for p in payloads if p.get("id") != removed_item.id.value]
        slots.memory_hits = [m for m in slots.memory_hits if m.id.value != removed_item.id.value]
        slots.injected_memory_ids = [m.id.value for m in slots.memory_hits]
        notes.append(f"trim_memory:{removed_item.id.value}")
        return True

    def _lowest_score_memory_id(
        self,
        memories: list[MemoryItem],
        trim_priority: list[str],
        hit_scores: dict[str, float],
    ) -> str | None:
        if trim_priority:
            for memory_id in trim_priority:
                if any(memory.id.value == memory_id for memory in memories):
                    return memory_id
        if not memories:
            return None
        return min(memories, key=lambda memory: hit_scores.get(memory.id.value, 0.0)).id.value

    def _trim_event_hits(self, prompt_slots: dict, slots: ContextSlots, notes: list[str]) -> bool:
        events = list(prompt_slots.get("event_hits") or [])
        if not events:
            return False
        prompt_slots["event_hits"] = events[:-1]
        slots.event_hits = list(prompt_slots["event_hits"])
        notes.append("trim_event_hits")
        return True

    def _trim_recent_turns(self, prompt_slots: dict, slots: ContextSlots, notes: list[str]) -> bool:
        turns = list(prompt_slots.get("recent_turns") or [])
        if not turns:
            return False
        longest_idx = max(range(len(turns)), key=lambda i: len(str(turns[i].get("content") or "")))
        longest = turns[longest_idx]
        content = str(longest.get("content") or "")
        if len(content) > 120:
            turns[longest_idx] = trim_recent_turn(longest, max(80, len(content) // 2))
            prompt_slots["recent_turns"] = turns
            slots.recent_turns = turns
            notes.append("truncate_recent_turn")
            return True
        prompt_slots["recent_turns"] = turns[:-1]
        slots.recent_turns = list(prompt_slots["recent_turns"])
        notes.append("drop_recent_turn")
        return True

    def _trim_summary(self, prompt_slots: dict, slots: ContextSlots, notes: list[str]) -> bool:
        summary = str(prompt_slots.get("thread_summary") or "")
        if not summary:
            return False
        if len(summary) > 80:
            trimmed = truncate_text(summary, max(40, len(summary) // 2))
            prompt_slots["thread_summary"] = trimmed
            slots.thread_summary = trimmed
            notes.append("truncate_summary")
            return True
        prompt_slots["thread_summary"] = ""
        slots.thread_summary = ""
        notes.append("drop_summary")
        return True
