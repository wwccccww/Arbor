from __future__ import annotations

from dataclasses import dataclass, field

from arbor.domain.multimodal.artifact import Artifact, ArtifactSegment
from arbor.domain.shared.ids import PersonaId, TenantId


@dataclass
class InMemoryArtifactStores:
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    segments: dict[str, ArtifactSegment] = field(default_factory=dict)
    lineage: list[dict] = field(default_factory=list)


class InMemoryArtifactRepository:
    def __init__(self, stores: InMemoryArtifactStores) -> None:
        self.stores = stores

    def get(self, tenant_id: TenantId, artifact_id: str) -> Artifact | None:
        item = self.stores.artifacts.get(artifact_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    def save(self, artifact: Artifact) -> None:
        self.stores.artifacts[artifact.id] = artifact

    def list_for_persona(
        self, tenant_id: TenantId, persona_id: PersonaId, *, limit: int = 50
    ) -> list[Artifact]:
        items = [
            a
            for a in self.stores.artifacts.values()
            if a.tenant_id == tenant_id and a.persona_id == persona_id and a.status == "active"
        ]
        items.sort(key=lambda a: a.created_at, reverse=True)
        return items[:limit]


class InMemoryArtifactSegmentRepository:
    def __init__(self, stores: InMemoryArtifactStores) -> None:
        self.stores = stores

    def add(self, segment: ArtifactSegment) -> None:
        self.stores.segments[segment.id] = segment

    def list_for_artifact(self, tenant_id: TenantId, artifact_id: str) -> list[ArtifactSegment]:
        items = [
            s
            for s in self.stores.segments.values()
            if s.artifact_id == artifact_id and s.tenant_id == tenant_id
        ]
        return sorted(items, key=lambda s: (s.page_number or 0, s.time_start_ms or 0))


class InMemoryArtifactLineageRepository:
    def __init__(self, stores: InMemoryArtifactStores) -> None:
        self.stores = stores

    def add(
        self,
        *,
        tenant_id: TenantId,
        lineage_id: str,
        artifact_id: str,
        segment_id: str | None,
        run_id: str | None,
        step_id: str | None,
        memory_id: str | None,
        citation_kind: str = "evidence",
    ) -> None:
        self.stores.lineage.append(
            {
                "id": lineage_id,
                "tenant_id": tenant_id.value,
                "artifact_id": artifact_id,
                "segment_id": segment_id,
                "run_id": run_id,
                "step_id": step_id,
                "memory_id": memory_id,
                "citation_kind": citation_kind,
            }
        )

    def list_for_run(self, tenant_id: TenantId, run_id: str) -> list[dict]:
        return [
            row
            for row in self.stores.lineage
            if row.get("tenant_id") == tenant_id.value and row.get("run_id") == run_id
        ]
