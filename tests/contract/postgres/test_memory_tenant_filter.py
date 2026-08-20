from arbor.domain.shared.ids import PersonaId, TenantId
from arbor.domain.shared.textvec import fixture_embed


def test_memory_tenant_filter(pg):
    hits = pg.vectors.search(
        tenant_id=TenantId("0b000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0b000000-0000-4000-a000-000000000010"),
        query_vector=fixture_embed("林夏讨厌香菜，点餐不能放香菜。"),
        k=5,
    )
    assert all(h[0].id.value != "0a000000-0000-4000-a000-000000000302" for h in hits)
    assert all(h[0].tenant_id.value == "0b000000-0000-4000-a000-000000000001" for h in hits)
