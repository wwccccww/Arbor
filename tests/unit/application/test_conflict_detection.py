from arbor.application.memory.conflict_detection import (
    enrich_inbox_extract,
    find_conflicting_memory,
    texts_conflict,
)
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
PERSONA = PersonaId("0a000000-0000-4000-a000-000000000010")
CILANTRO = MemoryId("0a000000-0000-4000-a000-000000000302")


def _fact(mid: str, text: str) -> MemoryItem:
    return MemoryItem(
        id=MemoryId(mid),
        tenant_id=TENANT,
        persona_id=PERSONA,
        text=text,
        type=MemoryType.FACT,
        status=MemoryStatus.ACTIVE,
    )


def test_texts_conflict_polarity_with_shared_topic():
    assert texts_conflict("林夏其实可以接受香菜", "林夏讨厌香菜，点餐不能放香菜。")


def test_texts_conflict_irrelevant_polarity_is_false():
    assert not texts_conflict("林夏喜欢猫", "林夏讨厌香菜")


def test_find_conflicting_memory_links_cilantro():
    memories = [_fact(CILANTRO.value, "林夏讨厌香菜，点餐不能放香菜。")]
    found = find_conflicting_memory("林夏其实可以接受香菜", memories)
    assert found == CILANTRO


def test_enrich_inbox_extract_from_heuristic():
    extracted = enrich_inbox_extract(
        {"kind": "fact", "text": "林夏其实可以接受香菜"},
        [_fact(CILANTRO.value, "林夏讨厌香菜")],
    )
    assert extracted["kind"] == "conflict"
    assert extracted["conflicts_with"] == CILANTRO.value


def test_enrich_inbox_extract_keeps_reasoner_conflicts_with():
    extracted = enrich_inbox_extract(
        {
            "kind": "conflict",
            "text": "林夏对猫毛过敏",
            "conflicts_with": "0a000000-0000-4000-a000-000000000307",
        },
        [_fact("0a000000-0000-4000-a000-000000000307", "林夏很喜欢猫")],
    )
    assert extracted["conflicts_with"] == "0a000000-0000-4000-a000-000000000307"
