from __future__ import annotations

import json
from dataclasses import dataclass

from arbor.application.conversation.compress_thread_summary import compress_thread_summary
from arbor.application.retrieval import retrieve
from arbor.application.tools.run_tools import run_persona_tools
from arbor.domain.conversation.context_policy import ContextPolicy
from arbor.domain.conversation.stream import StreamFinished, parse_model_out
from arbor.domain.conversation.thread import Citation, Message, Thread
from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import InboxItem, MemoryItem
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId, ThreadId, UserId
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
                text=text,
                injected_memory_ids=list(ctx.slots.injected_memory_ids),
            )
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
        result = self._finish(ctx, merged)
        yield StreamFinished(json.dumps(result, ensure_ascii=False))

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

        policy = ContextPolicy()
        event_nodes = self.events.list_nodes(tenant_id, persona_id)
        active = self.memories.list_active(tenant_id, persona_id)
        stored_attachments = _normalize_attachments(attachments)
        llm_text = self._enrich_text_with_attachments(text, stored_attachments)
        retrieved = retrieve(
            strategy=self.strategy if Capability.READ_MEMORY in caps else "summary_only",
            query=llm_text,
            tenant_id=tenant_id,
            persona_id=persona_id,
            k=5,
            memories=active,
            events=event_nodes,
            summary=thread.summary,
            vector_search=self.vectors.search,
            embed=self.embed.embed,
        )
        if Capability.READ_MEMORY not in caps:
            slots = policy.build_without_memory(persona.profile, summary="")
            event_payload = []
            hits: list[MemoryItem] = []
        else:
            hits = retrieved["hits"]
            event_payload = [
                {"id": e.id.value, "title": e.title, "summary": e.summary} for e in retrieved["event_nodes"]
            ]
            slots = policy.assemble(
                profile=persona.profile,
                capabilities=caps,
                summary=thread.summary,
                event_hits=event_payload,
                memory_hits=hits,
                tool_policy=persona.tool_policy,
            )
            extra_ids = [m.id.value for m in hits]
            for mid in extra_ids:
                if mid not in slots.injected_memory_ids:
                    slots.injected_memory_ids.append(mid)

        prompt_slots = {
            "profile": slots.profile,
            "tool_policy": slots.tool_policy,
            "tool_results": run_persona_tools(
                llm_text,
                persona.tool_policy,
                tenant_id=tenant_id,
                user_id=user_id,
                calendar_tool=self.calendar_tool,
            ),
            "thread_summary": slots.thread_summary,
            "event_hits": slots.event_hits,
            "memory_hits": [m.text for m in slots.memory_hits],
        }
        extracted = self.reasoner.extract(text) if self.reasoner else None
        inbox_added = 0
        if extracted and extracted.get("text"):
            item = InboxItem(
                id=self.ids.new_id(),
                tenant_id=tenant_id,
                persona_id=persona_id,
                kind=extracted.get("kind", "fact"),
                payload={"text": extracted["text"]},
            )
            self.inbox.add(item)
            inbox_added = 1
        return _Context(
            tenant_id=tenant_id,
            persona_id=persona_id,
            thread=thread,
            text=text,
            llm_text=llm_text,
            caps=caps,
            slots=slots,
            prompt_slots=prompt_slots,
            hits=hits,
            stored_attachments=stored_attachments,
            inbox_added=inbox_added,
        )

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
            "injected_contexts": [
                "档案: " + " ".join(f"{k}={v}" for k, v in (ctx.prompt_slots.get("profile") or {}).items() if v),
                *(["摘要: " + ctx.prompt_slots["thread_summary"]] if ctx.prompt_slots.get("thread_summary") else []),
                *[
                    f"事件: {event.get('title', '')} {event.get('summary', '')}".strip()
                    if isinstance(event, dict)
                    else f"事件: {event}"
                    for event in ctx.prompt_slots.get("event_hits") or []
                ],
                *[str(memory) for memory in ctx.prompt_slots.get("memory_hits") or [] if memory],
            ],
            "slot_order": ctx.slots.slot_order(),
            "prompt_slots": ctx.prompt_slots,
            "inbox_added": ctx.inbox_added,
            "attachments": [{"filename": item["filename"]} for item in ctx.stored_attachments],
        }


@dataclass
class _Context:
    tenant_id: TenantId
    persona_id: PersonaId
    thread: Thread
    text: str
    llm_text: str
    caps: list[Capability]
    slots: object
    prompt_slots: dict
    hits: list[MemoryItem]
    stored_attachments: list[dict]
    inbox_added: int


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
