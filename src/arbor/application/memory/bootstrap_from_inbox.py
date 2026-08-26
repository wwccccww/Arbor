from __future__ import annotations

import re

from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId

_EVENT_MARKERS = ("吵架", "见面", "分手", "结婚", "生日", "旅行", "事故", "离职", "入职")


def _profile_hints_from_text(text: str) -> dict:
    stripped = (text or "").strip()
    hints: dict = {}
    if stripped and len(stripped) <= 120:
        hints["one_liner_candidate"] = stripped
    taboos: list[str] = []
    for marker in ("讨厌", "不喜欢", "忌"):
        if marker in stripped:
            part = stripped.split(marker, 1)[-1].strip()
            taboo = part.split("，")[0].split("。")[0].split("；")[0].strip()[:40]
            if taboo:
                taboos.append(taboo)
    if taboos:
        hints["taboos"] = taboos
    if "住在" in stripped or "居住在" in stripped:
        city = re.sub(r".*住在\s*", "", stripped)
        city = re.sub(r".*居住在\s*", "", city).split("，")[0].split("。")[0].strip()
        if city and len(city) <= 20:
            hints["location_line"] = f"住在{city}"
    return hints


def _looks_like_event(kind: str, payload: dict) -> bool:
    if kind in {"event", "conflict"}:
        return True
    memory_type = str(payload.get("memory_type") or "")
    if memory_type in {"episode_summary"}:
        return True
    text = str(payload.get("text") or "")
    if re.search(r"\d{4}年|\d{1,2}月", text):
        return True
    return any(marker in text for marker in _EVENT_MARKERS)


class BootstrapFromInbox:
    """Turn pending Inbox items into profile hints, memories, and first event nodes."""

    def __init__(self, *, personas, inbox, confirm, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.inbox = inbox
        self.confirm = confirm
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        capabilities: list[Capability] | None = None,
        max_events: int = 5,
        max_facts: int = 12,
    ) -> dict:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.WRITE_MEMORY not in caps:
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "write_memory required")

        pending = self.inbox.list_pending(tenant_id, persona_id)
        if not pending:
            return {
                "profile_updated": False,
                "events_created": 0,
                "memories_created": 0,
                "inbox_processed": 0,
            }

        profile_updated = False
        one_liner_candidate = None
        taboo_candidates: list[str] = []
        for item in pending:
            hints = _profile_hints_from_text(str(item.payload.get("text") or ""))
            if not persona.profile.one_liner and hints.get("one_liner_candidate"):
                one_liner_candidate = one_liner_candidate or hints["one_liner_candidate"]
            if hints.get("location_line") and not persona.profile.one_liner:
                one_liner_candidate = hints["location_line"]
            for taboo in hints.get("taboos") or []:
                if taboo not in taboo_candidates:
                    taboo_candidates.append(taboo)

        if one_liner_candidate and not persona.profile.one_liner:
            persona.profile.one_liner = one_liner_candidate
            profile_updated = True
        if taboo_candidates:
            merged = list(persona.profile.taboos)
            for taboo in taboo_candidates:
                if taboo not in merged:
                    merged.append(taboo)
            if merged != list(persona.profile.taboos):
                persona.profile.taboos = merged
                profile_updated = True
        if profile_updated:
            self.personas.save(persona)

        event_items = [item for item in pending if _looks_like_event(item.kind, item.payload)]
        fact_items = [item for item in pending if item not in event_items]

        events_created = 0
        memories_created = 0
        inbox_processed = 0

        for item in event_items[:max_events]:
            self.confirm(
                tenant_id=tenant_id,
                user_id=user_id,
                persona_id=persona_id,
                inbox_id=item.id,
                capabilities=caps,
                mark_key_event=True,
            )
            events_created += 1
            memories_created += 1
            inbox_processed += 1

        for item in fact_items[:max_facts]:
            self.confirm(
                tenant_id=tenant_id,
                user_id=user_id,
                persona_id=persona_id,
                inbox_id=item.id,
                capabilities=caps,
                mark_key_event=False,
            )
            memories_created += 1
            inbox_processed += 1

        return {
            "profile_updated": profile_updated,
            "events_created": events_created,
            "memories_created": memories_created,
            "inbox_processed": inbox_processed,
        }
