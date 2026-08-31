from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arbor.application.tools.registry import (
    IdempotencyPolicy,
    ToolDefinition,
    ToolRegistry,
    ToolRiskLevel,
)
from arbor.paths import repo_root

PUBLIC_ROOT = repo_root() / "eval" / "public"
BFCL_MANIFEST = PUBLIC_ROOT / "manifests" / "bfcl.json"
BFCL_SMOKE = PUBLIC_ROOT / "smoke" / "bfcl-smoke.json"


def load_manifest(path: Path | None = None) -> dict:
    path = path or BFCL_MANIFEST
    return json.loads(path.read_text(encoding="utf-8"))


def load_smoke_cases(path: Path | None = None) -> dict:
    path = path or BFCL_SMOKE
    return json.loads(path.read_text(encoding="utf-8"))


def bfcl_function_to_schema(fn: dict) -> dict:
    """Normalize BFCL/OpenAI-style function object to JSON Schema."""
    if "parameters" in fn:
        return dict(fn["parameters"])
    if "input_schema" in fn:
        return dict(fn["input_schema"])
    return {"type": "object", "properties": {}}


def register_bfcl_functions(registry: ToolRegistry, functions: list[dict]) -> None:
    for fn in functions or []:
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        registry.register(
            ToolDefinition(
                name=name,
                description=str(fn.get("description") or ""),
                input_schema=bfcl_function_to_schema(fn),
                risk_level=ToolRiskLevel.READ,
                idempotency_policy=IdempotencyPolicy.NONE,
                handler=lambda **_kwargs: {"status": "ok", "provider": "bfcl-stub"},
            )
        )


def plan_script_from_case(case: dict) -> list[dict]:
    if case.get("expect_no_tool"):
        return [
            {
                "schema_version": 1,
                "action": "answer",
                "text": str(case.get("answer_text") or "No tool call required."),
                "citations": [],
                "completion": True,
            }
        ]
    script: list[dict] = []
    for call in case.get("expected_calls") or []:
        script.append(
            {
                "schema_version": 1,
                "action": "tool",
                "tool_name": str(call.get("name") or call.get("tool_name") or ""),
                "arguments": dict(call.get("arguments") or {}),
                "evidence_ids": [],
            }
        )
    script.append(
        {
            "schema_version": 1,
            "action": "answer",
            "text": str(case.get("answer_text") or "Done."),
            "citations": [],
            "completion": True,
        }
    )
    return script


def normalize_call_name(name: str) -> str:
    return (name or "").strip().replace("-", "_")


def calls_equivalent(expected: dict, actual: dict) -> tuple[bool, bool]:
    """Return (function_match, argument_match)."""
    exp_name = normalize_call_name(str(expected.get("name") or expected.get("tool_name") or ""))
    act_name = normalize_call_name(str(actual.get("name") or actual.get("tool_name") or ""))
    if exp_name != act_name:
        return False, False
    exp_args = dict(expected.get("arguments") or {})
    act_args = dict(actual.get("arguments") or {})
    return True, _arguments_equal(exp_args, act_args)


def _arguments_equal(expected: dict, actual: dict) -> bool:
    if set(expected.keys()) != set(actual.keys()):
        return False
    for key, exp_val in expected.items():
        act_val = actual[key]
        if isinstance(exp_val, float) or isinstance(act_val, float):
            if abs(float(exp_val) - float(act_val)) > 1e-6:
                return False
        elif exp_val != act_val:
            return False
    return True


def validate_expected_executable(registry: ToolRegistry, case: dict) -> bool:
    if case.get("expect_no_tool"):
        return True
    for call in case.get("expected_calls") or []:
        name = str(call.get("name") or call.get("tool_name") or "")
        tool = registry.get(name)
        if tool is None:
            return False
        try:
            registry.validate_arguments(tool, dict(call.get("arguments") or {}))
        except Exception:
            return False
    return True


def extract_tool_calls_from_steps(steps: list[Any]) -> list[dict]:
    calls: list[dict] = []
    for step in steps:
        kind = getattr(step, "kind", None)
        kind_val = kind.value if hasattr(kind, "value") else str(kind or "")
        if kind_val != "tool":
            continue
        inp = dict(getattr(step, "input", None) or {})
        out = dict(getattr(step, "output", None) or {})
        if out.get("skipped"):
            continue
        calls.append(
            {
                "name": str(inp.get("tool_name") or ""),
                "arguments": dict(inp.get("arguments") or {}),
            }
        )
    return calls
