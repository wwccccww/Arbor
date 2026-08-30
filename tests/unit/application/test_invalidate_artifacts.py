from __future__ import annotations

from arbor.adapters.outbound.inmemory import InMemoryPersonaRepository, InMemoryStores
from arbor.adapters.outbound.inmemory_artifacts import (
    InMemoryArtifactRepository,
    InMemoryArtifactStores,
)
from arbor.application.multimodal.invalidate_artifacts import InvalidateArtifactsForObjectUri
from arbor.application.multimodal.record_artifact import RecordArtifactEvidence
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId
from tests.unit.application.test_send_message import load_mini, USER

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


def test_invalidate_artifacts_for_deleted_object_uri():
    stores = InMemoryStores()
    load_mini(stores)
    personas = InMemoryPersonaRepository(stores)
    persona = personas.get(TENANT, LINXIA)
    assert persona is not None
    persona.grants.append(Grant(user_id=USER, capabilities=list(Capability)))

    artifact_stores = InMemoryArtifactStores()
    artifacts = InMemoryArtifactRepository(artifact_stores)
    from arbor.adapters.outbound.inmemory import SeqIdGenerator
    from arbor.adapters.outbound.inmemory_artifacts import (
        InMemoryArtifactLineageRepository,
        InMemoryArtifactSegmentRepository,
    )

    segments = InMemoryArtifactSegmentRepository(artifact_stores)
    lineage = InMemoryArtifactLineageRepository(artifact_stores)
    record = RecordArtifactEvidence(
        personas=personas,
        artifacts=artifacts,
        segments=segments,
        lineage=lineage,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    uri = "s3://bucket/evidence.pdf"
    created = record(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        object_uri=uri,
        mime_type="application/pdf",
        segment_payloads=[{"modality": "text", "text": "证据", "page_number": 2}],
    )
    invalidate = InvalidateArtifactsForObjectUri(
        personas=personas,
        artifacts=artifacts,
        auth=AuthorizationPolicy(),
    )
    result = invalidate(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        object_uri=uri,
        capabilities=list(Capability),
    )
    assert created["artifact_id"] in result["invalidated_artifact_ids"]
    saved = artifacts.get(TENANT, created["artifact_id"])
    assert saved is not None
    assert saved.status == "deleted"
