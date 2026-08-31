from __future__ import annotations

import json
import re
from pathlib import Path

from arbor.paths import repo_root

PUBLIC_ROOT = repo_root() / "eval" / "public"
MULTIHOP_MANIFEST = PUBLIC_ROOT / "manifests" / "multihop.json"
MULTIHOP_SMOKE = PUBLIC_ROOT / "smoke" / "multihop-smoke.json"
MULTIHOP_DEV = PUBLIC_ROOT / "dev" / "multihop-dev.json"
MULTIHOP_CORPUS = PUBLIC_ROOT / "corpora" / "multihop"


def load_manifest(path: Path | None = None) -> dict:
    path = path or MULTIHOP_MANIFEST
    return json.loads(path.read_text(encoding="utf-8"))


def load_smoke_cases(path: Path | None = None) -> dict:
    path = path or MULTIHOP_SMOKE
    return json.loads(path.read_text(encoding="utf-8"))


def load_dev_cases(path: Path | None = None) -> dict:
    path = path or MULTIHOP_DEV
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_answer(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def answer_em(expected: str, actual: str) -> float:
    return 1.0 if normalize_answer(expected) == normalize_answer(actual) else 0.0


def answer_f1(expected: str, actual: str) -> float:
    exp_tokens = normalize_answer(expected).split()
    act_tokens = normalize_answer(actual).split()
    if not exp_tokens and not act_tokens:
        return 1.0
    if not exp_tokens or not act_tokens:
        return 0.0
    common = set(exp_tokens) & set(act_tokens)
    if not common:
        return 0.0
    precision = len(common) / len(act_tokens)
    recall = len(common) / len(exp_tokens)
    return 2 * precision * recall / (precision + recall)


def supporting_fact_recall(*, expected_ids: list[str], retrieved_ids: list[str]) -> float:
    if not expected_ids:
        return 1.0
    hits = sum(1 for doc_id in expected_ids if doc_id in retrieved_ids)
    return hits / len(expected_ids)


def citation_precision(*, citations: list[str], retrieved_ids: list[str]) -> float:
    if not citations:
        return 1.0
    valid = sum(1 for cid in citations if cid in retrieved_ids)
    return valid / len(citations)


def citation_recall(*, citations: list[str], expected_ids: list[str]) -> float:
    if not expected_ids:
        return 1.0
    cited = sum(1 for doc_id in expected_ids if doc_id in citations)
    return cited / len(expected_ids)


def faithfulness(*, citations: list[str], retrieved_ids: list[str]) -> float:
    if not citations:
        return 1.0
    subset = all(cid in retrieved_ids for cid in citations)
    return 1.0 if subset else 0.0


def build_corpus_index(corpus: list[dict]) -> dict[str, dict]:
    return {str(doc["id"]): dict(doc) for doc in corpus or [] if doc.get("id")}


def retrieve_from_corpus(*, query: str, corpus: list[dict], top_k: int = 5) -> list[str]:
    """Deterministic keyword retrieval for smoke — not production RAG."""
    query_tokens = set(normalize_answer(query).split())
    scored: list[tuple[float, str]] = []
    for doc in corpus or []:
        doc_id = str(doc.get("id") or "")
        text = normalize_answer(str(doc.get("text") or "") + " " + str(doc.get("title") or ""))
        doc_tokens = set(text.split())
        overlap = len(query_tokens & doc_tokens)
        if overlap:
            scored.append((float(overlap), doc_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [doc_id for _, doc_id in scored[:top_k]]


def extract_answer_from_steps(steps: list) -> tuple[str, list[str], list[str]]:
    answer_text = ""
    citations: list[str] = []
    retrieved: list[str] = []
    for step in steps:
        kind = getattr(step, "kind", None)
        kind_val = kind.value if hasattr(kind, "value") else str(kind or "")
        inp = dict(getattr(step, "input", None) or {})
        out = dict(getattr(step, "output", None) or {})
        if kind_val == "retrieve":
            for mid in out.get("memory_ids") or out.get("hit_ids") or inp.get("expected_hit_ids") or []:
                retrieved.append(str(mid))
        if kind_val == "answer":
            answer_text = str(out.get("text") or out.get("answer") or inp.get("text") or answer_text)
            for cid in out.get("citations") or out.get("citation_ids") or inp.get("citations") or []:
                citations.append(str(cid))
    return answer_text, citations, retrieved


def expected_from_plan_script(case: dict) -> tuple[str, list[str], list[str]]:
    answer_text = ""
    citations: list[str] = []
    retrieved: list[str] = []
    for step in case.get("plan_script") or []:
        if str(step.get("action")) == "retrieve":
            retrieved.extend(str(x) for x in step.get("expected_hit_ids") or [])
        if str(step.get("action")) == "answer":
            answer_text = str(step.get("text") or answer_text)
            citations.extend(str(x) for x in step.get("citations") or [])
    return answer_text, citations, retrieved


def plan_script_from_case(case: dict) -> list[dict]:
    return list(case.get("plan_script") or [])


def expected_retrieved_ids(case: dict) -> list[str]:
    ids: list[str] = []
    for step in case.get("plan_script") or []:
        if str(step.get("action")) == "retrieve":
            ids.extend(str(x) for x in step.get("expected_hit_ids") or [])
    return ids
