import os

import pytest


pytestmark = pytest.mark.postgres


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="Postgres contract tests need DATABASE_URL")
def test_event_edge_check():
    pytest.skip("real pgvector adapter not implemented")
