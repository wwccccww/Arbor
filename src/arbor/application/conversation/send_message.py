from __future__ import annotations

import json
from dataclasses import dataclass

from arbor.application.conversation.compress_thread_summary import compress_thread_summary
from arbor.application.conversation.context_compiler import ContextCompiler
from arbor.application.memory.conflict_detection import enrich_inbox_extract
from arbor.application.tools.execute import execute_tool_calls
from arbor.application.tools.run_tools import allowed_tool_names, run_persona_tools
from arbor.domain.conversation.context_policy import ContextSlots
from arbor.domain.conversation.stream import StreamFinished, parse_model_out
from arbor.domain.conversation.thread import Citation, Message, Thread
from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import InboxItem, MemoryItem
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId, ThreadId, UserId
from arbor.env import tool_mode
from arbor.ports.outbound import (
    EmbeddingClient,
    EventGraphRepository,
    InboxRepository,
    LLMClient,
    MemoryRepository,
    PersonaRepository,
    ReasoningClient,
    ThreadRepository,
    VectorIndex,
)


@dataclass
class SendMessage:
    personas: PersonaRepository
    memories: MemoryRepository
    threads: ThreadRepository
    events: EventGraphRepository
    inbox: InboxRepository
    vectors: VectorIndex
    llm: LLMClient
    reasoner: ReasoningClient
    embed: EmbeddingClient
    ids: object
    auth: AuthorizationPolicy
    strategy: str = "layered_tree"
    storage: object | None = None
    enrich_with_vision: bool = True
    vision_enrich: object | None = None
    calendar_tool: object | None = None
    ticket_tool: object | None = None
    context_compiler: ContextCompiler | None = None

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        thread_id: ThreadId,
        persona_id: PersonaId,
        text: str,
        capabilities: list[Capability] | None = None,
        attachments: list | None = None,
    ) -> dict:
        ctx = self._prepare(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            persona_id=persona_id,
            text=text,
            capabilities=capabilities,
            attachments=attachments,
        )
        llm_out = self.llm.complete(
            prompt_slots=ctx.prompt_slots,
            text=ctx.llm_text,
            injected_memory_ids=list(ctx.slots.injected_memory_ids),
        )
        llm_out = self._maybe_llm_tool_round(ctx, llm_out)
        return self._finish(ctx, llm_out)

    def stream_reply(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        thread_id: ThreadId,
        persona_id: PersonaId,
        text: str,
        capabilities: list[Capability] | None = None,
        attachments: list | None = None,
    ):
        """Stream the assistant reply as text deltas, then persist and yield a
        final ``StreamFinished`` sentinel describing the complete response.

        Yields ``str`` chunks (for the UI to render incrementally) and ends with
        a :class:`StreamFinished` whose ``raw`` field is the model envelope the
        caller can parse for ``text``/``citations``.
        """
        ctx = self._prepare(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            persona_id=persona_id,
            text=text,
            capabilities=capabilities,
            attachments=attachments,
        )
        streaming = getattr(self.llm, "complete_stream", None)
        if streaming is None:
            llm_out = self.llm.complete(
                prompt_slots=ctx.prompt_slots,
                text=ctx.llm_text,
                injected_memory_ids=list(ctx.slots.injected_memory_ids),
            )
            llm_out = self._maybe_llm_tool_round(ctx, llm_out)
            result = self._finish(ctx, llm_out)
            for piece in result["text"]:
                yield piece
            yield StreamFinished(json.dumps(result, ensure_ascii=False))
            return

        deltas: list[str] = []
        parsed: dict | None = None
        for chunk in streaming(
            prompt_slots=ctx.prompt_slots,
            text=ctx.llm_text,
            injected_memory_ids=list(ctx.slots.injected_memory_ids),
        ):
            if isinstance(chunk, StreamFinished):
                parsed = parse_model_out(chunk.raw)
                break
            if isinstance(chunk, str) and chunk:
                deltas.append(chunk)
                yield chunk

        merged = dict(parsed or {})
        merged["text"] = merged.get("text", "") or "".join(deltas)
        citations = [c for c in (merged.get("citations") or []) if c in ctx.slots.injected_memory_ids]
        merged["citations"] = citations
        merged = self._maybe_llm_tool_round(ctx, merged)
        if merged.pop("tool_round_applied", False):
            from arbor.domain.conversation.stream import chunk_text

            for piece in chunk_text(merged.get("text") or ""):
                yield piece
        result = self._finish(ctx, merged)
        yield StreamFinished(json.dumps(result, ensure_ascii=False))

    def _compiler(self) -> ContextCompiler:
        if self.context_compiler is not None:
            return self.context_compiler
        return ContextCompiler(strategy=self.strategy)

    def _prepare(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        thread_id: ThreadId,
        persona_id: PersonaId,
        text: str,
        capabilities: list[Capability] | None,
        attachments: list | None,
    ) -> _Context:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        thread = self.threads.get(tenant_id, thread_id)
        if thread is None:
            thread = Thread(id=thread_id, tenant_id=tenant_id, persona_id=persona_id)
        if not self.auth.can_chat(persona, user_id) and Capability.CHAT not in caps:
            raise DomainError("FORBIDDEN_CHAT", "chat grant required")

        stored_attachments = _normalize_attachments(attachments)
        llm_text = self._enrich_text_with_attachments(text, stored_attachments)
        active = self.memories.list_active(tenant_id, persona_id)
        event_nodes = self.events.list_nodes(tenant_id, persona_id)
        event_edges = self.events.list_edges(tenant_id, persona_id)

        compiled = self._compiler().compile(
            persona=persona,
            thread=thread,
            query=llm_text,
            capabilities=caps,
            tenant_id=tenant_id,
            persona_id=persona_id,
            memories=active,
            event_nodes=event_nodes,
            vector_search=self.vectors.search,
            embed=self.embed.embed,
            user_text=llm_text,
            event_edges=event_edges,
            lexical_search=getattr(self.vectors, "lexical_search", None),
        )
        if tool_mode() in {"keywords", "both"}:
            tool_results = run_persona_tools(
                llm_text,
                persona.tool_policy,
                tenant_id=tenant_id,
                user_id=user_id,
                calendar_tool=self.calendar_tool,
                ticket_tool=self.ticket_tool,
            )
            compiled = self._compiler().apply_tool_results(compiled, tool_results)

        extracted = self.reasoner.extract(text, active_memories=active) if self.reasoner else None
        inbox_added = 0
        if extracted and extracted.get("text"):
            extracted = enrich_inbox_extract(extracted, active)
            conflict_raw = extracted.get("conflicts_with")
            conflicts_with = MemoryId(str(conflict_raw)) if conflict_raw else None
            item = InboxItem(
                id=self.ids.new_id(),
                tenant_id=tenant_id,
                persona_id=persona_id,
                kind=extracted.get("kind", "fact"),
                payload={"text": extracted["text"]},
                conflicts_with=conflicts_with,
            )
            self.inbox.add(item)
            inbox_added = 1
        return _Context(
            tenant_id=tenant_id,
            user_id=user_id,
            persona_id=persona_id,
            thread=thread,
            text=text,
            llm_text=llm_text,
            caps=caps,
            slots=compiled.slots,
            prompt_slots=compiled.prompt_slots,
            hits=compiled.hits,
            injected_contexts=compiled.injected_contexts,
            stored_attachments=stored_attachments,
            inbox_added=inbox_added,
            persona=persona,
            compiled=compiled,
        )

    def _maybe_llm_tool_round(self, ctx: _Context, llm_out: dict) -> dict:
        if tool_mode() not in {"llm", "both"}:
            return llm_out
        calls = llm_out.get("tool_calls") or []
        if not calls:
            return llm_out
        allowed = allowed_tool_names(ctx.persona.tool_policy)
        extra = execute_tool_calls(
            calls,
            allowed_tools=allowed,
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            query_text=ctx.llm_text,
            calendar_tool=self.calendar_tool,
            ticket_tool=self.ticket_tool,
        )
        if not extra:
            return llm_out
        merged_results = list(ctx.prompt_slots.get("tool_results") or []) + extra
        compiled = self._compiler().apply_tool_results(ctx.compiled, merged_results)
        ctx.compiled = compiled
        ctx.prompt_slots = compiled.prompt_slots
        ctx.slots = compiled.slots
        ctx.injected_contexts = compiled.injected_contexts
        follow_up = self.llm.complete(
            prompt_slots=ctx.prompt_slots,
            text=ctx.llm_text,
            injected_memory_ids=list(ctx.slots.injected_memory_ids),
        )
        follow_up["tool_calls"] = []
        follow_up["tool_round_applied"] = True
        return follow_up

    def _enrich_text_with_attachments(self, text: str, attachments: list[dict]) -> str:
        if self.vision_enrich is not None:
            return str(self.vision_enrich(text, attachments))
        if self.storage is None or not self.enrich_with_vision:
            return text
        return text

    def _finish(self, ctx: _Context, llm_out: dict) -> dict:
        allowed = set(ctx.slots.injected_memory_ids)
        citations = []
        for cid in llm_out.get("citations") or []:
            if cid in allowed:
                citations.append(cid)
        by_id = {item.id.value: item for item in ctx.hits}
        citation_items = [_citation_item(cid, by_id.get(cid)) for cid in citations]
        user_message_id = self.ids.new_id()
        assistant_message_id = self.ids.new_id()
        ctx.thread.append_message(
            Message(
                id=user_message_id,
                role="user",
                content=ctx.text,
                attachments=ctx.stored_attachments,
            ),
            can_chat=True,
        )
        ctx.thread.append_message(
            Message(
                id=assistant_message_id,
                role="assistant",
                content=llm_out.get("text", ""),
                citations=[Citation(memory_id=MemoryId(c)) for c in citations],
            ),
            can_chat=True,
        )
        summary = compress_thread_summary(ctx.thread, self.reasoner)
        if summary:
            ctx.thread.summary = summary
        self.threads.save(ctx.thread)
        return {
            "message_id": assistant_message_id,
            "text": llm_out.get("text", ""),
            "citations": citations,
            "citation_items": citation_items,
            "injected_memory_ids": list(ctx.slots.injected_memory_ids),
            "injected_contexts": list(ctx.injected_contexts),
            "slot_order": ctx.slots.slot_order(),
            "prompt_slots": ctx.prompt_slots,
            "context_token_budget": ctx.compiled.token_budget,
            "context_token_estimate": ctx.compiled.token_estimate,
            "context_truncation_notes": list(ctx.compiled.truncation_notes),
            "retrieval_meta": dict(ctx.compiled.retrieval_meta),
            "tool_results": list(ctx.prompt_slots.get("tool_results") or []),
            "inbox_added": ctx.inbox_added,
            "attachments": [{"filename": item["filename"]} for item in ctx.stored_attachments],
        }


