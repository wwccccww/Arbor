import os

import pytest


pytestmark = pytest.mark.postgres


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="Postgres contract tests need DATABASE_URL")
def test_memory_tenant_filter():
    pytest.skip("real pgvector adapter not implemented")
