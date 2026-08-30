from __future__ import annotations

from datetime import UTC, datetime

from arbor.domain.errors import DomainError
from arbor.domain.multimodal.artifact import Artifact, ArtifactSegment
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class RecordArtifactEvidence:
    """Persist artifact, segments, and optional lineage to agent run."""

    def __init__(
        self,
        *,
        personas,
        artifacts,
        segments,
        lineage,
        ids,
        auth: AuthorizationPolicy,
    ) -> None:
        self.personas = personas
        self.artifacts = artifacts
        self.segments = segments
        self.lineage = lineage
        self.ids = ids
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        object_uri: str,
        mime_type: str,
        segment_payloads: list[dict],
        parser: str = "",
        parser_version: str = "",
        checksum: str = "",
        run_id: str | None = None,
        step_id: str | None = None,
        supersedes: str | None = None,
    ) -> dict:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.WRITE_MEMORY not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN", "write_memory required")

        if supersedes:
            prior = self.artifacts.get(tenant_id, supersedes)
            if prior is not None:
                prior.status = "superseded"
                self.artifacts.save(prior)

        artifact_id = self.ids.new_id()
        now = _now_iso()
        artifact = Artifact(
            id=artifact_id,
            tenant_id=tenant_id,
            persona_id=persona_id,
            object_uri=object_uri,
            mime_type=mime_type,
            checksum=checksum,
            parser=parser,
            parser_version=parser_version,
            status="active",
            supersedes=supersedes,
            created_by=user_id.value,
            created_at=now,
        )
        self.artifacts.save(artifact)

        segment_ids: list[str] = []
        for payload in segment_payloads:
            segment_id = self.ids.new_id()
            segment = ArtifactSegment(
                id=segment_id,
                artifact_id=artifact_id,
                tenant_id=tenant_id,
                persona_id=persona_id,
                modality=str(payload.get("modality") or "text"),
                text=str(payload.get("text") or ""),
                page_number=payload.get("page_number"),
                time_start_ms=payload.get("time_start_ms"),
                time_end_ms=payload.get("time_end_ms"),
                bounding_box=payload.get("bounding_box"),
                confidence=payload.get("confidence"),
                derived_by=str(payload.get("derived_by") or parser),
                memory_id=payload.get("memory_id"),
            )
            self.segments.add(segment)
            segment_ids.append(segment_id)
            if run_id:
                self.lineage.add(
                    tenant_id=tenant_id,
                    lineage_id=self.ids.new_id(),
                    artifact_id=artifact_id,
                    segment_id=segment_id,
                    run_id=run_id,
                    step_id=step_id,
                    memory_id=payload.get("memory_id"),
                    citation_kind=str(payload.get("citation_kind") or "evidence"),
                )

        return {
            "artifact_id": artifact_id,
            "segment_ids": segment_ids,
            "object_uri": object_uri,
        }
