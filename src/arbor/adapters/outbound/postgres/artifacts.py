from __future__ import annotations

from psycopg.types.json import Jsonb

from arbor.domain.multimodal.artifact import Artifact, ArtifactSegment
from arbor.domain.shared.ids import PersonaId, TenantId


def _iso(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


class PgArtifactRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def get(self, tenant_id: TenantId, artifact_id: str) -> Artifact | None:
        row = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, object_uri, mime_type, checksum,
                   parser, parser_version, status, supersedes, created_by, created_at
            FROM artifacts
            WHERE id = %s AND tenant_id = %s::uuid
            """,
            (artifact_id, tenant_id.value),
        ).fetchone()
        return _artifact_from_row(row) if row else None

    def save(self, artifact: Artifact) -> None:
        self.conn.execute(
            """
            INSERT INTO artifacts (
                id, tenant_id, persona_id, object_uri, mime_type, checksum,
                parser, parser_version, status, supersedes, created_by, created_at
            )
            VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                supersedes = EXCLUDED.supersedes,
                parser = EXCLUDED.parser,
                parser_version = EXCLUDED.parser_version
            """,
            (
                artifact.id,
                artifact.tenant_id.value,
                artifact.persona_id.value,
                artifact.object_uri,
                artifact.mime_type,
                artifact.checksum,
                artifact.parser,
                artifact.parser_version,
                artifact.status,
                artifact.supersedes,
                artifact.created_by or None,
                artifact.created_at if artifact.created_at else None,
            ),
        )

    def list_for_persona(
        self, tenant_id: TenantId, persona_id: PersonaId, *, limit: int = 50
    ) -> list[Artifact]:
        rows = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, object_uri, mime_type, checksum,
                   parser, parser_version, status, supersedes, created_by, created_at
            FROM artifacts
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid AND status = 'active'
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (tenant_id.value, persona_id.value, limit),
        ).fetchall()
        return [_artifact_from_row(row) for row in rows]


class PgArtifactSegmentRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def add(self, segment: ArtifactSegment) -> None:
        self.conn.execute(
            """
            INSERT INTO artifact_segments (
                id, artifact_id, tenant_id, persona_id, modality, text,
                page_number, time_start_ms, time_end_ms, bounding_box,
                confidence, derived_by, memory_id
            )
            VALUES (%s, %s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                segment.id,
                segment.artifact_id,
                segment.tenant_id.value,
                segment.persona_id.value,
                segment.modality,
                segment.text,
                segment.page_number,
                segment.time_start_ms,
                segment.time_end_ms,
                Jsonb(segment.bounding_box) if segment.bounding_box else None,
                segment.confidence,
                segment.derived_by,
                segment.memory_id,
            ),
        )

    def list_for_artifact(self, tenant_id: TenantId, artifact_id: str) -> list[ArtifactSegment]:
        rows = self.conn.execute(
            """
            SELECT id, artifact_id, tenant_id, persona_id, modality, text,
                   page_number, time_start_ms, time_end_ms, bounding_box,
                   confidence, derived_by, memory_id
            FROM artifact_segments
            WHERE tenant_id = %s::uuid AND artifact_id = %s
            ORDER BY page_number NULLS LAST, time_start_ms NULLS LAST
            """,
            (tenant_id.value, artifact_id),
        ).fetchall()
        return [_segment_from_row(row) for row in rows]


class PgArtifactLineageRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def add(
        self,
        *,
        tenant_id: TenantId,
        lineage_id: str,
        artifact_id: str,
        segment_id: str | None,
        run_id: str | None,
        step_id: str | None,
        memory_id: str | None,
        citation_kind: str = "evidence",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO artifact_lineage (
                id, tenant_id, artifact_id, segment_id, run_id, step_id, memory_id, citation_kind
            )
            VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                lineage_id,
                tenant_id.value,
                artifact_id,
                segment_id,
                run_id,
                step_id,
                memory_id,
                citation_kind,
            ),
        )

    def list_for_run(self, tenant_id: TenantId, run_id: str) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, artifact_id, segment_id, run_id, step_id, memory_id, citation_kind
            FROM artifact_lineage
            WHERE tenant_id = %s::uuid AND run_id = %s
            """,
            (tenant_id.value, run_id),
        ).fetchall()
        return [dict(row) for row in rows]


def _artifact_from_row(row: dict) -> Artifact:
    return Artifact(
        id=str(row["id"]),
        tenant_id=TenantId(str(row["tenant_id"])),
        persona_id=PersonaId(str(row["persona_id"])),
        object_uri=str(row.get("object_uri") or ""),
        mime_type=str(row.get("mime_type") or ""),
        checksum=str(row.get("checksum") or ""),
        parser=str(row.get("parser") or ""),
        parser_version=str(row.get("parser_version") or ""),
        status=str(row.get("status") or "active"),
        supersedes=str(row["supersedes"]) if row.get("supersedes") else None,
        created_by=str(row["created_by"]) if row.get("created_by") else "",
        created_at=_iso(row.get("created_at")),
    )


def _segment_from_row(row: dict) -> ArtifactSegment:
    bbox = row.get("bounding_box")
    return ArtifactSegment(
        id=str(row["id"]),
        artifact_id=str(row["artifact_id"]),
        tenant_id=TenantId(str(row["tenant_id"])),
        persona_id=PersonaId(str(row["persona_id"])),
        modality=str(row.get("modality") or "text"),
        text=str(row.get("text") or ""),
        page_number=row.get("page_number"),
        time_start_ms=row.get("time_start_ms"),
        time_end_ms=row.get("time_end_ms"),
        bounding_box=dict(bbox) if bbox else None,
        confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
        derived_by=str(row.get("derived_by") or ""),
        memory_id=str(row["memory_id"]) if row.get("memory_id") else None,
    )
