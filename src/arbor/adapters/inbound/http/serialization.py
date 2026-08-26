from __future__ import annotations

from arbor.domain.persona.authorization import Capability
from arbor.env import strict_tenant_membership


def caps_for(persona, user: dict) -> list[Capability]:
    if not strict_tenant_membership() and user["role"] in {"owner", "admin"}:
        return list(Capability)
    for grant in persona.grants:
        if grant.user_id.value == user["user_id"]:
            return list(grant.capabilities)
    return []


def grant_json(grant) -> dict:
    return {
        "user_id": grant.user_id.value,
        "capabilities": [cap.value for cap in grant.capabilities],
    }


def persona_json(persona, caps: list[Capability]) -> dict:
    body = {
        "id": persona.id.value,
        "skin": persona.skin,
        "display_name": persona.profile.display_name,
        "one_liner": persona.profile.one_liner,
        "avatar": persona.profile.avatar or "",
    }
    if Capability.READ_MEMORY in caps:
        body["taboos"] = list(persona.profile.taboos)
        body["relationships"] = list(persona.profile.relationships)
        body["personality"] = persona.profile.personality
    if Capability.ADMIN in caps:
        body["grants"] = [grant_json(grant) for grant in persona.grants]
        body["tool_policy"] = {
            "allowed_tools": list(persona.tool_policy.allowed_tools),
            "notes": persona.tool_policy.notes,
        }
    return body


def tenant_json(tenant, user_id) -> dict:
    membership = tenant.member(user_id)
    return {
        "id": tenant.id.value,
        "name": tenant.name,
        "role": membership.role.value if membership else None,
    }


def public_attachments(items) -> list[dict]:
    return [
        {"filename": item["filename"]}
        for item in items or []
        if isinstance(item, dict) and item.get("filename")
    ]


def citation_json(memories, tenant, citation) -> dict:
    """Project a stored citation into the same shape post_message returns."""
    body: dict = {}
    if citation.memory_id:
        body["memory_id"] = citation.memory_id.value
        item = memories.get(tenant, citation.memory_id)
        if item is not None:
            body["preview"] = (item.text or "")[:40]
            if item.event_id:
                body["event_id"] = item.event_id.value
    if citation.event_id:
        body["event_id"] = citation.event_id.value
    return body
