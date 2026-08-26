#!/usr/bin/env python3
"""Parse docs/openapi.yaml and basic path sanity checks for CI."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "openapi.yaml"


def main() -> int:
    raw = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        print("openapi root must be a mapping", file=sys.stderr)
        return 1
    paths = raw.get("paths")
    if not isinstance(paths, dict) or not paths:
        print("openapi paths missing", file=sys.stderr)
        return 1
    servers = raw.get("servers") or []
    base = ""
    if servers and isinstance(servers[0], dict):
        base = str(servers[0].get("url") or "").rstrip("/")
    for path in paths:
        if not str(path).startswith("/"):
            print(f"invalid path key: {path}", file=sys.stderr)
            return 1
        if base and str(path).startswith(base + "/"):
            print(f"path should be relative to servers.url, not include {base}: {path}", file=sys.stderr)
            return 1
    print(f"openapi ok: {len(paths)} paths, server base {base or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
