from __future__ import annotations

import json
import re
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
BFCL_DEV = PUBLIC_ROOT / "dev" / "bfcl-dev.json"


def load_manifest(path: Path | None = None) -> dict:
    path = path or BFCL_MANIFEST
    return json.loads(path.read_text(encoding="utf-8"))


def load_smoke_cases(path: Path | None = None) -> dict:
    path = path or BFCL_SMOKE
    return json.loads(path.read_text(encoding="utf-8"))


def load_dev_cases(path: Path | None = None) -> dict:
    path = path or BFCL_DEV
    return json.loads(path.read_text(encoding="utf-8"))


def bfcl_function_to_schema(fn: dict) -> dict:
    """Normalize BFCL/OpenAI-style function object to JSON Schema."""
    if "parameters" in fn:
        schema = dict(fn["parameters"])
    elif "input_schema" in fn:
        schema = dict(fn["input_schema"])
    else:
        return {"type": "object", "properties": {}}
    if schema.get("type") == "dict":
        schema["type"] = "object"
    props = dict(schema.get("properties") or {})
    for spec in props.values():
        if isinstance(spec, dict) and spec.get("type") == "dict":
            spec["type"] = "object"
    schema["properties"] = props
    return schema


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
                aliases=[name.lower()],
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


def normalize_planner_tool_payload(data: dict) -> dict:
    """Normalize common LLM variants into planner tool actions."""
    out = dict(data)
    action = str(out.get("action") or "").strip().lower()
    if action in {"function", "tool_call", "call"}:
        out["action"] = "tool"
    if out.get("action") == "tool":
        if not out.get("tool_name"):
            for key in ("name", "function", "function_name"):
                if out.get(key):
                    out["tool_name"] = out[key]
                    break
        if out.get("arguments") is None:
            for key in ("parameters", "args", "input"):
                if out.get(key) is not None:
                    out["arguments"] = out[key]
                    break
        if out.get("arguments") is None:
            out["arguments"] = {}
    return out


def _schema_type(spec: dict) -> str | None:
    typ = spec.get("type")
    if isinstance(typ, list):
        for candidate in typ:
            if candidate and candidate != "null":
                return str(candidate)
        return None
    return str(typ) if typ else None


def _coerce_scalar(value: object, spec: dict) -> object:
    typ = _schema_type(spec)
    if typ == "string":
        if value is None:
            return ""
        text = str(value).strip()
        if re.fullmatch(r"\d{4}[/.\-]\d{1,2}[/.\-]\d{1,2}", text):
            parts = re.split(r"[/.\-]", text)
            if len(parts) == 3:
                y, m, d = parts
                return f"{y}-{int(m):02d}-{int(d):02d}"
        return text
    if typ == "integer":
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value.strip())
        return value
    if typ == "number":
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return value
        return value
    if typ == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            low = value.strip().lower()
            if low in {"true", "1", "yes"}:
                return True
            if low in {"false", "0", "no"}:
                return False
        return value
    if typ == "array":
        if isinstance(value, list):
            item_spec = dict(spec.get("items") or {})
            return [_coerce_scalar(item, item_spec) for item in value]
        if isinstance(value, str):
            return [value]
        return value
    if typ == "object" and isinstance(value, dict):
        nested = dict(spec.get("properties") or {})
        return coerce_tool_arguments(
            value,
            {"type": "object", "properties": nested, "required": spec.get("required") or []},
        )
    return value


def coerce_tool_arguments(arguments: dict, schema: dict) -> dict:
    """Best-effort schema coercion for BFCL / AgentDojo tool arguments."""
    props = dict(schema.get("properties") or {})
    if not props:
        return dict(arguments or {})
    required = set(schema.get("required") or [])
    coerced: dict = {}
    incoming = dict(arguments or {})
    for key, spec in props.items():
        if key in incoming:
            coerced[key] = _coerce_scalar(incoming[key], spec if isinstance(spec, dict) else {})
        elif "default" in (spec or {}):
            coerced[key] = spec["default"]
    for key in required:
        if key not in coerced and key in incoming:
            coerced[key] = _coerce_scalar(incoming[key], props.get(key) or {})
    return coerced if coerced else dict(incoming)


def schema_for_tool_name(tool_name: str, tool_schemas: list[dict]) -> dict:
    target = normalize_call_name(tool_name)
    for schema in tool_schemas or []:
        fn = dict(schema.get("function") or schema)
        name = normalize_call_name(str(fn.get("name") or schema.get("name") or ""))
        if name == target:
            if "parameters" in fn:
                return bfcl_function_to_schema(fn)
            if "input_schema" in fn:
                return dict(fn["input_schema"])
    return {"type": "object", "properties": {}}


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


