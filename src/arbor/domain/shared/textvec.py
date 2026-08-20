from __future__ import annotations

import hashlib
import math


def fixture_embed(text: str, dim: int = 64) -> list[float]:
    vec = [0.0] * dim
    if not text:
        return vec
    data = text.encode("utf-8")
    for i in range(max(len(data) - 1, 1)):
        chunk = data[i : i + 2] if len(data) > 1 else data
        digest = hashlib.md5(chunk).digest()
        vec[digest[0] % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))
