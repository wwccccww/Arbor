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

    def list_recent(self, tenant_id: str, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, tenant_id, suite_version, strategy, mode, status,
                   metrics, p0_tenant_leak_zero, cases
            FROM eval_runs
            WHERE tenant_id = %s::uuid
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (tenant_id, limit),
        ).fetchall()
        out: list[dict] = []
        for row in rows:
            metrics = row["metrics"]
            cases = row["cases"]
            if not isinstance(metrics, dict):
                metrics = json.loads(metrics or "{}")
            if not isinstance(cases, list):
                cases = json.loads(cases or "[]")
            out.append(
                {
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
            )
        return out

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
        self._order: list[str] = []

    def save(self, run: dict) -> None:
        self._runs[run["id"]] = dict(run)
        if run["id"] not in self._order:
            self._order.append(run["id"])

    def list_recent(self, tenant_id: str, limit: int = 10) -> list[dict]:
        items: list[dict] = []
        for run_id in reversed(self._order):
            run = self._runs.get(run_id)
            if run is None or run.get("tenant_id") != tenant_id:
                continue
            items.append(dict(run))
            if len(items) >= limit:
                break
        return items

    def get(self, tenant_id: str, run_id: str) -> dict | None:
        run = self._runs.get(run_id)
        if run is None or run.get("tenant_id") != tenant_id:
            return None
        return dict(run)
