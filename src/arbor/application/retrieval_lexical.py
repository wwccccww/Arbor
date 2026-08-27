from __future__ import annotations

import re

from arbor.domain.memory.memory import MemoryItem, MemoryType
from arbor.domain.shared.textvec import cosine

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[a-zA-Z]+")


def tokenize(text: str) -> set[str]:
    stripped = (text or "").strip().lower()
    if not stripped:
        return set()
    tokens: set[str] = set()
    for piece in _CJK.findall(stripped):
        if len(piece) == 1:
            tokens.add(piece)
        else:
            for i in range(len(piece) - 1):
                tokens.add(piece[i : i + 2])
    for word in _LATIN.findall(stripped):
        if len(word) >= 2:
            tokens.add(word)
    if not tokens and stripped:
        tokens.add(stripped[:32])
    return tokens


def lexical_token_score(query: str, text: str) -> float:
    q_tokens = tokenize(query)
    if not q_tokens:
        return 0.0
    t_tokens = tokenize(text)
    if not t_tokens:
        return 0.0
    overlap = len(q_tokens & t_tokens)
    return overlap / len(q_tokens)


def memory_type_weight(item: MemoryItem, *, fact_weight: float, chunk_weight: float) -> float:
    if item.type is MemoryType.FACT:
        return fact_weight
    if item.type is MemoryType.EPISODE_SUMMARY:
        return (fact_weight + chunk_weight) / 2
    if item.type in {MemoryType.FILE_CHUNK, MemoryType.TRANSCRIPT, MemoryType.IMAGE_CAPTION}:
        return chunk_weight
    return chunk_weight


def score_memory(
    query: str,
    item: MemoryItem,
    embed,
    *,
    fact_weight: float,
    chunk_weight: float,
    query_vector: list[float] | None = None,
    item_vector: list[float] | None = None,
) -> float:
    blob = item.text or ""
    lexical = lexical_token_score(query, blob)
    if query_vector is not None and item_vector is not None:
        vec = cosine(query_vector, item_vector)
    else:
        vec = cosine(embed(query), embed(blob))
    type_w = memory_type_weight(item, fact_weight=fact_weight, chunk_weight=chunk_weight)
    return (0.45 * lexical + 0.55 * vec) * type_w


def mmr_select(
    candidates: list[tuple[MemoryItem, float]],
    embed,
    limit: int,
    lambda_: float = 0.7,
) -> list[MemoryItem]:
    if not candidates or limit <= 0:
        return []
    remaining = list(candidates)
    selected: list[MemoryItem] = []
    selected_vectors: list[list[float]] = []
    while remaining and len(selected) < limit:
        best_idx = -1
        best_score = -1.0
        for idx, (item, rel_score) in enumerate(remaining):
            vec = embed(item.text or "")
            if not selected_vectors:
                mmr = rel_score
            else:
                max_sim = max(cosine(vec, svec) for svec in selected_vectors)
                mmr = lambda_ * rel_score - (1.0 - lambda_) * max_sim
            if mmr > best_score:
                best_score = mmr
                best_idx = idx
        if best_idx < 0:
            break
        item, _ = remaining.pop(best_idx)
        selected.append(item)
        selected_vectors.append(embed(item.text or ""))
    return selected


def rrf_merge(rankings: list[list[MemoryItem]], k: int = 60) -> list[MemoryItem]:
    scores: dict[str, float] = {}
    order: dict[str, MemoryItem] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            mid = item.id.value
            order[mid] = item
            scores[mid] = scores.get(mid, 0.0) + 1.0 / (k + rank + 1)
    merged = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    return [order[mid] for mid, _ in merged]

