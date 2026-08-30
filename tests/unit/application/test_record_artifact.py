from __future__ import annotations

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.inmemory import (
    InMemoryPersonaRepository,
    InMemoryStores,
    SeqIdGenerator,
)
from arbor.adapters.outbound.inmemory_artifacts import (
    InMemoryArtifactLineageRepository,
    InMemoryArtifactRepository,
    InMemoryArtifactSegmentRepository,
    InMemoryArtifactStores,
)
from arbor.application.multimodal.record_artifact import RecordArtifactEvidence
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def test_record_artifact_with_lineage():
    stores = InMemoryStores()
    load_world(ROOT / "eval" / "fixtures" / "suite-v1" / "world.json", stores)
    persona_id = PersonaId("0a000000-0000-4000-a000-000000000010")
    tenant_id = TenantId("0a000000-0000-4000-a000-000000000001")
    user_id = UserId("0a000000-0000-4000-a000-000000000002")
    personas = InMemoryPersonaRepository(stores)
    persona = personas.get(tenant_id, persona_id)
    assert persona is not None
    persona.grants.append(Grant(user_id=user_id.value, capabilities=[Capability.WRITE_MEMORY]))

    artifact_stores = InMemoryArtifactStores()
    artifacts = InMemoryArtifactRepository(artifact_stores)
    segments = InMemoryArtifactSegmentRepository(artifact_stores)
    lineage = InMemoryArtifactLineageRepository(artifact_stores)
    ids = SeqIdGenerator()

    record = RecordArtifactEvidence(
        personas=personas,
        artifacts=artifacts,
        segments=segments,
        lineage=lineage,
        ids=ids,
        auth=AuthorizationPolicy(),
    )
    result = record(
        tenant_id=tenant_id,
        user_id=user_id,
        persona_id=persona_id,
        object_uri="s3://bucket/manual.pdf",
        mime_type="application/pdf",
        segment_payloads=[
            {
                "modality": "text",
                "text": "空调维修 SOP 第 3 页",
                "page_number": 3,
            }
        ],
        parser="pdf",
        parser_version="1.0",
        run_id="run-1",
        step_id="step-1",
    )
    assert result["artifact_id"]
    saved = artifacts.get(tenant_id, result["artifact_id"])
    assert saved is not None
    assert saved.object_uri.endswith("manual.pdf")
    segs = segments.list_for_artifact(tenant_id, result["artifact_id"])
    assert len(segs) == 1
    assert segs[0].page_number == 3
    rows = lineage.list_for_run(tenant_id, "run-1")
    assert len(rows) == 1
    assert rows[0]["artifact_id"] == result["artifact_id"]
