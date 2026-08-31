from __future__ import annotations

import json

import pytest

from arbor.application.agent.planner import (
    FallbackPlanner,
    LLMPlanner,
    ScriptedPlanner,
    filter_evidence_ids,
    is_repeated_action_loop,
)
from arbor.domain.agent.action import validate_planner_action
from arbor.domain.errors import DomainError


def test_scripted_planner_follows_plan_script():
    planner = ScriptedPlanner()
    script = [
        {"schema_version": 1, "action": "retrieve", "query": "q", "scopes": ["semantic_memory"]},
        {"schema_version": 1, "action": "answer", "text": "ok", "citations": [], "completion": True},
    ]
    first = planner.next_action(
        goal="test",
        steps=[],
        context_manifest={},
        tool_schemas=[],
        budget={},
        plan_script=script,
        evidence_ids=[],
    )
    assert first["action"] == "retrieve"
    second = planner.next_action(
        goal="test",
        steps=[{"kind": "retrieve", "status": "completed"}],
        context_manifest={},
        tool_schemas=[],
        budget={},
        plan_script=script,
        evidence_ids=["m1"],
    )
    assert second["action"] == "answer"


def test_filter_evidence_drops_forged_ids():
    action = validate_planner_action(
        {
            "schema_version": 1,
            "action": "tool",
            "tool_name": "ticket.create",
            "arguments": {"title": "x"},
            "evidence_ids": ["m1", "forged"],
        }
    )
    filtered = filter_evidence_ids(action, ["m1"])
    assert filtered["evidence_ids"] == ["m1"]


def test_fallback_planner_handoff_on_invalid_json(monkeypatch):
    class BrokenPrimary:
        def next_action(self, **kwargs):
            raise DomainError("LLM_INVALID_JSON", "bad json")

    planner = FallbackPlanner(BrokenPrimary())
    action = planner.next_action(
        goal="goal",
        steps=[],
        context_manifest={},
        tool_schemas=[],
        budget={},
    )
    assert action["action"] == "handoff"
    assert planner.last_metadata.get("fallback_used") is True


def test_llm_planner_parses_json_object(monkeypatch):
    payload = {
        "schema_version": 1,
        "action": "answer",
        "text": "done",
        "citations": [],
        "completion": True,
    }

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    monkeypatch.setattr(
        "arbor.application.agent.planner.chat_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr(
        "arbor.application.agent.planner.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )
    planner = LLMPlanner(model="deepseek-chat")
    action = planner.next_action(
        goal="hello",
        steps=[],
        context_manifest={},
        tool_schemas=[{"name": "ticket.create"}],
        budget={"max_steps": 8, "current_step": 1},
        evidence_ids=[],
    )
    assert action["action"] == "answer"
    assert planner.last_metadata.get("model") == "deepseek-chat"


def test_llm_planner_missing_key_raises(monkeypatch):
    monkeypatch.setattr("arbor.application.agent.planner.chat_api_key", lambda: "")
    planner = LLMPlanner()
    with pytest.raises(DomainError) as exc:
        planner.next_action(
            goal="hello",
            steps=[],
            context_manifest={},
            tool_schemas=[],
            budget={},
        )
    assert exc.value.code == "LLM_UNAVAILABLE"


def test_action_loop_detection():
    action = validate_planner_action(
        {
            "schema_version": 1,
            "action": "retrieve",
            "query": "same",
            "scopes": ["semantic_memory"],
        }
    )
    steps = [{"input": dict(action)} for _ in range(3)]
    assert is_repeated_action_loop(steps, action) is True


def test_unknown_action_rejected():
    with pytest.raises(DomainError):
        validate_planner_action({"schema_version": 1, "action": "fly"})
