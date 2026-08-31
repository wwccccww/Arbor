from __future__ import annotations

import json
import re
from typing import Any

import httpx

from arbor.domain.agent.action import validate_planner_action
from arbor.domain.errors import DomainError
from arbor.env import chat_api_key, chat_base_url, chat_model

PROMPT_VERSION = "agent-planner-v1"
SCHEMA_VERSION = 1


def filter_evidence_ids(action: dict, allowed: list[str]) -> dict:
    """Drop citations / evidence not injected in the current step."""
    allowed_set = set(allowed or [])
    out = dict(action)
    if out.get("action") == "tool":
        out["evidence_ids"] = [e for e in out.get("evidence_ids") or [] if e in allowed_set]
    if out.get("action") == "answer":
        out["citations"] = [c for c in out.get("citations") or [] if c in allowed_set]
    return out


def action_signature(action: dict) -> str:
    payload = {
        "action": action.get("action"),
        "tool_name": action.get("tool_name"),
        "query": action.get("query"),
        "arguments": action.get("arguments"),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def is_repeated_action_loop(steps: list[dict], action: dict, *, window: int = 3) -> bool:
    """Detect identical planner actions repeated ``window`` times."""
    if len(steps) < window:
        return False
    sig = action_signature(action)
    recent_inputs = [s.get("input") or {} for s in steps[-window:]]
    return all(action_signature(inp) == sig for inp in recent_inputs)


class ScriptedPlanner:
    """Deterministic planner for tests and agent-smoke eval."""

    planner_kind = "fake"
    planner_version = "scripted-v1"

    def next_action(
        self,
        *,
        goal: str,
        steps: list[dict],
        context_manifest: dict | None = None,
        tool_schemas: list[dict] | None = None,
        budget: dict | None = None,
        plan_script: list[dict] | None = None,
        evidence_ids: list[str] | None = None,
        run_metadata: dict | None = None,
    ) -> dict:
        del context_manifest, tool_schemas, budget
        meta = dict(run_metadata or {})
        eval_variant = dict(meta.get("eval_variant") or {})
        step_rag_enabled = eval_variant.get("step_rag_enabled", True)
        pending_query = str(meta.get("pending_retrieve_query") or "").strip()
        if pending_query and step_rag_enabled:
            last_tool_idx = max(
                (i for i, s in enumerate(steps) if s.get("kind") == "tool"),
                default=-1,
            )
            retrieve_after_tool = any(
                s.get("kind") == "retrieve" for s in steps[last_tool_idx + 1 :]
            )
            if not retrieve_after_tool:
                action = validate_planner_action(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "action": "retrieve",
                        "query": pending_query,
                        "scopes": ["semantic_memory", "procedural_memory", "episodic_memory"],
                        "reason": "re-retrieve after tool observation",
                    }
                )
                return filter_evidence_ids(action, list(evidence_ids or []))

        if plan_script:
            index = len(steps)
            if index < len(plan_script):
                action = validate_planner_action(plan_script[index])
                return filter_evidence_ids(action, list(evidence_ids or []))

        if not any(s.get("kind") == "retrieve" for s in steps):
            action = validate_planner_action(
                {
                    "schema_version": SCHEMA_VERSION,
                    "action": "retrieve",
                    "query": goal,
                    "scopes": ["semantic_memory", "procedural_memory", "episodic_memory"],
                    "reason": "gather evidence before acting",
                }
            )
            return filter_evidence_ids(action, list(evidence_ids or []))
        goal_lower = (goal or "").lower()
        if "ticket" in goal_lower and not any(s.get("kind") == "tool" for s in steps):
            action = validate_planner_action(
                {
                    "schema_version": SCHEMA_VERSION,
                    "action": "tool",
                    "tool_name": "ticket.create",
                    "arguments": {"title": goal[:80], "priority": "high"},
                    "evidence_ids": list(evidence_ids or []),
                    "reason": "goal requires ticket",
                }
            )
            return filter_evidence_ids(action, list(evidence_ids or []))
        action = validate_planner_action(
            {
                "schema_version": SCHEMA_VERSION,
                "action": "answer",
                "text": f"已完成处理：{goal}",
                "citations": list(evidence_ids or []),
                "completion": True,
            }
        )
        return filter_evidence_ids(action, list(evidence_ids or []))


