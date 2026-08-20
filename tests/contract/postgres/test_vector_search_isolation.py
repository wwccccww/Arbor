import inspect

import pytest

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId
from arbor.domain.shared.textvec import fixture_embed


def test_vector_search_isolation(pg):
    cat = pg.vectors.search(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        query_vector=fixture_embed("林夏喜欢猫想养宠物"),
        k=5,
    )
    assert all(h[0].id.value != "0a000000-0000-4000-a000-000000000307" for h in cat)

    sig = inspect.signature(pg.vectors.search)
    assert sig.parameters["tenant_id"].default is inspect.Parameter.empty
    with pytest.raises(DomainError) as missing:
        pg.vectors.search(
            tenant_id=None,  # type: ignore[arg-type]
            persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
            query_vector=[0.0] * 64,
            k=5,
        )
    assert missing.value.code == "VALIDATION_ERROR"

    mid = MemoryId("0a000000-0000-4000-a000-000000000305")
    pg.memories.delete(TenantId("0a000000-0000-4000-a000-000000000001"), mid)
    after = pg.vectors.search(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        query_vector=fixture_embed("每周日晚上打电话"),
        k=5,
    )
    assert all(h[0].id != mid for h in after)
