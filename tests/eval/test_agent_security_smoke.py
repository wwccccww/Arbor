from __future__ import annotations

import json

from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack
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
from arbor.application.evaluation.agent_security_runner import (
    run_agent_security_smoke,
    security_baseline_path,
    security_fixture_path,
)
from arbor.application.multimodal.invalidate_artifacts import InvalidateArtifactsForObjectUri
from arbor.application.multimodal.record_artifact import RecordArtifactEvidence
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId
from tests.unit.application.test_send_message import USER, load_mini

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


def test_agent_security_smoke_matches_baseline():
    stack = build_agent_eval_stack(use_employee_templates=False)
    live = run_agent_security_smoke(stack=stack, fixture_path=security_fixture_path())
    baseline_path = security_baseline_path()
    assert baseline_path.is_file()
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert live.get("task_success_rate") == baseline.get("task_success_rate")
    assert live.get("unauthorized_action_rate", 0.0) == 0.0
    assert live.get("approval_bypass_rate", 0.0) == 0.0
    assert live.get("duplicate_side_effect_rate", 0.0) == 0.0
    assert live.get("tenant_leak_rate", 0.0) == 0.0
    for case in live.get("cases") or []:
        assert case.get("ok") is True, case


def test_artifact_invalidation_clears_evidence():
    stores = InMemoryStores()
    load_mini(stores)
    personas = InMemoryPersonaRepository(stores)
    persona = personas.get(TENANT, LINXIA)
    assert persona is not None
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
    uri = "s3://bucket/security-evidence.pdf"
    created = record(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        object_uri=uri,
        mime_type="application/pdf",
        segment_payloads=[{"modality": "text", "text": "页码 3 证据", "page_number": 3}],
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


def test_multimodal_segment_has_page_locator():
    stores = InMemoryStores()
    load_mini(stores)
    personas = InMemoryPersonaRepository(stores)
    persona = personas.get(TENANT, LINXIA)
    assert persona is not None
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
    created = record(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        object_uri="s3://bucket/locator.pdf",
        mime_type="application/pdf",
        segment_payloads=[
            {"modality": "text", "text": "定位段落", "page_number": 7, "time_start_ms": 1200}
        ],
    )
    seg_list = segments.list_for_artifact(TENANT, created["artifact_id"])
    assert seg_list
    seg = seg_list[0]
    assert seg.page_number == 7
    assert seg.time_start_ms == 1200
