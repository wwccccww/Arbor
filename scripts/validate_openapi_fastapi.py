"""Ensure FastAPI registered /v1 paths are documented in docs/openapi.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "openapi.yaml"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Undocumented operational endpoints (not part of public /v1 contract).
SKIP_EXACT = {
    "/ready",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/health",
}

SKIP_RELATIVE_PREFIXES = (
    "/debug/",
    "/eval/",
)


def _normalize_app_path(path: str) -> str | None:
    if not path.startswith("/v1"):
        if path in SKIP_EXACT:
            return None
        return None
    relative = path[len("/v1") :] or "/"
    if any(relative.startswith(prefix) for prefix in SKIP_RELATIVE_PREFIXES):
        return None
    return relative


def main() -> int:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    documented = set((spec.get("paths") or {}).keys())

    from apps.api.main import create_app

    app = create_app()
    openapi = app.openapi()
    app_paths: set[str] = set()
    for path in openapi.get("paths", {}):
        normalized = _normalize_app_path(path)
        if normalized is not None:
            app_paths.add(normalized)

    missing = sorted(app_paths - documented)
    if missing:
        print("FastAPI paths missing from docs/openapi.yaml:", file=sys.stderr)
        for item in missing:
            print(f"  {item}", file=sys.stderr)
        return 1

    print(f"openapi fastapi alignment ok: {len(app_paths)} documented /v1 paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
