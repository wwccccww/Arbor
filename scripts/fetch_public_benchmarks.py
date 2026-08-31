#!/usr/bin/env python3
"""Download public benchmark datasets (full sets stay out of Git)."""

from __future__ import annotations

import argparse
import hashlib
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


def _verify_smoke(manifest: dict) -> int:
    smoke_rel = manifest.get("splits", {}).get("smoke")
    if not smoke_rel:
        print("manifest missing smoke split", file=sys.stderr)
        return 1
    smoke_path = ROOT / str(smoke_rel)
    if not smoke_path.is_file():
        print(f"missing smoke fixture: {smoke_path}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(smoke_path.read_bytes()).hexdigest()
    expected = manifest.get("content_hash")
    if (
        isinstance(expected, str)
        and expected.startswith("sha256:")
        and digest != expected.removeprefix("sha256:")
    ):
        print(f"smoke hash mismatch for {smoke_path}", file=sys.stderr)
        return 1
    print(f"smoke ready: {smoke_path} ({manifest.get('dataset_version')}) sha256={digest[:12]}…")
    return 0


def fetch_benchmark(name: str, *, only_smoke: bool) -> int:
    manifest = _load_manifest(name)
    code = _verify_smoke(manifest)
    if code != 0:
        return code
    if only_smoke:
        return 0
    print(
        f"full {name} download not bundled; clone upstream and point nightly job at local path",
        file=sys.stderr,
    )
    print(f"source: {manifest.get('source_url')}", file=sys.stderr)
    corpus = manifest.get("splits", {}).get("corpus")
    if corpus:
        corpus_path = ROOT / str(corpus)
        corpus_path.mkdir(parents=True, exist_ok=True)
        print(f"corpus dir ready: {corpus_path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fetch_public_benchmarks")
    parser.add_argument(
        "--benchmark",
        default="all",
        choices=["all", "bfcl", "agentdojo", "multihop"],
    )
    parser.add_argument("--only", default="smoke", choices=["smoke", "full"])
    args = parser.parse_args(argv)
    only_smoke = args.only == "smoke"
    names = ["bfcl", "agentdojo", "multihop"] if args.benchmark == "all" else [args.benchmark]
    code = 0
    for name in names:
        code = max(code, fetch_benchmark(name, only_smoke=only_smoke))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
