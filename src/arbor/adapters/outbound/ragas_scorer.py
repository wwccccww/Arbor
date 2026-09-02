"""RAGAS faithfulness and full-metric adapters. Judge must not be the generator."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from arbor.env import judge_api_key, judge_base_url, judge_embedding_model, judge_model, load_dotenv

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


def _siliconflow_is_finished(response) -> bool:
    """SiliconFlow/OpenAI-compatible hosts may return finish_reason=length."""
    allowed = {"stop", "STOP", "MAX_TOKENS", "eos_token", "length"}
    for generation in response.flatten():
        resp = generation.generations[0][0]
        finish = None
        if resp.generation_info is not None:
            finish = resp.generation_info.get("finish_reason")
        elif getattr(resp, "message", None) is not None:
            finish = resp.message.response_metadata.get("finish_reason")
        if finish is not None and finish not in allowed:
            return False
    return True


def _build_ragas_llm_and_embeddings():
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.embeddings.base import LangchainEmbeddingsWrapper
    from ragas.llms.base import LangchainLLMWrapper

    key = judge_api_key()
    base = judge_base_url()
    load_dotenv()
    max_tokens = int(os.environ.get("ARBOR_JUDGE_MAX_TOKENS", "4096"))
    chat = ChatOpenAI(
        model=judge_model(),
        api_key=key,
        base_url=base,
        temperature=0,
        max_retries=5,
        timeout=300,
        max_tokens=max_tokens,
    )
    llm = LangchainLLMWrapper(chat, is_finished_parser=_siliconflow_is_finished)
    embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model=judge_embedding_model(),
            api_key=key,
            base_url=base,
            max_retries=5,
            timeout=120,
        )
    )
    return llm, embeddings


def _judge_run_config():
    import os

    from ragas.run_config import RunConfig

    load_dotenv()
    workers = int(os.environ.get("ARBOR_JUDGE_MAX_WORKERS", "2"))
    timeout = int(os.environ.get("ARBOR_JUDGE_TIMEOUT", "300"))
    return RunConfig(max_workers=workers, timeout=timeout, max_retries=10, max_wait=90)


def _metric_value(raw) -> float | None:
    import math

    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value):
        return None
    return value


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
            llm, embeddings = _build_ragas_llm_and_embeddings()
            result = evaluate(
                dataset,
                metrics=metrics,
                llm=llm,
                embeddings=embeddings,
                run_config=_judge_run_config(),
            )
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
                item[name] = _metric_value(value)
            scored.append(item)
        return scored


class FakeRagasMetricsScorer:
    """Test double returning perfect scores without ragas SDK."""

    def score_batch(self, samples: list[RagasSample]) -> list[dict[str, float | None]]:
        perfect = {name: 1.0 for name in RAGAS_METRIC_NAMES}
        return [dict(perfect) if (s.answer or "").strip() and s.contexts else {n: None for n in RAGAS_METRIC_NAMES} for s in samples]
