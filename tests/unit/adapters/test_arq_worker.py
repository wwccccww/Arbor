"""Regression guards for the ARQ worker entrypoints.

Each assertion here maps to a defect that either stopped ``arbor-worker`` from
booting or stopped it from running any job.
"""

from __future__ import annotations

import arq.cli
import pytest

from arbor.adapters.outbound.arq.cli import main
from arbor.adapters.outbound.arq.worker import WorkerSettings, _is_final_attempt


def test_worker_settings_expose_callable_jobs() -> None:
    assert isinstance(WorkerSettings, type)
    assert all(callable(fn) for fn in WorkerSettings.functions)
    assert "process_import_job" in [fn.__name__ for fn in WorkerSettings.functions]


def test_worker_entrypoint_hands_arq_the_settings_class(monkeypatch: pytest.MonkeyPatch) -> None:
    # arq 0.28 takes the settings class positionally. The legacy dotted-path
    # string raised TypeError, so the worker process exited immediately.
    captured: dict = {}

    def fake_run_worker(settings_cls, **kwargs) -> None:
        captured["settings_cls"] = settings_cls

    monkeypatch.setattr(arq.cli, "run_worker", fake_run_worker)
    main()

    assert isinstance(captured["settings_cls"], type)
    assert captured["settings_cls"] is WorkerSettings


def test_arq_runtimes_take_fixture_embedding_from_inmemory() -> None:
    # Importing FixtureEmbeddingClient from arbor.adapters.outbound.embedding
    # raised ImportError and aborted the worker before it registered.
    from arbor.adapters.outbound.arq import agent_runtime, import_runtime
    from arbor.adapters.outbound.inmemory import FixtureEmbeddingClient

    assert import_runtime.FixtureEmbeddingClient is FixtureEmbeddingClient
    assert agent_runtime.FixtureEmbeddingClient is FixtureEmbeddingClient


def test_demo_member_grant_id_is_typed() -> None:
    # A plain str made the duplicate-grant guard always true, and made
    # PgPersonaRepository.save fail on `grant.user_id.value`.
    from arbor.adapters.outbound.arq import agent_runtime, import_runtime
    from arbor.domain.shared.ids import UserId

    assert isinstance(import_runtime.MEMBER_ID, UserId)
    assert isinstance(agent_runtime.MEMBER_ID, UserId)


@pytest.mark.parametrize(
    ("ctx", "expected"),
    [
        ({"job_try": 1, "max_tries": 5}, False),
        ({"job_try": 4, "max_tries": 5}, False),
        ({"job_try": 5, "max_tries": 5}, True),
        ({"job_try": 6, "max_tries": 5}, True),
        ({}, True),
        (None, True),
        ({"job_try": "x", "max_tries": "y"}, True),
    ],
)
def test_final_attempt_detection(ctx: object, expected: bool) -> None:
    """Only the last ARQ attempt records a terminal status, so retries can recover."""
    assert _is_final_attempt(ctx) is expected
