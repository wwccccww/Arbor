import os

import pytest

from arbor.adapters.inbound.eval_runner import ROOT, run_all_strategies, run_suite
from arbor.env import database_url

pytestmark = pytest.mark.postgres


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres eval needs DATABASE_URL")
def test_suite_v1_pgvector_no_cross_tenant_hit():
    payload = run_all_strategies(ROOT / "eval/fixtures/suite-v1", backend="postgres")
    assert payload["backend"] == "postgres"
    for name, row in payload["strategies"].items():
        assert row["tenant_leak_count"] == 0, name
        assert row["persona_leak_rate"] == 0, name
        assert row["superseded_in_topk"] == 0, name
    layered = payload["strategies"]["layered_tree"]
    assert layered["identity_consistency"] == 1.0
    assert layered["recall_at_5"] >= 0.7


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres eval needs DATABASE_URL")
def test_suite_v1_pgvector_layered_tree_profile_layer():
    report = run_suite(
        suite_dir=ROOT / "eval/fixtures/suite-v1",
        strategy="layered_tree",
        backend="postgres",
    )
    assert report["backend"] == "postgres"
    assert report["metrics"]["profile_miss_count"] == 0
    assert report["p0_tenant_leak_zero"] is True
