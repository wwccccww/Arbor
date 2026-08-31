from __future__ import annotations

import json

from arbor.paths import repo_root


def list_eval_baselines() -> dict:
    root = repo_root() / "eval" / "baselines"
    items: list[dict] = []
    if not root.is_dir():
        return {"items": items}
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        suite = str(payload.get("suite_version") or path.stem.replace("-smoke", ""))
        items.append(
            {
                "id": path.stem,
                "suite_version": suite,
                "path": str(path.relative_to(repo_root())),
                "metrics": {
                    k: v
                    for k, v in payload.items()
                    if k not in {"suite_version", "cases", "tracks"} and not isinstance(v, list)
                },
                "tracks": list(payload.get("tracks") or []),
                "case_count": len(payload.get("cases") or []),
            }
        )
    return {"items": items}
