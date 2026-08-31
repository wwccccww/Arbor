#!/usr/bin/env python3
"""Download official BFCL JSONL and build frozen dev subset for CI/nightly."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "eval" / "public"
EXTERNAL = PUBLIC / "external" / "bfcl"
DEV_OUT = PUBLIC / "dev" / "bfcl-dev.json"
HF_BASE = "https://huggingface.co/datasets/gorilla-llm/Berkeley-Function-Calling-Leaderboard/resolve/main"

DEV_CATEGORIES = [
    ("BFCL_v3_simple.json", 73, "simple"),
    ("BFCL_v3_multiple.json", 55, "multiple"),
    ("BFCL_v3_parallel.json", 36, "parallel"),
    ("BFCL_v3_irrelevance.json", 36, "irrelevance"),
]


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        return
    with urllib.request.urlopen(url, timeout=120) as resp:
        dest.write_bytes(resp.read())


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _normalize_schema(params: dict) -> dict:
    schema = dict(params or {})
    if schema.get("type") == "dict":
        schema["type"] = "object"
    props = dict(schema.get("properties") or {})
    for spec in props.values():
        if isinstance(spec, dict) and spec.get("type") == "dict":
            spec["type"] = "object"
    schema["properties"] = props
    return schema


def _question_text(question: list) -> str:
    if not question:
        return ""
    turn = question[0] if question else []
    if isinstance(turn, list) and turn:
        return str(turn[0].get("content") or "")
    return str(question)


def _ground_truth_to_calls(ground_truth: list) -> list[dict]:
    calls: list[dict] = []
    for item in ground_truth or []:
        if not isinstance(item, dict):
            continue
        for name, args in item.items():
            arguments: dict = {}
            for key, options in (args or {}).items():
                if not isinstance(options, list):
                    continue
                chosen = None
                for opt in options:
                    if opt == "" or opt is None:
                        continue
                    chosen = opt
                    break
                if chosen is not None:
                    arguments[key] = chosen
            calls.append({"name": str(name), "arguments": arguments})
    return calls


def _convert_row(*, row: dict, category: str, answers: dict[str, dict]) -> dict:
    case_id = str(row.get("id") or "")
    functions = []
    for fn in row.get("function") or []:
        functions.append(
            {
                "name": str(fn.get("name") or ""),
                "description": str(fn.get("description") or ""),
                "parameters": _normalize_schema(dict(fn.get("parameters") or {})),
            }
        )
    answer = answers.get(case_id) or {}
    ground_truth = list(answer.get("ground_truth") or [])
    expect_no_tool = category == "irrelevance" or not ground_truth
    expected_calls = [] if expect_no_tool else _ground_truth_to_calls(ground_truth)
    return {
        "id": case_id,
        "source_category": category,
        "source_file": category,
        "goal": _question_text(row.get("question") or []),
        "functions": functions,
        "ground_truth": ground_truth,
        "expected_calls": expected_calls,
        "expect_no_tool": expect_no_tool,
        "answer_text": "No tool call required." if expect_no_tool else "Done.",
        "metadata": {"official": True, "bfcl_category": category},
    }


def build_dev(*, download: bool = True) -> dict:
    cases: list[dict] = []
    source_files: list[str] = []
    for filename, limit, category in DEV_CATEGORIES:
        q_url = f"{HF_BASE}/{filename}"
        q_path = EXTERNAL / filename
        if download:
            _download(q_url, q_path)
        source_files.append(filename)
        answers: dict[str, dict] = {}
        a_path = EXTERNAL / "possible_answer" / filename
        a_url = f"{HF_BASE}/possible_answer/{filename}"
        if category != "irrelevance":
            if download:
                _download(a_url, a_path)
            if a_path.is_file():
                for row in _load_jsonl(a_path):
                    answers[str(row.get("id") or "")] = row
        for row in _load_jsonl(q_path)[:limit]:
            cases.append(_convert_row(row=row, category=category, answers=answers))

    payload = {
        "benchmark_id": "bfcl",
        "suite_version": "bfcl-dev-v2",
        "description": "Official BFCL v3 dev subset (200 cases: simple/multiple/parallel/irrelevance) frozen from HuggingFace.",
        "planner_kind": "fake",
        "source": {
            "dataset": "gorilla-llm/Berkeley-Function-Calling-Leaderboard",
            "git_ref": "main",
            "files": source_files,
        },
        "cases": cases,
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_bfcl_dev_subset")
    parser.add_argument("--out", default=str(DEV_OUT))
    parser.add_argument("--no-download", action="store_true")
    args = parser.parse_args(argv)
    payload = build_dev(download=not args.no_download)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode()).hexdigest()
    print(f"wrote {out} cases={len(payload['cases'])} sha256={digest[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
