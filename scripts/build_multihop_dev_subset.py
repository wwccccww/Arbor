#!/usr/bin/env python3
"""Build frozen MultiHop-RAG official dev subset (100 stratified queries + corpus)."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "eval" / "public"
EXTERNAL = PUBLIC / "external" / "multihop"
DEV_OUT = PUBLIC / "dev" / "multihop-dev.json"
HF_BASE = "https://huggingface.co/datasets/yixuantt/MultiHopRAG/resolve/main"

STRATIFIED_LIMITS = {
    "inference_query": 30,
    "comparison_query": 30,
    "temporal_query": 25,
    "null_query": 15,
}


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        return
    with urllib.request.urlopen(url, timeout=180) as resp:
        dest.write_bytes(resp.read())


def _doc_id(url: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"mh-official-{digest}"


def _plan_script(*, query: str, answer: str, supporting_ids: list[str]) -> list[dict]:
    if not supporting_ids:
        return [
            {
                "schema_version": 1,
                "action": "answer",
                "text": answer,
                "citations": [],
                "completion": True,
            }
        ]
    return [
        {
            "schema_version": 1,
            "action": "retrieve",
            "query": query[:500],
            "scopes": ["semantic_memory"],
            "expected_hit_ids": supporting_ids,
        },
        {
            "schema_version": 1,
            "action": "answer",
            "text": answer,
            "citations": supporting_ids,
            "completion": True,
        },
    ]


def _pick_stratified(rows: list[dict]) -> list[dict]:
    by_type: dict[str, list[dict]] = {key: [] for key in STRATIFIED_LIMITS}
    for row in rows:
        qtype = str(row.get("question_type") or "")
        if qtype in by_type:
            by_type[qtype].append(row)
    picked: list[dict] = []
    for qtype, limit in STRATIFIED_LIMITS.items():
        picked.extend(by_type[qtype][:limit])
    return picked


def build_dev(*, download: bool = True) -> dict:
    qa_path = EXTERNAL / "MultiHopRAG.json"
    corpus_path = EXTERNAL / "corpus.json"
    if download:
        _download(f"{HF_BASE}/MultiHopRAG.json", qa_path)
        _download(f"{HF_BASE}/corpus.json", corpus_path)

    corpus_rows = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus_by_url = {str(row.get("url") or ""): row for row in corpus_rows}
    selected = _pick_stratified(json.loads(qa_path.read_text(encoding="utf-8")))

    corpus_docs: dict[str, dict] = {}
    cases: list[dict] = []
    for idx, row in enumerate(selected):
        query = str(row.get("query") or "")
        answer = str(row.get("answer") or "")
        qtype = str(row.get("question_type") or "")
        supporting_ids: list[str] = []
        for ev in row.get("evidence_list") or []:
            url = str(ev.get("url") or "")
            if not url:
                continue
            doc_id = _doc_id(url)
            supporting_ids.append(doc_id)
            if doc_id not in corpus_docs:
                upstream = corpus_by_url.get(url) or {}
                text = str(upstream.get("body") or ev.get("fact") or "")
                corpus_docs[doc_id] = {
                    "id": doc_id,
                    "title": str(upstream.get("title") or ev.get("title") or ""),
                    "text": text,
                    "tenant_id": "tenant-a",
                    "url": url,
                    "category": str(upstream.get("category") or ev.get("category") or ""),
                }
        case_id = f"multihop-dev-{idx:03d}"
        cases.append(
            {
                "id": case_id,
                "question": query,
                "question_type": qtype,
                "supporting_fact_ids": supporting_ids,
                "expected_answer": answer,
                "min_supporting_recall": 1.0,
                "min_answer_em": 1.0,
                "min_faithfulness": 1.0,
                "plan_script": _plan_script(query=query, answer=answer, supporting_ids=supporting_ids),
                "metadata": {
                    "official": True,
                    "source": "yixuantt/MultiHopRAG",
                    "question_type": qtype,
                },
            }
        )

    return {
        "benchmark_id": "multihop",
        "suite_version": "multihop-dev-v1",
        "description": "Official MultiHop-RAG dev subset (100 stratified queries + referenced corpus).",
        "planner_kind": "fake",
        "source": {
            "dataset": "yixuantt/MultiHopRAG",
            "git_ref": "main",
            "stratified_limits": STRATIFIED_LIMITS,
        },
        "corpus": sorted(corpus_docs.values(), key=lambda doc: doc["id"]),
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_multihop_dev_subset")
    parser.add_argument("--out", default=str(DEV_OUT))
    parser.add_argument("--no-download", action="store_true")
    args = parser.parse_args(argv)
    payload = build_dev(download=not args.no_download)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode()).hexdigest()
    print(
        f"wrote {out} cases={len(payload['cases'])} "
        f"corpus={len(payload['corpus'])} sha256={digest[:16]}…"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
