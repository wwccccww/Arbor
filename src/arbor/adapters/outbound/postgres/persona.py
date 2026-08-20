from __future__ import annotations

from psycopg.types.json import Jsonb

from arbor.adapters.outbound.postgres.mapping import grant_from_row, persona_from_row
from arbor.domain.persona.authorization import Capability, Persona
from arbor.domain.shared.ids import PersonaId, TenantId


class PgPersonaRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def get(self, tenant_id: TenantId, persona_id: PersonaId) -> Persona | None:
        row = self.conn.execute(
            """
            SELECT id, tenant_id, skin, display_name, one_liner, personality, taboos, relationships
            FROM personas
            WHERE id = %s::uuid AND tenant_id = %s::uuid
            """,
            (persona_id.value, tenant_id.value),
        ).fetchone()
        if row is None:
            return None
        grants = [
            grant_from_row(g)
            for g in self.conn.execute(
                """
                SELECT user_id, capabilities
                FROM persona_grants
                WHERE persona_id = %s::uuid AND tenant_id = %s::uuid
                """,
                (persona_id.value, tenant_id.value),
            ).fetchall()
        ]
        return persona_from_row(row, grants)

    def list(self, tenant_id: TenantId) -> list[Persona]:
        rows = self.conn.execute(
            "SELECT id FROM personas WHERE tenant_id = %s::uuid ORDER BY display_name, id",
            (tenant_id.value,),
        ).fetchall()
        return [p for p in (self.get(tenant_id, PersonaId(str(row["id"]))) for row in rows) if p]

    def save(self, persona: Persona) -> None:
        self.conn.execute(
            """
            INSERT INTO personas (
                id, tenant_id, skin, display_name, one_liner, personality, taboos, relationships, updated_at
            )
            VALUES (
                %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, now()
            )
            ON CONFLICT (id) DO UPDATE SET
                skin = EXCLUDED.skin,
                display_name = EXCLUDED.display_name,
                one_liner = EXCLUDED.one_liner,
                personality = EXCLUDED.personality,
                taboos = EXCLUDED.taboos,
                relationships = EXCLUDED.relationships,
                updated_at = now()
            """,
            (
                persona.id.value,
                persona.tenant_id.value,
                persona.skin,
                persona.profile.display_name,
                persona.profile.one_liner,
                Jsonb(persona.profile.personality) if persona.profile.personality is not None else None,
                Jsonb(list(persona.profile.taboos)),
                Jsonb(list(persona.profile.relationships)),
            ),
        )
        self.conn.execute(
            "DELETE FROM persona_grants WHERE persona_id = %s::uuid AND tenant_id = %s::uuid",
            (persona.id.value, persona.tenant_id.value),
        )
        for grant in persona.grants:
            caps = [cap.value if isinstance(cap, Capability) else str(cap) for cap in grant.capabilities]
            self.conn.execute(
                """
                INSERT INTO persona_grants (persona_id, tenant_id, user_id, capabilities)
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s)
                """,
                (persona.id.value, persona.tenant_id.value, grant.user_id.value, caps),
            )