class LLMPlanner:
    """Real-model structured action planner (JSON only, no chain-of-thought)."""

    planner_kind = "real"
    planner_version = PROMPT_VERSION

    def __init__(
        self,
        *,
        model: str | None = None,
        provider: str = "deepseek",
        timeout_s: float = 45.0,
    ) -> None:
        self.model = model or chat_model()
        self.provider = provider
        self.timeout_s = timeout_s
        self.last_metadata: dict[str, Any] = {}

    def next_action(
        self,
        *,
        goal: str,
        steps: list[dict],
        context_manifest: dict | None = None,
        tool_schemas: list[dict] | None = None,
        budget: dict | None = None,
        plan_script: list[dict] | None = None,
        evidence_ids: list[str] | None = None,
        run_metadata: dict | None = None,
    ) -> dict:
        del plan_script
        key = chat_api_key()
        if not key:
            raise DomainError("LLM_UNAVAILABLE", "chat API key missing for LLM planner")
        prompt = _planner_prompt(
            goal=goal,
            steps=steps,
            context_manifest=context_manifest or {},
            tool_schemas=tool_schemas or [],
            budget=budget or {},
            evidence_ids=list(evidence_ids or []),
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": goal},
            ],
            "max_tokens": 800,
            "temperature": 0.1,
        }
        try:
            response = httpx.post(
                f"{chat_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise DomainError("LLM_TIMEOUT", "planner request timed out") from exc
        except httpx.HTTPError as exc:
            raise DomainError("LLM_UPSTREAM", str(exc)) from exc
        if response.status_code == 429:
            raise DomainError("LLM_RATE_LIMIT", "planner rate limited")
        if response.status_code >= 500:
            raise DomainError("LLM_UPSTREAM", f"planner HTTP {response.status_code}")
        if response.status_code >= 400:
            raise DomainError("LLM_UPSTREAM", f"planner HTTP {response.status_code}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise DomainError("LLM_INVALID_RESPONSE", "planner response missing content") from exc
        raw = _parse_planner_json(content)
        action = validate_planner_action(raw)
        action = filter_evidence_ids(action, list(evidence_ids or []))
        self.last_metadata = {
            "provider": self.provider,
            "model": self.model,
            "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "reason_summary": str(action.get("reason") or "")[:200],
        }
        if run_metadata is not None:
            run_metadata["planner"] = dict(self.last_metadata)
        return action


class FallbackPlanner:
    """Primary planner with structured handoff on failure."""

    planner_kind = "fallback"
    planner_version = "fallback-v1"

    def __init__(self, primary, *, reason: str = "planner fallback") -> None:
        self.primary = primary
        self.reason = reason
        self.last_metadata: dict[str, Any] = {}

    def next_action(
        self,
        *,
        goal: str,
        steps: list[dict],
        context_manifest: dict | None = None,
        tool_schemas: list[dict] | None = None,
        budget: dict | None = None,
        plan_script: list[dict] | None = None,
        evidence_ids: list[str] | None = None,
        run_metadata: dict | None = None,
    ) -> dict:
        try:
            action = self.primary.next_action(
                goal=goal,
                steps=steps,
                context_manifest=context_manifest,
                tool_schemas=tool_schemas,
                budget=budget,
                plan_script=plan_script,
                evidence_ids=evidence_ids,
                run_metadata=run_metadata,
            )
            self.last_metadata = {"fallback_used": False}
            return action
        except DomainError as exc:
            self.last_metadata = {
                "fallback_used": True,
                "fallback_reason": exc.code,
            }
            if run_metadata is not None:
                run_metadata["planner"] = dict(self.last_metadata)
            return validate_planner_action(
                {
                    "schema_version": SCHEMA_VERSION,
                    "action": "handoff",
                    "text": self.reason,
                    "reason": exc.code,
                }
            )


def _planner_prompt(
    *,
    goal: str,
    steps: list[dict],
    context_manifest: dict,
    tool_schemas: list[dict],
    budget: dict,
    evidence_ids: list[str],
) -> str:
    tools_blob = json.dumps(tool_schemas[:12], ensure_ascii=False)
    steps_blob = json.dumps(
        [
            {"kind": s.get("kind"), "status": s.get("status")}
            for s in steps[-8:]
        ],
        ensure_ascii=False,
    )
    manifest_summary = {
        "item_count": len(context_manifest.get("items") or []),
        "token_usage": context_manifest.get("token_usage"),
        "untrusted_instruction_count": context_manifest.get("untrusted_instruction_count"),
    }
    budget_summary = {
        "max_steps": budget.get("max_steps"),
        "current_step": budget.get("current_step"),
        "token_budget": budget.get("token_budget"),
        "consumed_tokens": budget.get("consumed_tokens"),
    }
    return (
        "你是 Arbor Agent 规划器。只输出一个 JSON 对象，不要 markdown、不要解释、不要思维链。"
        f"schema_version={SCHEMA_VERSION}。"
        "允许 action: retrieve|tool|answer|request_clarification|handoff。"
        "tool 时 tool_name 必须来自工具列表；evidence_ids/citations 只能使用当前 evidence_ids。"
        "超预算或无法继续时使用 handoff。"
        f"工具列表: {tools_blob}。"
        f"已执行步骤: {steps_blob}。"
        f"上下文摘要: {json.dumps(manifest_summary, ensure_ascii=False)}。"
        f"预算: {json.dumps(budget_summary, ensure_ascii=False)}。"
        f"可用 evidence_ids: {json.dumps(evidence_ids, ensure_ascii=False)}。"
        f"目标: {goal}"
    )


def _parse_planner_json(content: str) -> dict:
    blob = (content or "").strip()
    if not blob:
        raise DomainError("LLM_INVALID_JSON", "empty planner output")
    match = re.search(r"\{.*\}", blob, flags=re.DOTALL)
    if not match:
        raise DomainError("LLM_INVALID_JSON", "planner output is not JSON object")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise DomainError("LLM_INVALID_JSON", "planner JSON parse failed") from exc
    if not isinstance(data, dict):
        raise DomainError("LLM_INVALID_JSON", "planner output must be object")
    return data
