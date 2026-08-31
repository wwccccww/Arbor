from __future__ import annotations

from typing import Protocol

from arbor.domain.multimodal.artifact import Artifact, ArtifactSegment
from arbor.domain.shared.ids import PersonaId, TenantId


class ArtifactRepository(Protocol):
    def get(self, tenant_id: TenantId, artifact_id: str) -> Artifact | None: ...
    def save(self, artifact: Artifact) -> None: ...
    def list_for_persona(
        self, tenant_id: TenantId, persona_id: PersonaId, *, limit: int = 50
    ) -> list[Artifact]: ...


class ArtifactSegmentRepository(Protocol):
    def add(self, segment: ArtifactSegment) -> None: ...
    def list_for_artifact(self, tenant_id: TenantId, artifact_id: str) -> list[ArtifactSegment]: ...


class ArtifactLineageRepository(Protocol):
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
    ) -> None: ...
    def list_for_run(self, tenant_id: TenantId, run_id: str) -> list[dict]: ...
