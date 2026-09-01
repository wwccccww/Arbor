"""RAGAS faithfulness and full-metric adapters. Judge must not be the generator."""

from __future__ import annotations

from dataclasses import dataclass, field

from arbor.env import judge_api_key

RAGAS_METRIC_NAMES: tuple[str, ...] = (
    "faithfulness",
    "context_recall",
    "context_precision",
    "answer_relevancy",
    "answer_correctness",
)


@dataclass
class RagasSample:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str = ""
    reference_contexts: list[str] = field(default_factory=list)


def _load_ragas_metrics():
    from ragas.metrics import (
        answer_correctness,
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    return [
        faithfulness,
        context_recall,
        context_precision,
        answer_relevancy,
        answer_correctness,
    ]


class RagasFaithfulnessScorer:
    def score(self, question: str, answer: str, contexts: list[str]) -> float | None:
        batch = RagasMetricsScorer().score_batch(
            [RagasSample(question=question, answer=answer, contexts=contexts)]
        )
        if not batch:
            return None
        return batch[0].get("faithfulness")


class RagasMetricsScorer:
    """Batch RAGAS evaluate for Route A official generation suite."""

    def score_batch(self, samples: list[RagasSample]) -> list[dict[str, float | None]]:
        empty = [{name: None for name in RAGAS_METRIC_NAMES} for _ in samples]
        if not judge_api_key() or not samples:
            return empty
        usable = [
            sample
            for sample in samples
            if (sample.answer or "").strip() and sample.contexts and (sample.question or "").strip()
        ]
        if not usable:
            return empty
        try:
            from datasets import Dataset
            from ragas import evaluate
        except Exception:
            return empty
        try:
            metrics = _load_ragas_metrics()
        except Exception:
            return empty
        try:
            dataset = Dataset.from_dict(
                {
                    "question": [sample.question for sample in usable],
                    "answer": [sample.answer for sample in usable],
                    "contexts": [list(sample.contexts) for sample in usable],
                    "ground_truth": [sample.ground_truth or sample.answer for sample in usable],
                    "reference": [sample.ground_truth or sample.answer for sample in usable],
                    "reference_contexts": [
                        list(sample.reference_contexts or sample.contexts) for sample in usable
                    ],
                }
            )
            result = evaluate(dataset, metrics=metrics)
            frame = result.to_pandas()
        except Exception:
            return empty
        scored: list[dict[str, float | None]] = []
        usable_idx = 0
        for sample in samples:
            if not (
                (sample.answer or "").strip()
                and sample.contexts
                and (sample.question or "").strip()
            ):
                scored.append({name: None for name in RAGAS_METRIC_NAMES})
                continue
            row = frame.iloc[usable_idx]
            usable_idx += 1
            item: dict[str, float | None] = {}
            for name in RAGAS_METRIC_NAMES:
                value = row.get(name)
                item[name] = None if value is None else float(value)
            scored.append(item)
        return scored


class FakeRagasMetricsScorer:
    """Test double returning perfect scores without ragas SDK."""

    def score_batch(self, samples: list[RagasSample]) -> list[dict[str, float | None]]:
        perfect = {name: 1.0 for name in RAGAS_METRIC_NAMES}
        return [dict(perfect) if (s.answer or "").strip() and s.contexts else {n: None for n in RAGAS_METRIC_NAMES} for s in samples]
