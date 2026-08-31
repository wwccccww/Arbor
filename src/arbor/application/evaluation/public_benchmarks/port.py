from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PublicBenchmarkCase:
    id: str
    benchmark: str
    split: str
    input: dict
    expected: dict
    metadata: dict = field(default_factory=dict)


@dataclass
class PublicBenchmarkResult:
    case_id: str
    ok: bool
    scores: dict[str, float]
    actual: dict
    latency_ms: float = 0.0
    tokens: int = 0
    cost_micros: int = 0
    security_violations: list[str] = field(default_factory=list)
    detail: str = ""
