from __future__ import annotations

import json

from arbor.adapters.inbound.eval_runner import ROOT, run_ragas_official_generation, run_suite
from arbor.adapters.outbound.ragas_scorer import FakeRagasMetricsScorer
from arbor.application.evaluation.generation import RAGAS_METRIC_KEYS, aggregate_generation
from arbor.paths import repo_root


def test_ragas_official_manifest_exists():
    manifest = repo_root() / "eval" / "public" / "manifests" / "ragas-official.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["benchmark_id"] == "ragas-official"
    assert data["n_cases"] == 100
    assert "faithfulness" in data["metrics"]


def test_ragas_official_fixture_has_100_cases():
    cases = json.loads(
        (ROOT / "eval/fixtures/suite-ragas-official/cases.json").read_text(encoding="utf-8")
    )
    assert len(cases) == 100
    assert all(case.get("reference") for case in cases)
    assert all(case.get("reference_contexts") for case in cases)


def test_ragas_official_retrieval_no_cross_tenant_leak():
    report = run_suite(
        suite_dir=ROOT / "eval/fixtures/suite-ragas-official",
        strategy="layered_tree",
        backend="memory",
    )
    assert report["metrics"]["tenant_leak_count"] == 0
    assert report["metrics"]["n_cases"] == 100


def test_fake_ragas_metrics_scorer_batch():
    from arbor.adapters.outbound.ragas_scorer import RagasSample

    scorer = FakeRagasMetricsScorer()
    scored = scorer.score_batch(
        [
            RagasSample(
                question="林夏住哪？",
                answer="杭州西湖区。",
                contexts=["林夏住在杭州西湖区。"],
                ground_truth="林夏住在杭州西湖区。",
            )
        ]
    )
    assert scored[0]["faithfulness"] == 1.0
    assert scored[0]["answer_correctness"] == 1.0


def test_aggregate_generation_includes_ragas_metric_keys():
    rows = [
        {
            "id": "x",
            "behavior": "answer",
            "skill": "episode_detail",
            "citation_subset": True,
            "text_leak": False,
            "retrieval_leak": False,
            "leaked": False,
            "ragas_faithfulness": 0.9,
            "ragas_context_recall": 0.8,
            "ragas_context_precision": 0.85,
            "ragas_answer_relevancy": 0.95,
            "ragas_answer_correctness": 0.88,
        }
    ]
    metrics = aggregate_generation(rows)
    for key in RAGAS_METRIC_KEYS:
        assert metrics[key] is not None
    assert metrics["ragas_skipped"] is False


def test_ragas_official_generation_smoke_with_fake_scorer():
    from arbor.adapters.outbound.inmemory import ScriptedLLM

    report = run_ragas_official_generation(
        llm=ScriptedLLM(),
        scorer=FakeRagasMetricsScorer(),
        backend="memory",
        case_limit=2,
    )
    assert report["benchmark_id"] == "ragas-official"
    assert report["suite_version"] == "ragas-official-v1"
    assert len(report["cases"]) == 2
    metrics = report["metrics"]
    assert metrics["citation_subset_rate"] == 1.0
    assert metrics["ragas_faithfulness"] == 1.0
    assert metrics["ragas_answer_correctness"] == 1.0
