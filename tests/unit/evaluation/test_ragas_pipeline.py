from __future__ import annotations

import json

from arbor.adapters.outbound.inmemory import ScriptedLLM
from arbor.adapters.outbound.ragas_scorer import RAGAS_METRIC_NAMES, FakeRagasMetricsScorer
from arbor.application.evaluation.ragas_pipeline import (
    RagasRunStore,
    build_report_from_artifacts,
    default_run_dir,
    generation_fingerprint,
    run_ragas_official_generate,
    run_ragas_official_pipeline,
    run_ragas_official_score,
)


def test_generation_fingerprint_stable():
    record = {
        "case_id": "ragas-llm-001",
        "query": "q",
        "reference": "r",
        "contexts": ["c"],
        "answer": "a",
        "generator": "deepseek-chat",
        "strategy": "layered_tree",
        "embed": "fixture",
    }
    first = generation_fingerprint(record)
    second = generation_fingerprint(record)
    assert first == second
    record["answer"] = "changed"
    assert generation_fingerprint(record) != first


def test_run_store_batch_paths(tmp_path):
    store = RagasRunStore(tmp_path, batch_size=10)
    store.ensure_dirs()
    assert store.batch_path("generations", 0).name == "batch-000.jsonl"
    assert store.batch_path("scores", 3).name == "batch-003.jsonl"


def test_metric_cache_roundtrip(tmp_path):
    store = RagasRunStore(tmp_path)
    store.save_metric_cache("case-1", "faithfulness", 0.9, "fp123")
    assert store.load_metric_cache("case-1", "faithfulness", "fp123") == 0.9
    assert store.load_metric_cache("case-1", "faithfulness", "other") is None


def test_pipeline_generate_score_resume(tmp_path):
    run_dir = tmp_path / "run-a"
    run_ragas_official_generate(
        strategy="layered_tree",
        llm=ScriptedLLM(),
        backend="memory",
        embed="fixture",
        case_limit=3,
        run_dir=run_dir,
        batch_size=2,
        resume=True,
    )
    gen_files = list((run_dir / "generations").glob("batch-*.jsonl"))
    assert len(gen_files) == 2
    rows = []
    for path in gen_files:
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    assert len(rows) == 3
    assert all(row.get("fingerprint") for row in rows)

    run_ragas_official_score(
        run_dir=run_dir,
        scorer=FakeRagasMetricsScorer(),
        batch_size=2,
        resume=True,
    )
    score_files = list((run_dir / "scores").glob("batch-*.jsonl"))
    assert len(score_files) == 2

    # Resume should skip completed batches.
    run_ragas_official_generate(
        strategy="layered_tree",
        llm=ScriptedLLM(),
        backend="memory",
        embed="fixture",
        case_limit=3,
        run_dir=run_dir,
        batch_size=2,
        resume=True,
    )
    run_ragas_official_score(
        run_dir=run_dir,
        scorer=FakeRagasMetricsScorer(),
        batch_size=2,
        resume=True,
    )

    report = build_report_from_artifacts(
        run_dir=run_dir,
        strategy="layered_tree",
        backend="memory",
        embed_label="fixture",
    )
    assert report["n_cases"] == 3
    assert report["metrics"]["ragas_faithfulness"] == 1.0
    assert report["benchmark_id"] == "ragas-official"


def test_pipeline_score_only_uses_cache(tmp_path):
    run_dir = tmp_path / "run-b"
    store = RagasRunStore(run_dir, batch_size=10)
    store.ensure_dirs()
    record = {
        "case_id": "ragas-llm-001",
        "query": "q",
        "reference": "r",
        "reference_contexts": ["rc"],
        "answer": "a",
        "text": "a",
        "contexts": ["c"],
        "behavior": "answer",
        "skill": "episode_detail",
        "injected_memory_ids": [],
        "citations": [],
        "leaked": False,
        "strategy": "layered_tree",
        "embed": "fixture",
        "generator": "deepseek-chat",
    }
    record["fingerprint"] = generation_fingerprint(record)
    store.write_jsonl(store.batch_path("generations", 0), [record])
    for metric in RAGAS_METRIC_NAMES:
        store.save_metric_cache("ragas-llm-001", metric, 0.5, record["fingerprint"])

    class FailingScorer:
        def score_batch(self, samples, *, metric_names=None):
            raise AssertionError("should not call scorer when cache is warm")

    run_ragas_official_score(run_dir=run_dir, scorer=FailingScorer(), batch_size=10, resume=True)
    scores = store.read_jsonl(store.batch_path("scores", 0))
    assert scores[0]["metrics"]["faithfulness"] == 0.5


def test_run_ragas_official_pipeline_in_memory_fast_path():
    report = run_ragas_official_pipeline(
        llm=ScriptedLLM(),
        scorer=FakeRagasMetricsScorer(),
        backend="memory",
        embed="fixture",
        case_limit=2,
        use_disk=False,
    )
    assert report["n_cases"] == 2
    assert report["metrics"]["ragas_faithfulness"] == 1.0


def test_default_run_dir_uses_date():
    assert default_run_dir("custom-id").name == "custom-id"
