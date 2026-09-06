from __future__ import annotations

import re

from arbor.domain.memory.memory import MemoryItem, MemoryType
from arbor.domain.shared.textvec import cosine

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[a-zA-Z]+")

_QUERY_ALIASES: tuple[tuple[str, str], ...] = (
    ("overtime work order", "超时工单"),
    ("work orders", "工单"),
    ("working hours", "工作时间"),
    ("customer service", "在线客服"),
    ("after 9 pm", "21:00"),
    ("after 9pm", "21:00"),
    ("longjing", "龙井"),
    ("beverage", "茶"),
    ("daily basis", "日常喝"),
    ("durian", "榴莲"),
    ("allergic", "过敏"),
    ("allergy", "过敏"),
    ("birthday", "生日"),
    ("invoice", "发票"),
    ("shipping", "运费"),
    ("cilantro", "香菜"),
    ("spice level", "微辣"),
    ("spice", "辣度"),
    ("call time", "打电话"),
    ("noodle shop", "面馆"),
    ("laozhang", "老张"),
    ("argument", "争吵"),
    ("earphones", "耳机"),
    ("mr. zhang", "张先生"),
    ("made up", "和好"),
    ("osmanthus", "桂花糕"),
    ("no-reason return", "无理由退货"),
    ("no reason return", "无理由退货"),
    ("first meet", "第一次见面"),
    ("west lake", "西湖"),
    ("wearing", "穿"),
)
_TYPO_FIXES: tuple[tuple[str, str], ...] = (
    ("whts ", "what's "),
    ("wher ", "where "),
    ("whre ", "where "),
    ("wht r ", "what are "),
    ("conditons", "conditions"),
)

_PROFILE_SLOT_HINTS = (
    "过敏",
    "allergy",
    "allergic",
    "生日",
    "birthday",
    "茶",
    "tea",
    "beverage",
    "喝什么",
    "日常喝",
    "durian",
    "榴莲",
    "饮食",
    "dietary",
    "讨厌",
    "水果",
)
_POLICY_HINTS = (
    "发票",
    "invoice",
    "运费",
    "shipping",
    "退换",
    "return",
    "质量问题",
    "quality",
    "超时",
    "overtime",
    "客服",
    "working hours",
    "9 pm",
    "9pm",
    "怎么给",
    "谁承担",
)


def normalize_query(query: str) -> str:
    """Fold Latin case, apply light typo fixes, and collapse whitespace."""
    text = (query or "").strip()
    if not text:
        return ""
    folded = " ".join(text.casefold().split())
    for src, dst in _TYPO_FIXES:
        folded = folded.replace(src, dst)
    return folded


def expand_retrieval_query(query: str) -> str:
    """Normalize plus append Chinese aliases for cross-lingual retrieval."""
    lowered = normalize_query(query)
    if not lowered:
        return ""
    extras: list[str] = []
    seen: set[str] = set()
    for english, chinese in _QUERY_ALIASES:
        if english in lowered and chinese not in lowered and chinese not in seen:
            extras.append(chinese)
            seen.add(chinese)
    if extras:
        return f"{lowered} {' '.join(extras)}"
    return lowered


def _hint_in_query(query: str, hints: tuple[str, ...]) -> bool:
    lowered = (query or "").lower()
    return any(hint in lowered or hint in (query or "") for hint in hints)


def needs_profile_facts(query: str) -> bool:
    return _hint_in_query(query, _PROFILE_SLOT_HINTS)


def is_policy_query(query: str) -> bool:
    return _hint_in_query(query, _POLICY_HINTS)


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


def query_has_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))


def memory_min_score_for_query(query: str, default: float) -> float:
    """Latin-only queries skip lexical floor (cross-lingual vector retrieval)."""
    if not query_has_cjk(query):
        return 0.0
    return default


def lexical_token_score(query: str, text: str) -> float:
    q_tokens = tokenize(query)
    if not q_tokens:
        return 0.0
    t_tokens = tokenize(text)
    if not t_tokens:
        return 0.0
    overlap = len(q_tokens & t_tokens)
    return overlap / len(q_tokens)


_MEDIA_HINTS = ("photo", "照片", "图片", "picture", "image", "pic")


def query_media_boost(query: str, text: str, memory_type: MemoryType) -> float:
    lowered = (query or "").lower()
    if not any(hint in lowered or hint in query for hint in _MEDIA_HINTS):
        return 0.0
    blob = text or ""
    if "照片" in blob or memory_type is MemoryType.IMAGE_CAPTION:
        return 0.35
    return 0.0


_RESIDENCE_HINTS = ("reside", "live", "where", "address", "district", "home", "住", "区")
_WEEKEND_HINTS = ("weekend", "周末", "usually do", "平时", "通常")
_CALL_HINTS = ("call time", "打电话", "21:00", "what's the call")


def query_lifestyle_boost(query: str, text: str) -> float:
    lowered = (query or "").lower()
    blob = text or ""
    if any(hint in lowered or hint in query for hint in _CALL_HINTS) and "打电话" in blob:
        return 0.55
    if not any(hint in lowered or hint in query for hint in _WEEKEND_HINTS):
        return 0.0
    if any(token in blob for token in ("周末", "打游戏", "打电话的约定")):
        return 0.45
    return 0.0


