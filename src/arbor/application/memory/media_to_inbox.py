from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from arbor.domain.memory.memory import InboxItem
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


@dataclass
class MediaInboxResult:
    inbox_created: int
    parser: str
    media_kind: str
    chunks_parsed: int


class MediaToInbox:
    """Parse multimodal bytes into pending Inbox items (no Memory write)."""

    def __init__(
        self,
        *,
        personas,
        inbox,
        ids,
        auth: AuthorizationPolicy,
        reasoner=None,
        parse_media: Callable[[bytes, str], Any] | None = None,
    ) -> None:
        self.personas = personas
        self.inbox = inbox
        self.ids = ids
        self.auth = auth
        self.reasoner = reasoner
        self.parse_media = parse_media

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        filename: str,
        data: bytes,
        hint: str | None = None,
        capabilities: list[Capability] | None = None,
        use_reasoner_for_facts: bool = True,
    ) -> MediaInboxResult:
        from arbor.domain.errors import DomainError
        from arbor.domain.shared.media_kinds import MediaKind, media_kind_for_filename

        persona = self.personas.get(tenant_id, persona_id)
        caps = capabilities or (self.auth.capabilities_for(persona, user_id) if persona else [])
        if Capability.WRITE_MEMORY not in caps:
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "write_memory required")

        kind = media_kind_for_filename(filename)
        if kind is MediaKind.TEXT and use_reasoner_for_facts and data:
            try:
                plain = data.decode("utf-8-sig").strip()
            except UnicodeDecodeError:
                plain = ""
            if plain and self.reasoner is not None:
                extracted = self.reasoner.extract(plain)
                if extracted and not extracted.get("skip"):
                    kind_name = extracted.get("kind") or "fact"
                    payload = {
                        "text": extracted.get("text") or plain,
                        "source": filename,
                        "source_text": extracted.get("source_text") or plain,
                        "memory_type": "fact",
                    }
                    if hint:
                        payload["hint"] = hint
                    self.inbox.add(
                        InboxItem(
                            id=self.ids.new_id(),
                            tenant_id=tenant_id,
                            persona_id=persona_id,
                            kind=kind_name if kind_name in {"fact", "event", "conflict"} else "fact",
                            payload=payload,
                        )
                    )
                    return MediaInboxResult(
                        inbox_created=1,
                        parser="reasoner",
                        media_kind="text",
                        chunks_parsed=1,
                    )

        if self.parse_media is None:
            raise DomainError("VALIDATION_ERROR", "multimodal parser not configured")

        parsed = self.parse_media(data, filename)
        created = self._add_chunks(
            tenant_id=tenant_id,
            persona_id=persona_id,
            filename=filename,
            hint=hint,
            parsed=parsed,
            use_reasoner_for_facts=use_reasoner_for_facts,
        )
        return MediaInboxResult(
            inbox_created=created,
            parser=parsed.parser,
            media_kind=parsed.media_kind,
            chunks_parsed=len(parsed.chunks),
        )

    def _add_chunks(
        self,
        *,
        tenant_id: TenantId,
        persona_id: PersonaId,
        filename: str,
        hint: str | None,
        parsed: Any,
        use_reasoner_for_facts: bool,
    ) -> int:
        created = 0
        for chunk in parsed.chunks:
            if not (chunk.text or "").strip():
                continue
            memory_type = chunk.memory_type
            text = chunk.text.strip()
            kind = "fact"
            if memory_type in {"file_chunk", "transcript", "image_caption"}:
                payload = {
                    "text": text,
                    "source": filename,
                    "memory_type": memory_type,
                    "chunk_meta": dict(chunk.metadata),
                }
                if hint:
                    payload["hint"] = hint
                self.inbox.add(
                    InboxItem(
                        id=self.ids.new_id(),
                        tenant_id=tenant_id,
                        persona_id=persona_id,
                        kind="fact",
                        payload=payload,
                    )
                )
                created += 1
                continue

            extracted = None
            if use_reasoner_for_facts and self.reasoner is not None:
                extracted = self.reasoner.extract(text)
            if extracted and not extracted.get("skip"):
                kind = extracted.get("kind") or "fact"
                payload = {
                    "text": extracted.get("text") or text,
                    "source": filename,
                    "source_text": extracted.get("source_text") or text,
                    "memory_type": "fact",
                }
            else:
                payload = {"text": text, "source": filename, "memory_type": "fact"}
            if hint:
                payload["hint"] = hint
            self.inbox.add(
                InboxItem(
                    id=self.ids.new_id(),
                    tenant_id=tenant_id,
                    persona_id=persona_id,
                    kind=kind if kind in {"fact", "event", "conflict"} else "fact",
                    payload=payload,
                )
            )
            created += 1
        return created
