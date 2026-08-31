#!/usr/bin/env python3
"""Download public benchmark datasets (full sets stay out of Git)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "eval" / "public"


def _load_manifest(name: str) -> dict:
    path = PUBLIC / "manifests" / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_bfcl(*, only_smoke: bool) -> int:
    manifest = _load_manifest("bfcl")
    smoke_path = ROOT / str(manifest["splits"]["smoke"])
    if not smoke_path.is_file():
        print(f"missing smoke fixture: {smoke_path}", file=sys.stderr)
        return 1
    print(f"bfcl smoke ready: {smoke_path} ({manifest['dataset_version']})")
    if only_smoke:
        return 0
    print(
        "full BFCL download not bundled; clone gorilla BFCL and point nightly job at local path",
        file=sys.stderr,
    )
    print(f"source: {manifest.get('source_url')}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fetch_public_benchmarks")
    parser.add_argument("--benchmark", default="bfcl", choices=["bfcl"])
    parser.add_argument("--only", default="smoke", choices=["smoke", "full"])
    args = parser.parse_args(argv)
    only_smoke = args.only == "smoke"
    if args.benchmark == "bfcl":
        return fetch_bfcl(only_smoke=only_smoke)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