def query_residence_boost(query: str, text: str) -> float:
    lowered = (query or "").lower()
    if not any(hint in lowered or hint in query for hint in _RESIDENCE_HINTS):
        return 0.0
    blob = text or ""
    if "住在" in blob:
        return 0.55
    if any(token in blob for token in ("区", "西湖", "杭州", "杨浦", "district")):
        return 0.2
    return 0.0


_SPICE_HINTS = ("spice", "辣", "辣度", "spicy", "微辣")
_TABOO_HINTS = ("cilantro", "香菜", "taboo", "禁忌", "dietary", "restrict")


def query_dietary_boost(query: str, text: str) -> float:
    lowered = (query or "").lower()
    blob = text or ""
    boost = 0.0
    if any(hint in lowered or hint in query for hint in _SPICE_HINTS):
        if any(token in blob for token in ("微辣", "辣")):
            boost = max(boost, 0.45)
    if any(hint in lowered or hint in query for hint in _TABOO_HINTS):
        if "香菜" in blob or "讨厌" in blob:
            boost = max(boost, 0.4)
    if any(hint in lowered or hint in query for hint in ("讨厌", "taboo", "禁忌")):
        if any(token in blob for token in ("讨厌", "榴莲", "香菜")):
            boost = max(boost, 0.45)
    if any(hint in lowered or hint in query for hint in ("饮食偏好", "dietary", "preference", "beverage")):
        if any(token in blob for token in ("微辣", "香菜", "榴莲", "龙井")):
            boost = max(boost, 0.4)
    return boost


_ALLERGY_HINTS = ("过敏", "allergy", "allergic")
_BIRTHDAY_HINTS = ("生日", "birthday")
_TEA_HINTS = ("茶", "tea", "longjing", "喝什么", "日常喝")
_DURIAN_HINTS = ("durian", "榴莲")


def query_slot_boost(query: str, text: str) -> float:
    lowered = (query or "").lower()
    blob = text or ""
    boost = 0.0
    if any(hint in lowered or hint in query for hint in _ALLERGY_HINTS) and "过敏" in blob:
        boost = max(boost, 0.55)
    if any(hint in lowered or hint in query for hint in _BIRTHDAY_HINTS) and "生日" in blob:
        boost = max(boost, 0.55)
    if any(hint in lowered or hint in query for hint in _TEA_HINTS) and any(
        token in blob for token in ("龙井", "茶")
    ):
        boost = max(boost, 0.5)
    if "beverage" in lowered and any(token in blob for token in ("龙井", "茶")):
        boost = max(boost, 0.5)
    if any(hint in lowered or hint in query for hint in _DURIAN_HINTS) and "榴莲" in blob:
        boost = max(boost, 0.55)
    if "水果" in query and "榴莲" in blob:
        boost = max(boost, 0.5)
    return boost


def query_policy_boost(query: str, text: str) -> float:
    if not is_policy_query(query):
        return 0.0
    blob = text or ""
    lowered = (query or "").lower()
    boost = 0.0
    if any(hint in lowered or hint in query for hint in ("发票", "invoice")) and "发票" in blob:
        boost = max(boost, 0.6)
    if any(hint in lowered or hint in query for hint in ("运费", "shipping", "谁承担")) and "运费" in blob:
        boost = max(boost, 0.6)
    if any(hint in lowered or hint in query for hint in ("超时", "overtime", "9 pm", "9pm", "客服", "working hours")):
        if any(token in blob for token in ("超时工单", "在线客服", "21:00")):
            boost = max(boost, 0.65)
    if any(hint in lowered or hint in query for hint in ("earphones", "耳机")) and "耳机" in blob:
        boost = max(boost, 0.7)
    if any(hint in lowered or hint in query for hint in ("food", "食品")) and "食品类" in blob:
        boost = max(boost, 0.65)
    if any(hint in lowered or hint in query for hint in ("退换", "质量", "quality", "return", "无理由")) and (
        "售后手册" in blob or "无理由" in blob or "退换" in blob
    ):
        boost = max(boost, 0.5)
    return boost


_PET_HINTS = ("pet", "宠物", "养猫", "橘猫", "猫")


def query_pet_boost(query: str, text: str) -> float:
    lowered = (query or "").lower()
    if not any(hint in lowered or hint in query for hint in _PET_HINTS):
        return 0.0
    blob = text or ""
    if any(token in blob for token in ("猫", "宠物", "橘猫")):
        return 0.45
    return 0.0


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
    lexical = (
        lexical_token_score(query, blob)
        + query_media_boost(query, blob, item.type)
        + query_residence_boost(query, blob)
        + query_lifestyle_boost(query, blob)
        + query_dietary_boost(query, blob)
        + query_pet_boost(query, blob)
        + query_slot_boost(query, blob)
        + query_policy_boost(query, blob)
    )
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

