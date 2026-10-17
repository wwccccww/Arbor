from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime

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
from arbor.env import agent_compat_chat, tool_mode
from arbor.observability.content_storage import store_encrypted_content_sample
from arbor.observability.context import current_request_context
from arbor.observability.decision_trace import (
    build_decision_trace_summary,
    decision_trace_expires_at,
)
from arbor.observability.eval_metrics import record_citation_violation
from arbor.observability.noop import NoopObservability
from arbor.observability.runtime import decision_trace_retention_days
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
    observability: object | None = None
    decision_traces: object | None = None
    agent_compat: object | None = None

    def _obs(self):
        return self.observability or NoopObservability()

    def _chat_model_label(self) -> str:
        label = getattr(self.llm, "observability_model", None)
        return str(label) if label else "scripted"

    def _record_llm_chat_metrics(self, *, model: str, duration_ms: float, stream: str) -> None:
        obs = self._obs()
        obs.event(
            "llm.chat",
            model=model,
            stream=stream,
            duration_ms=duration_ms,
            result="success",
            input_tokens=getattr(self.llm, "last_input_tokens", None),
            output_tokens=getattr(self.llm, "last_output_tokens", None),
        )
        if model != "scripted":
            from arbor.observability.llm import record_llm_usage

            record_llm_usage(
                obs,
                operation="chat",
                model=model,
                input_tokens=getattr(self.llm, "last_input_tokens", None),
                output_tokens=getattr(self.llm, "last_output_tokens", None),
                first_token_ms=getattr(self.llm, "last_first_token_ms", None),
            )
            obs.increment("arbor_llm_requests_total", operation="chat", model=model, result="success")

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
        persist: bool = True,
    ) -> dict:
        obs = self._obs()
        started = time.perf_counter()
        model = self._chat_model_label()
        result_label = "success"
        try:
            with obs.span(
                "conversation.send",
                stream="false",
                thread_id=thread_id.value,
                persona_id=persona_id.value,
            ):
                ctx = self._prepare(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    thread_id=thread_id,
                    persona_id=persona_id,
                    text=text,
                    capabilities=capabilities,
                    attachments=attachments,
                    persist=persist,
                )
                llm_started = time.perf_counter()
                llm_out = self.llm.complete(
                    prompt_slots=ctx.prompt_slots,
                    text=ctx.llm_text,
                    injected_memory_ids=list(ctx.slots.injected_memory_ids),
                )
                ctx.llm_duration_ms = round((time.perf_counter() - llm_started) * 1000, 2)
                self._record_llm_chat_metrics(model=model, duration_ms=ctx.llm_duration_ms, stream="false")
                llm_out = self._maybe_llm_tool_round(ctx, llm_out)
                return self._finish(ctx, llm_out, persist=persist)
        except Exception:
            result_label = "error"
            obs.increment("arbor_llm_requests_total", operation="chat", model=model, result="error")
            raise
        finally:
            duration = time.perf_counter() - started
            obs.observe("arbor_chat_duration_seconds", duration, model=model, result=result_label)
            obs.increment("arbor_chat_requests_total", stream="false", result=result_label)

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
        obs = self._obs()
        started = time.perf_counter()
        model = self._chat_model_label()
        result_label = "success"
        try:
            with obs.span(
                "conversation.send",
                stream="true",
                thread_id=thread_id.value,
                persona_id=persona_id.value,
            ):
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
                    llm_started = time.perf_counter()
                    llm_out = self.llm.complete(
                        prompt_slots=ctx.prompt_slots,
                        text=ctx.llm_text,
                        injected_memory_ids=list(ctx.slots.injected_memory_ids),
                    )
                    ctx.llm_duration_ms = round((time.perf_counter() - llm_started) * 1000, 2)
                    obs.event(
                        "llm.chat",
                        model=model,
                        stream="false",
                        duration_ms=ctx.llm_duration_ms,
                        result="success",
                    )
                    llm_out = self._maybe_llm_tool_round(ctx, llm_out)
                    result = self._finish(ctx, llm_out)
                    for piece in result["text"]:
                        yield piece
                    yield StreamFinished(json.dumps(result, ensure_ascii=False))
                    return

                llm_started = time.perf_counter()
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

                ctx.llm_duration_ms = round((time.perf_counter() - llm_started) * 1000, 2)
                self._record_llm_chat_metrics(model=model, duration_ms=ctx.llm_duration_ms, stream="true")
                merged = dict(parsed or {})
                merged["text"] = merged.get("text", "") or "".join(deltas)
                merged["citations"] = _filter_citations(
                    merged.get("citations") or [],
                    set(ctx.slots.injected_memory_ids),
                    self.observability,
                )
                merged = self._maybe_llm_tool_round(ctx, merged)
                if merged.pop("tool_round_applied", False):
                    from arbor.domain.conversation.stream import chunk_text

                    for piece in chunk_text(merged.get("text") or ""):
                        yield piece
                result = self._finish(ctx, merged)
                yield StreamFinished(json.dumps(result, ensure_ascii=False))
        except Exception:
            result_label = "error"
            obs.increment("arbor_llm_requests_total", operation="chat", model=model, result="error")
            raise
        finally:
            duration = time.perf_counter() - started
            obs.observe("arbor_chat_duration_seconds", duration, model=model, result=result_label)
            obs.increment("arbor_chat_requests_total", stream="true", result=result_label)

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
        persist: bool = True,
    ) -> _Context:
        obs = self._obs()
        with obs.span("auth.authorize", persona_id=persona_id.value):
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
            observability=self.observability,
        )
        retrieval_meta = dict(compiled.retrieval_meta or {})
        strategy = str(retrieval_meta.get("strategy") or self.strategy)
        hit_count = len(retrieval_meta.get("hit_ids") or [])
        if hit_count == 0:
            obs.increment("arbor_rag_empty_retrieval_total", strategy=strategy)
        for source, count in (retrieval_meta.get("per_source_counts") or {}).items():
            if int(count or 0) > 0:
                obs.increment("arbor_rag_hits_total", float(count), source=str(source))
        if tool_mode() in {"keywords", "both"}:
            tool_results = run_persona_tools(
                llm_text,
                persona.tool_policy,
                tenant_id=tenant_id,
                user_id=user_id,
                calendar_tool=self.calendar_tool,
                ticket_tool=self.ticket_tool,
                observability=self.observability,
            )
            compiled = self._compiler().apply_tool_results(compiled, tool_results)

        reasoner_meta: dict = {"called": False}
        extracted = None
        inbox_added = 0
        if persist:
            with obs.span("inbox.extract", thread_id=thread_id.value):
                if self.reasoner:
                    reasoner_started = time.perf_counter()
                    with obs.span("llm.extract", thread_id=thread_id.value):
                        extracted = self.reasoner.extract(text, active_memories=active)
                    reasoner_meta = {
                        "called": True,
                        "operation": "extract",
                        "duration_ms": round((time.perf_counter() - reasoner_started) * 1000, 2),
                        "result_kind": extracted.get("kind") if extracted else None,
                        "conflicts_with": extracted.get("conflicts_with") if extracted else None,
                    }
                    obs.event(
                        "llm.extract",
                        result_kind=reasoner_meta.get("result_kind"),
                        duration_ms=reasoner_meta.get("duration_ms"),
                        result="parsed" if extracted else "skipped",
                    )
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
                        created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    )
                    self.inbox.add(item)
                    inbox_added = 1
                    obs.event("inbox.extract", result="created", kind=item.kind)
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
            reasoner_meta=reasoner_meta,
            llm_duration_ms=0.0,
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
            observability=self.observability,
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

    def _finish(self, ctx: _Context, llm_out: dict, *, persist: bool = True) -> dict:
        allowed = set(ctx.slots.injected_memory_ids)
        citations = _filter_citations(llm_out.get("citations") or [], allowed, self.observability)
        by_id = {item.id.value: item for item in ctx.hits}
        citation_items = [_citation_item(cid, by_id.get(cid)) for cid in citations]
        request_ctx = current_request_context()
        request_id = request_ctx.request_id if request_ctx is not None else self.ids.new_id()
        if not persist:
            return {
                "message_id": self.ids.new_id(),
                "request_id": request_id,
                "agent_run_id": None,
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
                "decision_trace": {},
                "tool_results": list(ctx.prompt_slots.get("tool_results") or []),
                "inbox_added": 0,
                "attachments": [{"filename": item["filename"]} for item in ctx.stored_attachments],
            }
        user_message_id = self.ids.new_id()
        assistant_message_id = self.ids.new_id()
        now = datetime.now(UTC).isoformat()
        ctx.thread.append_message(
            Message(
                id=user_message_id,
                role="user",
                content=ctx.text,
                attachments=ctx.stored_attachments,
                created_at=now,
            ),
            can_chat=True,
        )
        ctx.thread.append_message(
            Message(
                id=assistant_message_id,
                role="assistant",
                content=llm_out.get("text", ""),
                citations=[Citation(memory_id=MemoryId(c)) for c in citations],
                created_at=now,
            ),
            can_chat=True,
        )
        summary = compress_thread_summary(ctx.thread, self.reasoner)
        if summary:
            ctx.thread.summary = summary
        with self._obs().span("postgres.persist_message"):
            self.threads.save(ctx.thread)
        model = self._chat_model_label()
        generation_meta = {
            "model": model,
            "latency_ms": ctx.llm_duration_ms,
            "citation_ids": list(citations),
            "input_tokens": getattr(self.llm, "last_input_tokens", None),
            "output_tokens": getattr(self.llm, "last_output_tokens", None),
        }
        decision_summary = build_decision_trace_summary(
            retrieval_meta=dict(ctx.compiled.retrieval_meta),
            token_budget=ctx.compiled.token_budget,
            token_estimate=ctx.compiled.token_estimate,
            injected_memory_ids=list(ctx.slots.injected_memory_ids),
            truncation_notes=list(ctx.compiled.truncation_notes),
            reasoner_meta=ctx.reasoner_meta,
            generation_meta=generation_meta,
        )
        if self.decision_traces is not None:
            now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            inline_payload, payload_uri, content_sampled = store_encrypted_content_sample(
                storage=self.storage,
                tenant_id=ctx.tenant_id.value,
                request_id=request_id,
                user_message=ctx.text,
                model_response=llm_out.get("text", ""),
                prompt_slots=ctx.prompt_slots,
                reasoning_content=getattr(self.llm, "last_reasoning_content", None)
                or getattr(self.reasoner, "last_reasoning_content", None),
            )
            entry = {
                "id": self.ids.new_id(),
                "request_id": request_id,
                "tenant_id": ctx.tenant_id.value,
                "persona_id": ctx.persona_id.value,
                "thread_id": ctx.thread.id.value,
                "message_id": assistant_message_id,
                "trace_version": 1,
                "summary_json": decision_summary,
                "created_at": now,
                "expires_at": decision_trace_expires_at(decision_trace_retention_days()),
                "encrypted_payload": inline_payload,
                "encrypted_payload_uri": payload_uri,
                "content_sampled": content_sampled,
            }
            self.decision_traces.save(entry)
        agent_run_id = None
        if agent_compat_chat() and self.agent_compat is not None:
            agent_run_id = self.agent_compat.record_completed_turn(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                persona_id=ctx.persona_id,
                thread_id=ctx.thread.id,
                goal=ctx.text,
                text=llm_out.get("text", ""),
                citations=list(citations),
                retrieval_meta=dict(ctx.compiled.retrieval_meta),
            )
        return {
            "message_id": assistant_message_id,
            "request_id": request_id,
            "agent_run_id": agent_run_id,
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
            "decision_trace": decision_summary,
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
    reasoner_meta: dict
    llm_duration_ms: float


def _filter_citations(raw: list, allowed: set[str], observability: object | None) -> list:
    violations = [cid for cid in raw if cid not in allowed]
    if violations:
        record_citation_violation(observability, count=len(violations))
    return [cid for cid in raw if cid in allowed]


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
