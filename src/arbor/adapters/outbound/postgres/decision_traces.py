from __future__ import annotations

import json


class PgDecisionTraceRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def save(self, entry: dict) -> None:
        self.conn.execute(
            """
            INSERT INTO decision_traces (
                id, request_id, tenant_id, persona_id, thread_id, message_id,
                trace_version, summary_json, created_at, expires_at,
                encrypted_payload, content_sampled
            )
            VALUES (
                %s, %s, %s::uuid, %s::uuid, %s::uuid, %s,
                %s, %s::jsonb, %s::timestamptz, %s::timestamptz,
                %s, %s
            )
            ON CONFLICT (request_id, tenant_id) DO UPDATE SET
                summary_json = EXCLUDED.summary_json,
                message_id = EXCLUDED.message_id,
                expires_at = EXCLUDED.expires_at,
                encrypted_payload = EXCLUDED.encrypted_payload,
                content_sampled = EXCLUDED.content_sampled
            """,
            (
                entry["id"],
                entry["request_id"],
                entry["tenant_id"],
                entry.get("persona_id"),
                entry.get("thread_id"),
                entry.get("message_id"),
                int(entry.get("trace_version") or 1),
                json.dumps(entry.get("summary_json") or {}),
                entry.get("created_at"),
                entry.get("expires_at"),
                entry.get("encrypted_payload"),
                bool(entry.get("content_sampled")),
            ),
        )

    def get_by_request_id(self, tenant_id: str, request_id: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT id, request_id, tenant_id, persona_id, thread_id, message_id,
                   trace_version, summary_json, created_at, expires_at,
                   encrypted_payload, content_sampled
            FROM decision_traces
            WHERE tenant_id = %s::uuid AND request_id = %s
            """,
            (tenant_id, request_id),
        ).fetchone()
        if row is None:
            return None
        summary = row["summary_json"]
        if not isinstance(summary, dict):
            summary = json.loads(summary or "{}")
        return {
            "id": str(row["id"]),
            "request_id": str(row["request_id"]),
            "tenant_id": str(row["tenant_id"]),
            "persona_id": str(row["persona_id"]) if row["persona_id"] else None,
            "thread_id": str(row["thread_id"]) if row["thread_id"] else None,
            "message_id": row["message_id"],
            "trace_version": row["trace_version"],
            "summary_json": summary,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
            "encrypted_payload": row.get("encrypted_payload"),
            "content_sampled": bool(row.get("content_sampled")),
        }

    def delete_by_request_id(self, tenant_id: str, request_id: str) -> bool:
        cur = self.conn.execute(
            """
            DELETE FROM decision_traces
            WHERE tenant_id = %s::uuid AND request_id = %s
            """,
            (tenant_id, request_id),
        )
        return bool(getattr(cur, "rowcount", 0))

    def delete_expired(self, now_iso: str) -> int:
        cur = self.conn.execute(
            """
            DELETE FROM decision_traces
            WHERE expires_at IS NOT NULL AND expires_at <= %s::timestamptz
            """,
            (now_iso,),
        )
        return int(getattr(cur, "rowcount", 0) or 0)
