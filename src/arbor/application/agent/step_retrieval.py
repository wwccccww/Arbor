from __future__ import annotations

from arbor.application.agent.context_engine import (
    ContextItem,
    ContextItemKind,
    compile_context_items,
    context_item_from_memory,
    detect_untrusted_instructions,
)
from arbor.application.agent.retrieval_dto import (
    RetrievalCandidate,
    RetrievalRequest,
    RetrievalResult,
)
from arbor.application.retrieval import retrieve
from arbor.application.retrieval_config import RetrievalConfig
from arbor.domain.persona.authorization import Capability


class StepRetrieval:
    def __init__(
        self,
        *,
        memories,
        events,
        vector_search,
        embed,
        retrieval_config: RetrievalConfig | None = None,
        lexical_search=None,
        observability=None,
    ) -> None:
        self.memories = memories
        self.events = events
        self.vector_search = vector_search
        self.embed = embed
        self.retrieval_config = retrieval_config or RetrievalConfig.from_env()
        self.lexical_search = lexical_search
        self.observability = observability

    def execute(
        self,
        request: RetrievalRequest,
        *,
        capabilities: list[Capability],
        summary: str = "",
    ) -> RetrievalResult:
        tenant_id = request.tenant_id
        persona_id = request.persona_id
        memories = (
            self.memories.list_active(tenant_id, persona_id)
            if Capability.READ_MEMORY in capabilities
            else []
        )
        if request.filters and request.filters.get("memory_classes"):
            allowed = {str(v) for v in request.filters["memory_classes"]}
            memories = [
                m
                for m in memories
                if m.memory_class is not None and m.memory_class.value in allowed
            ]
        event_nodes = self.events.list_nodes(tenant_id, persona_id)
        event_edges = self.events.list_edges(tenant_id, persona_id)
        retrieved = retrieve(
            strategy="layered_tree",
            query=request.query,
            tenant_id=tenant_id,
            persona_id=persona_id,
            k=request.k,
            memories=memories,
            events=event_nodes,
            edges=event_edges,
            summary=summary,
            vector_search=self.vector_search,
            embed=self.embed,
            config=self.retrieval_config,
            lexical_search=self.lexical_search,
            observability=self.observability,
        )
        hit_scores = dict(retrieved.get("hit_scores") or {})
        sources = dict(retrieved.get("sources") or {})
        candidates = []
        for item in retrieved.get("hits") or []:
            mid = item.id.value
            candidates.append(
                RetrievalCandidate(
                    memory_id=mid,
                    text=item.text or "",
                    source=sources.get(mid, ""),
                    score=hit_scores.get(mid),
                    memory_class=item.memory_class.value if item.memory_class else None,
                )
            )
        return RetrievalResult(
            candidates=candidates,
            strategy=str(retrieved.get("strategy") or "layered_tree"),
            hit_ids=list(retrieved.get("hit_ids") or []),
            source_counts=dict(retrieved.get("per_source_counts") or {}),
            sub_queries=list(retrieved.get("sub_queries") or []),
            query_plan=str(retrieved.get("query_plan") or ""),
        )


def build_step_context_items(
    *,
    goal: str,
    persona_profile: dict,
    evidence_ids: list[str],
    memories_by_id: dict[str, object],
    tool_results: list[dict],
    token_budget: int = 4000,
) -> tuple[list[ContextItem], dict]:
    items: list[ContextItem] = []
    items.append(
        ContextItem(
            id="policy:tenant_isolation",
            kind=ContextItemKind.POLICY,
            content="不得跨租户读取记忆或执行未授权工具。",
            trust_level="system",
            required=True,
            token_count=32,
        )
    )
    items.append(
        ContextItem(
            id="task:goal",
            kind=ContextItemKind.TASK,
            content=goal,
            trust_level="system",
            required=True,
            token_count=max(1, len(goal) // 4),
        )
    )
    if persona_profile:
        profile_text = str(persona_profile.get("display_name") or "")
        items.append(
            ContextItem(
                id="identity:profile",
                kind=ContextItemKind.IDENTITY,
                content=profile_text,
                trust_level="system",
                required=True,
                token_count=max(1, len(profile_text) // 4),
            )
        )
    for memory_id in evidence_ids:
        item = memories_by_id.get(memory_id)
        if item is None:
            continue
        items.append(
            context_item_from_memory(
                memory_id,
                item.text or "",
                source="memory",
                score=None,
                trust_level="evidence",
            )
        )
    for index, result in enumerate(tool_results or []):
        text = str(result)
        items.append(
            ContextItem(
                id=f"tool_result:{index}",
                kind=ContextItemKind.TOOL_RESULT,
                content=text,
                trust_level="untrusted",
                token_count=max(1, len(text) // 4),
                metadata={"tool": result.get("tool") if isinstance(result, dict) else None},
            )
        )
    selected, manifest = compile_context_items(items, token_budget=token_budget)
    manifest_dict = manifest.to_dict()
    manifest_dict["untrusted_instruction_total"] = sum(
        detect_untrusted_instructions(item.content) for item in selected if item.trust_level == "untrusted"
    )
    return selected, manifest_dict
