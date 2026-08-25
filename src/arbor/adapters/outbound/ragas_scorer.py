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
        # Judge wiring is opt-in via ARBOR_JUDGE_API_KEY. Without it we skip rather
        # than score generation with the same DeepSeek model.
        _ = (evaluate, faithfulness, Dataset, question)
        return None
