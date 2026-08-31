from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from arbor.domain.shared.ids import PersonaId, TenantId


class MemoryClass(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


@dataclass
class Artifact:
    id: str
    tenant_id: TenantId
    persona_id: PersonaId
    object_uri: str
    mime_type: str
    checksum: str = ""
    parser: str = ""
    parser_version: str = ""
    status: str = "active"
    supersedes: str | None = None
    created_by: str = ""
    created_at: str = ""


@dataclass
class ArtifactSegment:
    id: str
    artifact_id: str
    tenant_id: TenantId
    persona_id: PersonaId
    modality: str
    text: str
    page_number: int | None = None
    time_start_ms: int | None = None
    time_end_ms: int | None = None
    bounding_box: dict | None = None
    confidence: float | None = None
    derived_by: str = ""
    memory_id: str | None = None