def _value_in_options(actual: object, options: list) -> bool:
    if not options:
        return True
    for opt in options:
        if opt == "" or opt is None:
            if actual in ("", None):
                return True
            continue
        if isinstance(opt, float) or isinstance(actual, float):
            if abs(float(opt) - float(actual)) <= 1e-6:
                return True
        elif isinstance(opt, int) and isinstance(actual, (int, float)):
            if int(opt) == int(actual):
                return True
        elif isinstance(actual, int) and isinstance(opt, (int, float)):
            if int(actual) == int(opt):
                return True
        if isinstance(opt, str) and isinstance(actual, str) and opt.lower() == actual.lower():
            return True
    return False


def _missing_arg_allowed(options: list) -> bool:
    """BFCL ground truth lists ''/None when an omitted argument is acceptable."""
    return any(opt in ("", None) for opt in (options or []))


def _call_matches_ground_truth_item(actual: dict, gt_item: dict) -> tuple[bool, bool]:
    """Match one BFCL ground_truth dict entry against an actual call."""
    if not gt_item:
        return False, False
    exp_name = next(iter(gt_item.keys()))
    act_name = str(actual.get("name") or actual.get("tool_name") or "")
    fn_ok = normalize_call_name(exp_name) == normalize_call_name(act_name)
    if not fn_ok:
        return False, False
    exp_args = dict(gt_item.get(exp_name) or {})
    act_args = dict(actual.get("arguments") or {})
    arg_ok = True
    for key, options in exp_args.items():
        if key not in act_args:
            if not _missing_arg_allowed(list(options)):
                arg_ok = False
            continue
        if not _value_in_options(act_args[key], list(options)):
            arg_ok = False
    return True, arg_ok


def _score_unordered_ground_truth(
    *,
    actual_calls: list[dict],
    ground_truth: list[dict],
) -> tuple[bool, dict]:
    remaining = list(actual_calls)
    fn_hits = 0
    arg_hits = 0
    for gt_item in ground_truth:
        best_idx = -1
        best_fn = False
        best_arg = False
        for idx, act in enumerate(remaining):
            fn_ok, arg_ok = _call_matches_ground_truth_item(act, gt_item)
            if fn_ok and arg_ok:
                best_idx = idx
                best_fn, best_arg = True, True
                break
            if fn_ok and not best_fn:
                best_idx = idx
                best_fn, best_arg = fn_ok, arg_ok
        if best_idx >= 0:
            fn_hits += int(best_fn)
            arg_hits += int(best_arg)
            remaining.pop(best_idx)
    n = len(ground_truth) or 1
    scores = {
        "function_match": fn_hits / n,
        "argument_match": arg_hits / n,
        "executable": 1.0,
    }
    ok = (
        fn_hits == len(ground_truth)
        and arg_hits == len(ground_truth)
        and len(actual_calls) == len(ground_truth)
    )
    return ok, scores


def score_against_ground_truth(
    *,
    actual_calls: list[dict],
    ground_truth: list[dict],
    expect_no_tool: bool,
    unordered: bool = False,
) -> tuple[bool, dict]:
    if expect_no_tool:
        ok = len(actual_calls) == 0
        return ok, {
            "function_match": 1.0 if ok else 0.0,
            "argument_match": 1.0 if ok else 0.0,
            "executable": 1.0,
        }
    if not ground_truth:
        ok = len(actual_calls) == 0
        return ok, {
            "function_match": 1.0 if ok else 0.0,
            "argument_match": 1.0 if ok else 0.0,
            "executable": 1.0,
        }
    if unordered and len(ground_truth) > 1:
        return _score_unordered_ground_truth(actual_calls=actual_calls, ground_truth=ground_truth)
    if len(actual_calls) != len(ground_truth):
        fn_hits = 0
        arg_hits = 0
        for exp, act in zip(ground_truth, actual_calls, strict=False):
            fn_ok, arg_ok = _call_matches_ground_truth_item(act, exp)
            fn_hits += int(fn_ok)
            arg_hits += int(arg_ok)
        n = max(len(ground_truth), len(actual_calls))
        return False, {
            "function_match": fn_hits / n if n else 0.0,
            "argument_match": arg_hits / n if n else 0.0,
            "executable": 1.0,
        }
    fn_hits = 0
    arg_hits = 0
    for gt_item, act in zip(ground_truth, actual_calls, strict=True):
        fn_ok, arg_ok = _call_matches_ground_truth_item(act, gt_item)
        fn_hits += int(fn_ok)
        arg_hits += int(arg_ok)
    n = len(ground_truth) or 1
    scores = {
        "function_match": fn_hits / n,
        "argument_match": arg_hits / n,
        "executable": 1.0,
    }
    ok = fn_hits == n and arg_hits == n
    return ok, scores


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
