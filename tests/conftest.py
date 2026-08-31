from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _allow_plan_script_in_tests(monkeypatch):
    monkeypatch.setenv("ARBOR_ALLOW_PLAN_SCRIPT", "1")


@pytest.fixture
def domain_cases():
    return yaml.safe_load((ROOT / "tests/examples/domain.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def application_cases():
    return yaml.safe_load((ROOT / "tests/examples/application.yaml").read_text(encoding="utf-8"))
