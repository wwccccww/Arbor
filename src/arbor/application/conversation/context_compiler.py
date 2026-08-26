from __future__ import annotations

from dataclasses import dataclass, field

from arbor.application.conversation.context_budget import (
    estimate_json_tokens,
    estimate_prompt_slots_tokens,
    estimate_tokens,
    trim_recent_turn,
    truncate_text,
)
from arbor.application.evaluation.generation import injected_contexts
from arbor.application.retrieval import retrieve
from arbor.domain.conversation.context_policy import ContextPolicy, ContextSlots
from arbor.domain.conversation.thread import Thread
from arbor.domain.memory.memory import MemoryItem
from arbor.domain.persona.authorization import Capability
from arbor.domain.persona.persona import Persona
from arbor.domain.shared.ids import PersonaId, TenantId
from arbor.env import (
    context_max_output_tokens,
    context_recent_k,
    context_system_overhead_tokens,
    context_window_tokens,
    tool_mode,
)
from arbor.application.tools.run_tools import allowed_tool_names


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
    ) -> None:
        self.policy = policy or ContextPolicy()
        self.strategy = strategy
        self.context_window = context_window if context_window is not None else context_window_tokens()
        self.reserved_output = reserved_output if reserved_output is not None else context_max_output_tokens()
        self.system_overhead = system_overhead if system_overhead is not None else context_system_overhead_tokens()
        self.recent_k = recent_k if recent_k is not None else context_recent_k()

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
    ) -> CompiledContext:
        retrieval_strategy = self.strategy if Capability.READ_MEMORY in capabilities else "summary_only"
        retrieved = retrieve(
            strategy=retrieval_strategy,
            query=query,
            tenant_id=tenant_id,
            persona_id=persona_id,
            k=5,
            memories=memories,
            events=event_nodes,
            summary=thread.summary,
            vector_search=vector_search,
            embed=embed,
        )
        hits: list[MemoryItem] = []
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

        recent_turns = self._recent_turns(thread)
        slots.recent_turns = recent_turns

        prompt_slots = {
            "profile": slots.profile,
            "tool_policy": slots.tool_policy,
            "tool_results": list(tool_results or []),
            "thread_summary": slots.thread_summary,
            "recent_turns": list(slots.recent_turns),
            "event_hits": slots.event_hits,
            "memory_hits": [m.text for m in slots.memory_hits],
            "llm_tool_calls_enabled": tool_mode() in {"llm", "both"},
            "allowed_tool_names": sorted(allowed_tool_names(persona.tool_policy)),
        }

        budget = self._slot_budget(user_text)
        notes: list[str] = []
        prompt_slots, slots, notes = self._fit_budget(prompt_slots, slots, budget, notes)

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
    ) -> tuple[dict, ContextSlots, list[str]]:
        guard = 0
        while estimate_prompt_slots_tokens(prompt_slots) > budget and guard < 64:
            guard += 1
            if self._trim_tool_results(prompt_slots, notes):
                continue
            if self._trim_memory_hits(prompt_slots, slots, notes):
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

    def _trim_memory_hits(self, prompt_slots: dict, slots: ContextSlots, notes: list[str]) -> bool:
        texts = list(prompt_slots.get("memory_hits") or [])
        if not texts:
            return False
        prompt_slots["memory_hits"] = texts[:-1]
        if slots.memory_hits:
            removed = slots.memory_hits.pop()
            slots.injected_memory_ids = [m.id.value for m in slots.memory_hits]
            notes.append(f"trim_memory:{removed.id.value}")
        return True

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
