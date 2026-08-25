from arbor.adapters.outbound.inmemory import (
    InMemoryInboxRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    ScriptedReasoner,
    SeqIdGenerator,
)
from arbor.application.memory.commands import ProcessImportJob
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def test_process_import_uses_reasoner_extraction():
    stores = InMemoryStores()
    personas = InMemoryPersonaRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona_id = PersonaId("0a000000-0000-4000-a000-000000000010")
    process = ProcessImportJob(
        personas=personas,
        inbox=inbox,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
        reasoner=ScriptedReasoner(proposed_fact="林夏讨厌香菜"),
    )
    created = process(
        tenant_id=tenant,
        user_id=UserId("0a000000-0000-4000-a000-000000000002"),
        persona_id=persona_id,
        filename="notes.txt",
        data="她从来不吃香菜".encode(),
        capabilities=list(Capability),
    )
    assert created == 1
    pending = inbox.list_pending(tenant, persona_id)
    assert pending[0].payload["text"] == "林夏讨厌香菜"
