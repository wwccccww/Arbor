"""Build a hierarchical trace tree for AgentRun → Step → RAG/Tool/Approval."""

from __future__ import annotations

from arbor.domain.agent.step import AgentStep, StepKind


def _child_node(node_type: str, label: str, detail: dict | None = None) -> dict:
    payload: dict = {"type": node_type, "label": label}
    if detail:
        payload["detail"] = detail
    return payload


def build_agent_step_tree(steps: list[AgentStep], *, run_goal: str | None = None) -> dict:
    children: list[dict] = []
    for step in sorted(steps, key=lambda item: item.sequence):
        kind = step.kind.value if hasattr(step.kind, "value") else str(step.kind)
        node: dict = {
            "id": step.id,
            "sequence": step.sequence,
            "kind": kind,
            "status": step.status.value if hasattr(step.status, "value") else str(step.status),
            "label": f"{step.sequence}. {kind}",
            "children": [],
        }
        if step.started_at:
            node["started_at"] = step.started_at
        if step.finished_at:
            node["finished_at"] = step.finished_at
        latency = (step.observation or {}).get("latency_ms")
        if latency is not None:
            node["latency_ms"] = latency

        output = dict(step.output or {})
        observation = dict(step.observation or {})

        if step.kind == StepKind.RETRIEVE:
            hit_ids = list(output.get("hit_ids") or [])
            node["children"].append(
                _child_node("rag", f"检索命中 {len(hit_ids)}", {"hit_ids": hit_ids})
            )
            manifest = output.get("context_manifest")
            if isinstance(manifest, dict):
                selected = list(manifest.get("selected_item_ids") or [])
                node["children"].append(
                    _child_node(
                        "context",
                        f"上下文 {len(selected)} 项",
                        {
                            "selected_item_ids": selected,
                            "token_usage": manifest.get("token_usage"),
                            "untrusted_instruction_count": manifest.get("untrusted_instruction_count"),
                        },
                    )
                )
        elif step.kind == StepKind.TOOL:
            tool_name = str(output.get("tool") or (step.input or {}).get("tool_name") or "tool")
            node["children"].append(_child_node("tool", tool_name, {"result": output.get("result")}))
            if output.get("approval_id"):
                node["children"].append(
                    _child_node("approval", "待审批", {"approval_id": output.get("approval_id")})
                )
            if observation.get("approval_required"):
                node["children"].append(_child_node("approval", "需审批", observation))
        elif step.kind == StepKind.ANSWER:
            citations = list(output.get("citations") or [])
            node["children"].append(
                _child_node("answer", output.get("text") or "回答", {"citations": citations})
            )
        elif step.kind == StepKind.HANDOFF or step.kind == StepKind.REFLECT:
            node["children"].append(_child_node("outcome", kind, output))

        if step.error_kind:
            node["children"].append(
                _child_node("error", str(step.error_kind), {"message": step.error_message})
            )

        children.append(node)

    return {
        "type": "run",
        "label": run_goal or "Agent Run",
        "children": children,
    }
