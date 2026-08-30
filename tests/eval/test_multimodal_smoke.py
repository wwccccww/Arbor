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
from arbor.application.evaluation.multimodal_runner import run_multimodal_smoke
from arbor.application.multimodal.record_artifact import RecordArtifactEvidence
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def test_multimodal_v1_layered_smoke():
    stores = InMemoryStores()
    load_world(ROOT / "eval" / "fixtures" / "suite-v1" / "world.json", stores)
    personas = InMemoryPersonaRepository(stores)
    persona = personas.get(TENANT, LINXIA)
    if persona is not None:
        persona.grants.append(Grant(user_id=USER, capabilities=list(Capability)))

    artifact_stores = InMemoryArtifactStores()
    artifacts = InMemoryArtifactRepository(artifact_stores)
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
    report = run_multimodal_smoke(
        fixture_path=ROOT / "eval" / "fixtures" / "multimodal-v1" / "cases.json",
        record_artifact=record,
        personas=personas,
        artifacts=artifacts,
        segments=segments,
        lineage=lineage,
    )
    assert report["layer_pass_rate"] == 1.0
    assert len(report["cases"]) == 4
