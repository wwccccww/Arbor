from __future__ import annotations

import json

from arbor.paths import repo_root


def list_eval_baselines() -> dict:
    items: list[dict] = []
    private_root = repo_root() / "eval" / "baselines"
    public_root = repo_root() / "eval" / "public" / "baselines"
    for root, category in ((private_root, "private"), (public_root, "public")):
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            suite = str(payload.get("suite_version") or payload.get("version") or path.stem.replace("-smoke", ""))
            items.append(
                {
                    "id": path.stem,
                    "suite_version": suite,
                    "category": category,
                    "benchmark_id": payload.get("benchmark_id"),
                    "path": str(path.relative_to(repo_root())),
                    "metrics": {
                        k: v
                        for k, v in payload.items()
                        if k
                        not in {"suite_version", "cases", "tracks", "version", "benchmark_id", "description"}
                        and not isinstance(v, list)
                    },
                    "tracks": list(payload.get("tracks") or []),
                    "case_count": len(payload.get("cases") or []) or payload.get("case_count"),
                    "historical": bool(payload.get("historical")),
                    "planner_kind": payload.get("planner_kind"),
                }
            )
    return {"items": items}
