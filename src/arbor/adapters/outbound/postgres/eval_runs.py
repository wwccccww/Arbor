from __future__ import annotations

import json


class PgEvalRunRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def save(self, run: dict) -> None:
        self.conn.execute(
            """
            INSERT INTO eval_runs (
                id, tenant_id, suite_version, strategy, mode, status,
                metrics, p0_tenant_leak_zero, cases
            )
            VALUES (
                %s, %s::uuid, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                metrics = EXCLUDED.metrics,
                p0_tenant_leak_zero = EXCLUDED.p0_tenant_leak_zero,
                cases = EXCLUDED.cases
            """,
            (
                run["id"],
                run["tenant_id"],
                run["suite_version"],
                run["strategy"],
                run.get("mode") or "retrieval",
                run.get("status") or "completed",
                json.dumps(run.get("metrics") or {}),
                bool(run.get("p0_tenant_leak_zero")),
                json.dumps(run.get("cases") or []),
            ),
        )

    def get(self, tenant_id: str, run_id: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT id, tenant_id, suite_version, strategy, mode, status,
                   metrics, p0_tenant_leak_zero, cases
            FROM eval_runs
            WHERE id = %s AND tenant_id = %s::uuid
            """,
            (run_id, tenant_id),
        ).fetchone()
        if row is None:
            return None
        metrics = row["metrics"]
        cases = row["cases"]
        if not isinstance(metrics, dict):
            metrics = json.loads(metrics or "{}")
        if not isinstance(cases, list):
            cases = json.loads(cases or "[]")
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "suite_version": str(row["suite_version"]),
            "strategy": str(row["strategy"]),
            "mode": str(row["mode"] or "retrieval"),
            "status": str(row["status"] or "completed"),
            "metrics": metrics,
            "p0_tenant_leak_zero": bool(row["p0_tenant_leak_zero"]),
            "cases": cases,
        }


class InMemoryEvalRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, dict] = {}

    def save(self, run: dict) -> None:
        self._runs[run["id"]] = dict(run)

    def get(self, tenant_id: str, run_id: str) -> dict | None:
        run = self._runs.get(run_id)
        if run is None or run.get("tenant_id") != tenant_id:
            return None
        return dict(run)
