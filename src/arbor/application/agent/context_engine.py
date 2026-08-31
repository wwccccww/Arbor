from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ContextItemKind(str, Enum):
    IDENTITY = "identity"
    POLICY = "policy"
    TASK = "task"
    PLAN = "plan"
    MEMORY = "memory"
    EVIDENCE = "evidence"
    TOOL_RESULT = "tool_result"


@dataclass
class ContextItem:
    id: str
    kind: ContextItemKind
    content: str
    source_uri: str = ""
    source_type: str = ""
    trust_level: str = "system"
    relevance: float = 0.0
    confidence: float | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    token_count: int = 0
    required: bool = False
    permissions: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ContextManifest:
    selected: list[str] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)
    token_budget: int = 0
    token_usage: int = 0
    conflicts: list[str] = field(default_factory=list)
    untrusted_instruction_count: int = 0

    def to_dict(self) -> dict:
        return {
            "selected_item_ids": list(self.selected),
            "excluded_items": list(self.excluded),
            "token_budget": self.token_budget,
            "token_usage": self.token_usage,
            "conflicts": list(self.conflicts),
            "untrusted_instruction_count": self.untrusted_instruction_count,
        }


_INJECTION_PATTERNS = (
    "忽略之前",
    "忽略所有",
    "ignore previous",
    "ignore all",
    "system:",
    "调用工具",
    "tool_calls",
)


def detect_untrusted_instructions(text: str) -> int:
    haystack = (text or "").lower()
    count = 0
    for pattern in _INJECTION_PATTERNS:
        if pattern.lower() in haystack:
            count += 1
    return count


def compile_context_items(
    items: list[ContextItem],
    *,
    token_budget: int,
    observability: object | None = None,
) -> tuple[list[ContextItem], ContextManifest]:
    manifest = ContextManifest(token_budget=token_budget)
    required = [item for item in items if item.required]
    optional = [item for item in items if not item.required]
    optional.sort(key=lambda item: item.relevance, reverse=True)

    selected: list[ContextItem] = []
    usage = 0

    for item in required + optional:
        if item.trust_level == "untrusted":
            manifest.untrusted_instruction_count += detect_untrusted_instructions(item.content)
        need = item.token_count or max(1, len(item.content) // 4)
        if item.required:
            selected.append(item)
            usage += need
            manifest.selected.append(item.id)
            continue
        if usage + need > token_budget:
            manifest.excluded.append({"id": item.id, "reason": "token_budget"})
            continue
        selected.append(item)
        usage += need
        manifest.selected.append(item.id)

    manifest.token_usage = usage
    return selected, manifest


def context_item_from_memory(
    memory_id: str,
    text: str,
    *,
    source: str = "",
    score: float | None = None,
    trust_level: str = "evidence",
) -> ContextItem:
    content = (text or "").strip()
    return ContextItem(
        id=memory_id,
        kind=ContextItemKind.EVIDENCE,
        content=content,
        source_type=source or "memory",
        trust_level=trust_level,
        relevance=float(score or 0.0),
        token_count=max(1, len(content) // 4),
        metadata={"memory_id": memory_id},
    )
