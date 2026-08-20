-- Arbor outbound Postgres + pgvector schema.
-- embedding dim=64 matches arbor.domain.shared.textvec.fixture_embed (not bge-m3).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tenants (
    id uuid PRIMARY KEY,
    name text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY,
    email text,
    password_hash text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memberships (
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    user_id uuid NOT NULL REFERENCES users (id),
    role text NOT NULL DEFAULT 'member',
    PRIMARY KEY (tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS personas (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    skin text NOT NULL DEFAULT 'companion',
    display_name text NOT NULL DEFAULT '',
    one_liner text NOT NULL DEFAULT '',
    personality jsonb,
    taboos jsonb NOT NULL DEFAULT '[]'::jsonb,
    relationships jsonb NOT NULL DEFAULT '[]'::jsonb,
    tool_policy jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS persona_grants (
    persona_id uuid NOT NULL REFERENCES personas (id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    capabilities text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (persona_id, user_id)
);

CREATE TABLE IF NOT EXISTS threads (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    persona_id uuid NOT NULL REFERENCES personas (id),
    summary text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    thread_id uuid NOT NULL REFERENCES threads (id) ON DELETE CASCADE,
    role text NOT NULL,
    content text NOT NULL DEFAULT '',
    citation_memory_ids uuid[] NOT NULL DEFAULT '{}',
    citation_event_ids uuid[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS event_nodes (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    persona_id uuid NOT NULL,
    title text NOT NULL DEFAULT '',
    happened_at timestamptz,
    type text NOT NULL DEFAULT 'daily',
    importance smallint NOT NULL DEFAULT 3,
    summary text NOT NULL DEFAULT '',
    confidence real,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS event_edges (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    persona_id uuid NOT NULL,
    from_id uuid NOT NULL REFERENCES event_nodes (id),
    to_id uuid NOT NULL REFERENCES event_nodes (id),
    kind text NOT NULL,
    UNIQUE (from_id, to_id, kind)
);

CREATE TABLE IF NOT EXISTS memory_items (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    persona_id uuid NOT NULL,
    thread_id uuid,
    event_id uuid,
    type text NOT NULL DEFAULT 'fact',
    text text NOT NULL DEFAULT '',
    importance smallint,
    source jsonb,
    status text NOT NULL DEFAULT 'active',
    supersedes uuid,
    embedding vector(64),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS inbox_items (
    id text PRIMARY KEY,
    tenant_id uuid NOT NULL,
    persona_id uuid NOT NULL,
    kind text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    conflict_with uuid,
    status text NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    actor_user_id uuid NOT NULL,
    action text NOT NULL,
    resource_type text NOT NULL DEFAULT '',
    resource_id text,
    persona_id uuid,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_items_scope_status
    ON memory_items (tenant_id, persona_id, status);

CREATE INDEX IF NOT EXISTS memory_items_embedding_hnsw
    ON memory_items USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS event_nodes_scope
    ON event_nodes (tenant_id, persona_id);

CREATE INDEX IF NOT EXISTS event_edges_scope
    ON event_edges (tenant_id, persona_id);

CREATE INDEX IF NOT EXISTS audit_logs_tenant_created
    ON audit_logs (tenant_id, created_at DESC);

CREATE OR REPLACE FUNCTION arbor_event_edge_same_persona() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    from_tenant uuid;
    from_persona uuid;
    to_tenant uuid;
    to_persona uuid;
BEGIN
    SELECT tenant_id, persona_id INTO from_tenant, from_persona
    FROM event_nodes WHERE id = NEW.from_id;
    SELECT tenant_id, persona_id INTO to_tenant, to_persona
    FROM event_nodes WHERE id = NEW.to_id;
    IF from_tenant IS NULL OR to_tenant IS NULL THEN
        RAISE EXCEPTION 'event node missing' USING ERRCODE = 'P0002';
    END IF;
    IF from_tenant IS DISTINCT FROM to_tenant
        OR from_persona IS DISTINCT FROM to_persona
        OR NEW.tenant_id IS DISTINCT FROM from_tenant
        OR NEW.persona_id IS DISTINCT FROM from_persona THEN
        RAISE EXCEPTION 'EVENT_EDGE_PERSONA_MISMATCH' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS event_edges_same_persona ON event_edges;
CREATE TRIGGER event_edges_same_persona
    BEFORE INSERT OR UPDATE ON event_edges
    FOR EACH ROW EXECUTE FUNCTION arbor_event_edge_same_persona();
