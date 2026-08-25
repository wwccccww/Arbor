from __future__ import annotations

import os

import pytest

from arbor.env import database_url

pytestmark = pytest.mark.postgres


@pytest.fixture
def pg():
    url = database_url() or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("Postgres contract tests need DATABASE_URL")
    from arbor.adapters.outbound.postgres import PostgresSession

    session = PostgresSession.connect(url)
    session.reset()
    session.load_mini_world()
    try:
        yield session
    finally:
        session.close()
