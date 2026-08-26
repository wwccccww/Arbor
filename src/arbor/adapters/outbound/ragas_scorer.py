"""RAGAS faithfulness adapter. Judge must not be the generator."""

from __future__ import annotations

from arbor.env import judge_api_key


class RagasFaithfulnessScorer:
    def score(self, question: str, answer: str, contexts: list[str]) -> float | None:
        if not judge_api_key():
            return None
        if not answer.strip() or not contexts:
            return None
        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import faithfulness
        except Exception:
            return None
        try:
            dataset = Dataset.from_dict(
                {
                    "question": [question],
                    "answer": [answer],
                    "contexts": [contexts],
                }
            )
            result = evaluate(dataset, metrics=[faithfulness])
            row = result.to_pandas().iloc[0]
            value = row.get("faithfulness")
            if value is None:
                return None
            return float(value)
        except Exception:
            return None
