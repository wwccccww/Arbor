from arbor.adapters.inbound.eval_runner import ROOT, run_all_strategies, run_suite


def test_suite_v1_layered_tree_tenant_leak_zero():
    report = run_suite(suite_dir=ROOT / "eval/fixtures/suite-v1", strategy="layered_tree")
    assert report["metrics"]["tenant_leak_count"] == 0
    assert report["p0_tenant_leak_zero"] is True
    assert report["metrics"]["persona_leak_rate"] == 0
    assert report["metrics"]["superseded_in_topk"] == 0


def test_suite_v1_layered_tree_identity_and_profile_layer():
    report = run_suite(suite_dir=ROOT / "eval/fixtures/suite-v1", strategy="layered_tree")
    assert report["metrics"]["identity_consistency"] == 1.0
    assert report["metrics"]["profile_miss_count"] == 0
    assert report["metrics"]["recall_at_5"] >= 0.7


def test_suite_v1_all_strategies_no_cross_tenant_hit():
    payload = run_all_strategies(ROOT / "eval/fixtures/suite-v1")
    for name, row in payload["strategies"].items():
        assert row["tenant_leak_count"] == 0, name


def test_openapi_parses():
    import yaml

    path = ROOT / "docs/openapi.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "paths" in data
    required = data["components"]["schemas"]["Error"]["properties"]["error"]["required"]
    assert "code" in required
