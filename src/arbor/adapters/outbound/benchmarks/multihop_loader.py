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


def _extract_yes_no(text: str) -> str | None:
    """Pull a leading Yes/No from verbose LLM answers."""
    norm = normalize_answer(text)
    if not norm:
        return None
    first = norm.split()[0]
    if first in {"yes", "no"}:
        return first
    for prefix in ("the answer is yes", "the answer is no", "answer yes", "answer no"):
        if norm.startswith(prefix):
            return "yes" if "yes" in prefix else "no"
    if re.search(r"\byes\b", norm) and not re.search(r"\bno\b", norm):
        return "yes"
    if re.search(r"\bno\b", norm) and not re.search(r"\byes\b", norm):
        return "no"
    return None


NULL_QUERY_ANSWER = "Insufficient information."

_ANSWER_EQUIVALENTS: dict[str, frozenset[str]] = {
    "yes": frozenset({"yes", "agree", "true", "correct"}),
    "no": frozenset({"no", "disagree", "false", "incorrect"}),
    "agree": frozenset({"yes", "agree", "true"}),
    "disagree": frozenset({"no", "disagree", "false"}),
}

_INSUFFICIENT_MARKERS = (
    "insufficient information",
    "not enough information",
    "cannot determine",
    "unable to determine",
    "no sufficient information",
    "insufficient info",
)


def _answers_equivalent(expected: str, actual: str) -> bool:
    exp = normalize_answer(expected)
    act = normalize_answer(actual)
    if not exp or not act:
        return False
    if exp in _ANSWER_EQUIVALENTS:
        return any(token in act.split()[:3] for token in _ANSWER_EQUIVALENTS[exp])
    for key, aliases in _ANSWER_EQUIVALENTS.items():
        if exp == normalize_answer(key) and any(token in act.split()[:3] for token in aliases):
            return True
    if "insufficient" in exp:
        return any(marker in act for marker in _INSUFFICIENT_MARKERS)
    return False


def answer_em(expected: str, actual: str) -> float:
    exp = normalize_answer(expected)
    act = normalize_answer(actual)
    if exp == act:
        return 1.0
    if _answers_equivalent(expected, actual):
        return 1.0
    if exp in {"yes", "no"}:
        extracted = _extract_yes_no(actual)
        if extracted == exp:
            return 1.0
    if exp and act and exp in act:
        return 1.0
    if exp and act and act in exp:
        return 1.0
    return 0.0


_ENTITY_STOPWORDS = frozenset(
    {"Does", "Do", "Did", "The", "A", "An", "What", "When", "Where", "Who", "How", "Which", "Are", "Is", "Was", "Were"}
)


def compact_retrieve_query(question: str, *, max_words: int = 24) -> str:
    """Extract entity-heavy query for benchmark retrieval."""
    quoted = [
        m.group(1)
        for m in re.finditer(r'"([^"]+)"', question or "")
    ]
    caps = re.findall(
        r"\b[A-Z][A-Za-z0-9'.-]*(?:\s+(?:[A-Z][A-Za-z0-9'.-]*|(?:'s)))*\b",
        question or "",
    )
    parts: list[str] = []
    for chunk in quoted + caps:
        chunk = chunk.strip().strip("'").strip()
        if not chunk or chunk in _ENTITY_STOPWORDS:
            continue
        if chunk not in parts:
            parts.append(chunk)
    if parts:
        return " ".join(parts)[:400]
    words = (question or "").split()
    return " ".join(words[:max_words])


def primary_retrieve_query(question: str) -> str:
    """First-hop query: entities plus a short question prefix."""
    entities = compact_retrieve_query(question, max_words=12)
    words = (question or "").split()[:16]
    prefix = " ".join(words)
    if entities and entities not in prefix:
        return f"{entities} {prefix}"[:400]
    return prefix[:400]


def secondary_retrieve_query(question: str) -> str:
    """Second-hop query: full question for recall on comparison/temporal hops."""
    return (question or "").strip()[:500]


def tertiary_retrieve_query(question: str) -> str:
    """Third-hop query: compact entities only for missed supporting facts."""
    return compact_retrieve_query(question, max_words=16)


def answer_instruction_for_type(question_type: str) -> str:
    hints = {
        "comparison_query": (
            "This is a multi-source comparison. Each source/clause in the question must be verified separately."
        ),
        "temporal_query": (
            "This is a temporal ordering question. Verify each date/event claim in the evidence before deciding."
        ),
        "inference_query": (
            "This is an inference question. Find the single entity/name that satisfies ALL parts. "
            "Answer with one entity name or short phrase only."
        ),
        "null_query": (
            f"The corpus lacks supporting facts for this question. "
            f'Answer exactly: "{NULL_QUERY_ANSWER}"'
        ),
    }
    return hints.get(question_type, "Answer with the shortest factual phrase only.")


def is_null_query_case(case: dict) -> bool:
    return str(case.get("question_type") or "") == "null_query"


def uses_two_stage_reasoning(question_type: str) -> bool:
    return question_type in {"comparison_query", "temporal_query"}


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


def seed_corpus_to_memory(
    *,
    memories,
    vectors,
    embed,
    corpus: list[dict],
    tenant_id,
    persona_id,
    truncate_chars: int | None = 1200,
) -> int:
    """Index benchmark corpus docs as semantic memories for real RAG eval."""
    from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus, MemoryType
    from arbor.domain.shared.ids import MemoryId

    seeded = 0
    for doc in corpus or []:
        doc_id = str(doc.get("id") or "").strip()
        if not doc_id:
            continue
        title = str(doc.get("title") or "").strip()
        body = str(doc.get("text") or "").strip()
        text = f"{title}\n{body}".strip() if title else body
        if truncate_chars and len(text) > truncate_chars:
            text = text[:truncate_chars].rsplit(" ", 1)[0]
        if not text:
            continue
        item = MemoryItem(
            id=MemoryId(doc_id),
            tenant_id=tenant_id,
            persona_id=persona_id,
            text=text,
            type=MemoryType.FILE_CHUNK,
            status=MemoryStatus.ACTIVE,
            memory_class=MemoryClass.SEMANTIC,
            source={"benchmark_doc_id": doc_id, "url": doc.get("url")},
        )
        memories.save(item)
        vectors.upsert(tenant_id, persona_id, item.id, embed.embed(text), item.status)
        seeded += 1
    return seeded


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
