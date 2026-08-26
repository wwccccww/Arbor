"""Build import-job runtime for API and ARQ worker."""

from __future__ import annotations

from dataclasses import dataclass

from arbor.adapters.inbound.eval_runner import ROOT, load_world
from arbor.adapters.outbound.embedding import FixtureEmbeddingClient, embedding_client_from_env
from arbor.adapters.outbound.inmemory import (
    InMemoryInboxRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    ScriptedReasoner,
    SeqIdGenerator,
)
from arbor.adapters.outbound.multimodal.factory import parse_media_bytes
from arbor.adapters.outbound.object_storage import build_object_storage
from arbor.adapters.outbound.postgres.import_jobs import (
    InMemoryImportJobRepository,
    PgImportJobRepository,
)
from arbor.application.memory.import_jobs import RunImportJob
from arbor.application.memory.media_to_inbox import MediaToInbox
from arbor.application.memory.process_import import ProcessImportJob
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId

LINXIA_ID = "0a000000-0000-4000-a000-000000000010"
MEMBER_ID = "0a000000-0000-4000-a000-000000000003"


@dataclass
class ImportJobRuntime:
    import_jobs: object
    run_import: RunImportJob


def build_import_job_runtime(
    *,
    database_url: str | None = None,
    embed=None,
    reasoner=None,
) -> ImportJobRuntime:
    if embed is not None:
        resolved_embed = embed
    elif database_url:
        resolved_embed = embedding_client_from_env()
    else:
        resolved_embed = FixtureEmbeddingClient()

    if database_url:
        from arbor.adapters.outbound.postgres import PostgresSession

        session = PostgresSession.connect(database_url, embed=resolved_embed)
        session.migrate()
        session.seed_demo_world_if_empty()
        personas = session.personas
        inbox = session.inbox
        import_jobs = PgImportJobRepository(session.conn)
        storage = build_object_storage(session=session, stores=None)
        linxia = personas.get(TenantId("0a000000-0000-4000-a000-000000000001"), PersonaId(LINXIA_ID))
        if linxia is not None and not any(g.user_id == MEMBER_ID for g in linxia.grants):
            linxia.grants.append(Grant(user_id=MEMBER_ID, capabilities=[Capability.CHAT]))
            personas.save(linxia)
    else:
        stores = InMemoryStores()
        load_world(ROOT / "eval" / "fixtures" / "suite-v1" / "world.json", stores)
        linxia = stores.personas[LINXIA_ID]
        if not any(g.user_id == MEMBER_ID for g in linxia.grants):
            linxia.grants.append(Grant(user_id=MEMBER_ID, capabilities=[Capability.CHAT]))
        personas = InMemoryPersonaRepository(stores)
        inbox = InMemoryInboxRepository(stores)
        import_jobs = InMemoryImportJobRepository()
        storage = build_object_storage(session=None, stores=stores)

    ids = SeqIdGenerator()
    media_to_inbox = MediaToInbox(
        personas=personas,
        inbox=inbox,
        ids=ids,
        auth=AuthorizationPolicy(),
        reasoner=reasoner or ScriptedReasoner(),
        parse_media=parse_media_bytes,
    )
    process_import = ProcessImportJob(media_to_inbox=media_to_inbox)
    run_import = RunImportJob(
        import_jobs=import_jobs,
        storage=storage,
        process_import=process_import,
    )
    return ImportJobRuntime(import_jobs=import_jobs, run_import=run_import)
