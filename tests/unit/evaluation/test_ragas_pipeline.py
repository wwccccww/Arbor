from __future__ import annotations

import json

from arbor.adapters.outbound.inmemory import ScriptedLLM
from arbor.adapters.outbound.ragas_scorer import RAGAS_METRIC_NAMES, FakeRagasMetricsScorer, RagasSample
from arbor.application.evaluation.ragas_pipeline import (
    RagasRunStore,
    _eval_thread_id,
    _record_to_sample,
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


def test_eval_thread_id_is_per_case():
    case = {"id": "ragas-llm-001"}
    assert _eval_thread_id(case).value == "eval-ragas-llm-001"


def test_parallel_generation_workers(tmp_path):
    run_dir = tmp_path / "parallel"
    run_ragas_official_generate(
        strategy="layered_tree",
        llm=ScriptedLLM(),
        backend="memory",
        embed="fixture",
        case_limit=4,
        run_dir=run_dir,
        batch_size=2,
        gen_workers=2,
        resume=False,
    )
    rows = RagasRunStore(run_dir).load_all_generations()
    assert len(rows) == 4


def test_default_run_dir_uses_date():
    assert default_run_dir("custom-id").name == "custom-id"


def _generation_record(**overrides):
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
    record.update(overrides)
    record["fingerprint"] = generation_fingerprint(record)
    return record


def test_record_to_sample_skips_empty_answer():
    assert _record_to_sample(_generation_record(answer="", text="")) is None
    assert _record_to_sample(_generation_record(leaked=True)) is None
    assert _record_to_sample(_generation_record(behavior="refuse")) is None
    sample = _record_to_sample(_generation_record())
    assert sample is not None
    assert sample.answer == "a"


def test_fake_scorer_skips_none_and_empty_samples():
    scorer = FakeRagasMetricsScorer()
    scored = scorer.score_batch(
        [
            None,
            RagasSample(question="q", answer="", contexts=["c"]),
            RagasSample(question="q", answer="a", contexts=["c"]),
        ]
    )
    assert scored[0]["faithfulness"] is None
    assert scored[1]["faithfulness"] is None
    assert scored[2]["faithfulness"] == 1.0
    assert len(scored) == 3


def test_score_skips_unscorable_records_without_none_samples(tmp_path):
    run_dir = tmp_path / "run-unscorable"
    store = RagasRunStore(run_dir, batch_size=10)
    store.ensure_dirs()
    good = _generation_record(case_id="ragas-llm-001")
    empty = _generation_record(case_id="ragas-llm-007", answer="", text="")
    store.write_jsonl(store.batch_path("generations", 0), [good, empty])

    class RecordingScorer:
        def __init__(self):
            self.seen: list = []

        def score_batch(self, samples, *, metric_names=None):
            self.seen.extend(samples)
            assert all(sample is not None for sample in samples)
            assert all((sample.answer or "").strip() for sample in samples)
            return FakeRagasMetricsScorer().score_batch(samples, metric_names=metric_names)

    scorer = RecordingScorer()
    run_ragas_official_score(run_dir=run_dir, scorer=scorer, batch_size=10, resume=True)
    assert len(scorer.seen) == 1
    scores = store.read_jsonl(store.batch_path("scores", 0))
    by_id = {row["case_id"]: row["metrics"] for row in scores}
    assert by_id["ragas-llm-001"]["faithfulness"] == 1.0
    assert by_id["ragas-llm-007"]["faithfulness"] is None


def test_generate_case_worker_retries_unavailable(monkeypatch):
    from arbor.adapters.outbound.embedding import EmbeddingUnavailable
    from arbor.application.evaluation import ragas_pipeline as mod

    class _Sess:
        pass

    calls = {"n": 0}

    def fake_generate(_session, case):
        calls["n"] += 1
        if calls["n"] == 1:
            raise EmbeddingUnavailable("handshake")
        return {"case_id": case["id"], "answer": "ok"}

    mod._worker_local.session = _Sess()
    monkeypatch.setattr(mod, "_generate_case", fake_generate)
    monkeypatch.setattr(mod, "_public_generation_record", lambda rec: rec)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    out = mod._generate_case_worker({"id": "ragas-llm-001"})
    assert out["answer"] == "ok"
    assert calls["n"] == 2
