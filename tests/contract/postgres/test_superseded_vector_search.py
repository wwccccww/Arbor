"""P0: superseded memories must not appear in ANN search."""

from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId
from arbor.domain.shared.textvec import fixture_embed

OLD_CAT = MemoryId("0a000000-0000-4000-a000-000000000307")
ACTIVE_CAT = MemoryId("0a000000-0000-4000-a000-000000000308")
TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


def test_superseded_memory_not_in_vector_search(pg):
    hits = pg.vectors.search(
        tenant_id=TENANT,
        persona_id=LINXIA,
        query_vector=fixture_embed("林夏喜欢猫想养宠物"),
        k=8,
    )
    ids = {item.id for item, _score in hits}
    assert OLD_CAT not in ids
    assert ACTIVE_CAT in ids
