from __future__ import annotations

import json
import os
from pathlib import Path

from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack
from arbor.adapters.inbound.eval_runner import load_world
from arbor.adapters.outbound.inmemory import (
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
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
from arbor.application.agent.extract_memory import ExtractRunMemory
from arbor.application.evaluation.agent_runner import run_agent_smoke
from arbor.application.evaluation.multimodal_runner import run_multimodal_smoke
from arbor.application.multimodal.record_artifact import RecordArtifactEvidence
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, UserId
from arbor.paths import repo_root

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
USER = UserId("0a000000-0000-4000-a000-000000000002")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


def demo_manifest_path() -> Path:
    return repo_root() / "eval" / "fixtures" / "demo-v1" / "manifest.json"


def demo_baseline_path() -> Path:
    return repo_root() / "eval" / "baselines" / "demo-v1-smoke.json"


def _agent_case_ok(*, case_ids: set[str]) -> tuple[bool, str]:
    stack = build_agent_eval_stack(use_employee_templates=False)
    fixture = repo_root() / "eval" / "fixtures" / "agent-v1" / "cases.json"
    report = run_agent_smoke(
        fixture_path=fixture,
        start_run=stack["start_run"],
        approve_step=stack["approve_step"],
        reject_step=stack["reject_step"],
        resume_run=stack.get("resume_run"),
        personas=stack["personas"],
        runs=stack["runs"],
        case_ids=case_ids,
    )
    by_id = {str(item.get("id")): item for item in report.get("cases") or []}
    missing = sorted(case_ids - set(by_id))
    if missing:
        return False, f"missing cases: {missing}"
    failed = [cid for cid in case_ids if not by_id[cid].get("ok")]
    if failed:
        return False, f"failed: {failed}"
    return True, f"cases={sorted(case_ids)}"


def _multimodal_case_ok(*, case_ids: set[str]) -> tuple[bool, str]:
    root = repo_root()
    stores = InMemoryStores()
    load_world(root / "eval" / "fixtures" / "suite-v1" / "world.json", stores)
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
    fixture = root / "eval" / "fixtures" / "multimodal-v1" / "cases.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    filtered = [c for c in payload.get("cases") or [] if c.get("id") in case_ids]
    if len(filtered) != len(case_ids):
        return False, "multimodal case filter mismatch"
    temp_path = root / "eval" / "fixtures" / "multimodal-v1" / ".demo-filter.json"
    temp_path.write_text(
        json.dumps({**payload, "cases": filtered}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        report = run_multimodal_smoke(
            fixture_path=temp_path,
            record_artifact=record,
            personas=personas,
            artifacts=artifacts,
            segments=segments,
            lineage=lineage,
        )
    finally:
        temp_path.unlink(missing_ok=True)
    failed = [item["id"] for item in report.get("cases") or [] if not item.get("ok")]
    if failed:
        return False, f"failed: {failed}"
    return True, f"layer_pass_rate={report.get('layer_pass_rate')}"


def _agent_e2e_chain_ok(*, case_id: str = "ticket-with-approval") -> tuple[bool, str]:
    """Single-stack end-to-end agent flow (retrieve → tool → approval → answer)."""
    root = repo_root()
    fixture = root / "eval" / "fixtures" / "agent-v1" / "cases.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    case = next((c for c in payload.get("cases") or [] if c.get("id") == case_id), None)
    if case is None:
        return False, f"case {case_id} not found"
    stack = build_agent_eval_stack(use_employee_templates=False)
    persona = stack["personas"].get(TENANT, LINXIA)
    if persona is not None:
        from arbor.domain.persona.authorization import Capability, Grant

        if not any(Capability.ADMIN in g.capabilities for g in persona.grants if g.user_id == USER):
            persona.grants.append(Grant(user_id=USER, capabilities=[Capability.ADMIN, Capability.CHAT]))
        allowed = list(persona.tool_policy.allowed_tools or [])
        for tool in ("ticket", "calendar"):
            if tool not in allowed:
                allowed.append(tool)
        persona.tool_policy.allowed_tools = allowed
    calls_before = stack["eval_ticket_tool"].create_calls
    run = stack["start_run"](
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        goal=str(case.get("goal") or ""),
        plan_script=list(case.get("plan_script") or []),
        enqueue=True,
    )
    final = stack["runs"].get(TENANT, run.id)
    if final is None:
        return False, "run missing"
    if final.status.value == "waiting_approval":
        approval_id = final.metadata.get("pending_approval_id")
        stack["approve_step"](
            tenant_id=TENANT,
            user_id=USER,
            approval_id=str(approval_id),
        )
        final = stack["runs"].get(TENANT, run.id)
    ok = (
        final is not None
        and final.status.value == "completed"
        and stack["eval_ticket_tool"].create_calls == calls_before + 1
        and bool(final.final_output)
    )
    return ok, f"status={final.status.value if final else None} tickets={stack['eval_ticket_tool'].create_calls}"


def _inbox_extract_ok() -> tuple[bool, str]:
    stack = build_agent_eval_stack(use_employee_templates=False)
    personas = stack["personas"]
    persona = personas.get(TENANT, LINXIA)
    if persona is not None and not any(
        Capability.WRITE_MEMORY in g.capabilities for g in persona.grants if g.user_id == USER
    ):
        persona.grants.append(Grant(user_id=USER, capabilities=[Capability.WRITE_MEMORY, Capability.CHAT]))
    memories = InMemoryMemoryRepository(InMemoryStores())
    inbox = InMemoryInboxRepository(InMemoryStores())
    extract = ExtractRunMemory(
        personas=personas,
        inbox=inbox,
        memories=memories,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    added = extract(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        run_id="demo-run-inbox",
        goal="登记工单",
        final_output={"text": "工单已登记"},
        tool_results=[{"ticket_id": "demo-ticket"}],
    )
    pending = inbox.list_pending(TENANT, LINXIA)
    ok = added == 1 and len(pending) == 1 and pending[0].payload.get("memory_class") == "episodic"
    return ok, f"inbox_pending={len(pending)}"


def _trace_test_ok(path: str) -> tuple[bool, str]:
    rel = path.split("::")[0]
    test_file = repo_root() / rel
    if not test_file.is_file():
        return False, f"missing {rel}"
    text = test_file.read_text(encoding="utf-8")
    if "test_tempo_trace_search_by_agent_run_request_id" not in text:
        return False, "trace test not found"
    return True, rel


def run_demo_smoke(*, manifest_path: Path | None = None) -> dict:
    os.environ["ARBOR_ALLOW_PLAN_SCRIPT"] = "1"
    manifest_path = manifest_path or demo_manifest_path()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results: list[dict] = []
    for step in manifest.get("steps") or []:
        step_id = str(step.get("id") or "")
        verify = dict(step.get("verify") or {})
        kind = str(verify.get("kind") or "")
        ok = False
        detail = "unknown kind"
        if kind == "agent":
            case_ids = {str(v) for v in verify.get("case_ids") or []}
            ok, detail = _agent_case_ok(case_ids=case_ids)
        elif kind == "multimodal":
            case_ids = {str(v) for v in verify.get("case_ids") or []}
            ok, detail = _multimodal_case_ok(case_ids=case_ids)
        elif kind == "inbox_extract":
            ok, detail = _inbox_extract_ok()
        elif kind == "agent_e2e_chain":
            ok, detail = _agent_e2e_chain_ok(case_id=str(verify.get("case_id") or "ticket-with-approval"))
        elif kind == "trace_test":
            ok, detail = _trace_test_ok(str(verify.get("path") or ""))
        results.append(
            {
                "id": step_id,
                "title": step.get("title"),
                "ok": ok,
                "detail": detail,
            }
        )
    passed = sum(1 for item in results if item.get("ok"))
    total = len(results)
    return {
        "suite_version": manifest.get("suite_version"),
        "step_pass_rate": passed / total if total else 0.0,
        "steps": results,
        "start_command": manifest.get("start_command"),
        "recording": manifest.get("recording"),
    }
