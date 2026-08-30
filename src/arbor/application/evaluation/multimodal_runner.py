from __future__ import annotations

import json
from pathlib import Path

from arbor.application.multimodal.record_artifact import RecordArtifactEvidence


def run_multimodal_smoke(
    *,
    fixture_path: Path,
    record_artifact: RecordArtifactEvidence,
    personas,
    segments,
    lineage,
) -> dict:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    results: list[dict] = []

    for case in payload.get("cases") or []:
        from arbor.domain.shared.ids import PersonaId, TenantId, UserId

        tenant_id = TenantId(str(case["tenant_id"]))
        persona_id = PersonaId(str(case["persona_id"]))
        user_id = UserId(str(case["user_id"]))
        persona = personas.get(tenant_id, persona_id)
        if persona is not None and case.get("grant_write_memory"):
            from arbor.domain.persona.authorization import Capability, Grant

            if not any(
                Capability.WRITE_MEMORY in g.capabilities for g in persona.grants if g.user_id == user_id
            ):
                persona.grants.append(
                    Grant(user_id=user_id, capabilities=[Capability.WRITE_MEMORY, Capability.ADMIN])
                )

        segment = dict(case.get("segment") or {})
        run_id = str(case.get("run_id") or "run-mm-smoke")
        step_id = str(case.get("step_id") or "step-mm-smoke")
        recorded = record_artifact(
            tenant_id=tenant_id,
            user_id=user_id,
            persona_id=persona_id,
            object_uri=str(case.get("object_uri") or ""),
            mime_type=str(case.get("mime_type") or "application/octet-stream"),
            segment_payloads=[segment],
            parser=str(case.get("parser") or "stub"),
            parser_version=str(case.get("parser_version") or "1.0"),
            run_id=run_id if case.get("layer") == "agent" else None,
            step_id=step_id if case.get("layer") == "agent" else None,
        )
        artifact_id = str(recorded.get("artifact_id") or "")
        segs = segments.list_for_artifact(tenant_id, artifact_id)
        ok = bool(artifact_id and segs)
        layer = str(case.get("layer") or "perception")

        if layer == "perception":
            seg = segs[0]
            if case.get("expect_page_number") is not None:
                ok = seg.page_number == int(case["expect_page_number"])
            if case.get("expect_start_ms") is not None:
                ok = seg.time_start_ms == int(case["expect_start_ms"])
            if case.get("expect_end_ms") is not None:
                ok = ok and seg.time_end_ms == int(case["expect_end_ms"])
        elif layer == "agent":
            rows = lineage.list_for_run(tenant_id, str(case.get("expect_run_id") or run_id))
            ok = any(row.get("artifact_id") == artifact_id for row in rows)
            if case.get("expect_page_number") is not None and segs:
                ok = ok and segs[0].page_number == int(case["expect_page_number"])

        results.append({"id": case["id"], "layer": layer, "ok": ok})

    passed = sum(1 for item in results if item.get("ok"))
    total = len(results)
    return {
        "suite_version": payload.get("suite_version"),
        "layer_pass_rate": passed / total if total else 0.0,
        "cases": results,
    }
