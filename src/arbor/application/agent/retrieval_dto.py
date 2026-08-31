from __future__ import annotations

from dataclasses import dataclass, field

from arbor.domain.shared.ids import PersonaId, TenantId


@dataclass
class RetrievalRequest:
    tenant_id: TenantId
    persona_id: PersonaId
    query: str
    purpose: str = "agent_step"
    scopes: list[str] = field(default_factory=list)
    filters: dict | None = None
    k: int = 5
    run_id: str | None = None
    step_id: str | None = None


@dataclass
class RetrievalCandidate:
    memory_id: str
    text: str
    source: str = ""
    score: float | None = None
    memory_class: str | None = None


@dataclass
class RetrievalResult:
    candidates: list[RetrievalCandidate]
    strategy: str
    hit_ids: list[str]
    source_counts: dict = field(default_factory=dict)
    sub_queries: list[str] = field(default_factory=list)
    query_plan: str | None = None
