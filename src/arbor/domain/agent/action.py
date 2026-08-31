from __future__ import annotations

from typing import Any

from arbor.domain.errors import DomainError

ALLOWED_ACTIONS = frozenset(
    {"retrieve", "tool", "answer", "request_clarification", "handoff"}
)


def validate_planner_action(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise DomainError("VALIDATION_ERROR", "planner action must be a dict")
    action = str(raw.get("action") or "").strip().lower()
    if action not in ALLOWED_ACTIONS:
        raise DomainError("VALIDATION_ERROR", f"unknown planner action: {action}")
    schema_version = int(raw.get("schema_version") or 1)
    out: dict[str, Any] = {
        "schema_version": schema_version,
        "action": action,
        "reason": str(raw.get("reason") or ""),
        "completion": bool(raw.get("completion")),
    }
    if action == "retrieve":
        out["query"] = str(raw.get("query") or "").strip()
        scopes = raw.get("scopes") or []
        out["scopes"] = [str(s) for s in scopes if str(s).strip()]
    elif action == "tool":
        out["tool_name"] = str(raw.get("tool_name") or "").strip()
        out["arguments"] = dict(raw.get("arguments") or {})
        evidence = raw.get("evidence_ids") or []
        out["evidence_ids"] = [str(e) for e in evidence if str(e).strip()]
    elif action == "answer":
        out["text"] = str(raw.get("text") or "")
        citations = raw.get("citations") or []
        out["citations"] = [str(c) for c in citations if str(c).strip()]
    elif action == "request_clarification" or action == "handoff":
        out["text"] = str(raw.get("text") or "")
    return out
