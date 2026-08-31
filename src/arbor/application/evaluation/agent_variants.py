from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AgentEvalVariant:
    """Capability flags for fair agent ablation (same cases, different switches)."""

    id: str
    label: str
    max_steps: int
    step_rag_enabled: bool
    recovery_enabled: bool
    approval_enabled: bool
    planner_version: str = "scripted-v1"

    def to_metadata(self) -> dict:
        return asdict(self)


DEFAULT_ABLATION_VARIANTS: tuple[AgentEvalVariant, ...] = (
    AgentEvalVariant(
        id="single_round_tool",
        label="单轮 tool calling（max_steps=1）",
        max_steps=1,
        step_rag_enabled=False,
        recovery_enabled=False,
        approval_enabled=False,
    ),
    AgentEvalVariant(
        id="bounded_agent_loop",
        label="有界 Agent 循环（无 Step RAG）",
        max_steps=8,
        step_rag_enabled=False,
        recovery_enabled=False,
        approval_enabled=False,
    ),
    AgentEvalVariant(
        id="bounded_step_rag",
        label="有界循环 + Step RAG",
        max_steps=8,
        step_rag_enabled=True,
        recovery_enabled=False,
        approval_enabled=False,
    ),
    AgentEvalVariant(
        id="bounded_rag_recovery_hitl",
        label="Step RAG + 恢复/HITL",
        max_steps=8,
        step_rag_enabled=True,
        recovery_enabled=True,
        approval_enabled=True,
    ),
)