@dataclass
class _Context:
    tenant_id: TenantId
    user_id: UserId
    persona_id: PersonaId
    thread: Thread
    text: str
    llm_text: str
    caps: list[Capability]
    slots: ContextSlots
    prompt_slots: dict
    hits: list[MemoryItem]
    injected_contexts: list[str]
    stored_attachments: list[dict]
    inbox_added: int
    persona: object
    compiled: object


def _normalize_attachments(raw) -> list[dict]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise DomainError("VALIDATION_ERROR", "attachments must be a list")
    items: list[dict] = []
    for item in raw:
        if isinstance(item, str):
            filename = item.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip()
            uri = ""
        elif isinstance(item, dict):
            filename = str(item.get("filename") or item.get("name") or "")
            filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip()
            uri = str(item.get("uri") or "").strip()
        else:
            raise DomainError("VALIDATION_ERROR", "invalid attachment")
        if not filename:
            raise DomainError("VALIDATION_ERROR", "attachment filename required")
        entry = {"filename": filename}
        if uri:
            entry["uri"] = uri
        items.append(entry)
    return items


def _citation_item(memory_id: str, item: MemoryItem | None) -> dict:
    preview = (item.text[:40] if item and item.text else "")
    return {
        "memory_id": memory_id,
        "event_id": item.event_id.value if item and item.event_id else None,
        "preview": preview,
    }
