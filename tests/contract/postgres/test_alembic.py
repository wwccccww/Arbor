import os

import pytest

from arbor.domain.shared.ids import PersonaId, TenantId
from arbor.domain.shared.textvec import fixture_embed
from arbor.env import database_url


pytestmark = pytest.mark.postgres


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres Alembic tests need DATABASE_URL")
def test_migrate_is_idempotent_and_keeps_rows(pg):
    before = pg.conn.execute("SELECT COUNT(*) AS n FROM memory_items").fetchone()["n"]
    assert before > 0
    pg.migrate()
    after = pg.conn.execute("SELECT COUNT(*) AS n FROM memory_items").fetchone()["n"]
    assert after == before
    hits = pg.vectors.search(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        query_vector=fixture_embed("林夏讨厌香菜，点餐不能放香菜。"),
        k=5,
    )
    assert any(h[0].id.value == "0a000000-0000-4000-a000-000000000302" for h in hits)


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres Alembic tests need DATABASE_URL")
def test_create_app_does_not_wipe_existing_tenants(pg):
    from apps.api.main import create_app

    marker = "c0000000-0000-4000-a000-000000000099"
    pg.conn.execute(
        "INSERT INTO tenants (id, name) VALUES (%s::uuid, %s) ON CONFLICT (id) DO NOTHING",
        (marker, "keep-me"),
    )
    create_app(database_url=database_url() or os.environ["DATABASE_URL"])
    row = pg.conn.execute("SELECT name FROM tenants WHERE id = %s::uuid", (marker,)).fetchone()
    assert row is not None
    assert row["name"] == "keep-me"
