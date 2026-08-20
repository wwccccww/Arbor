#!/usr/bin/env python3
"""arbor-eval CLI. Retrieval only by default; no DeepSeek."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from arbor.adapters.inbound.eval_runner import ROOT, run_all_strategies, run_suite
from arbor.application.retrieval import STRATEGIES

SUITE_DIRS = {
    "v1": ROOT / "eval" / "fixtures" / "suite-v1",
    "ragas-v1": ROOT / "eval" / "fixtures" / "suite-ragas-v1",
}
BASELINE_FILES = {
    "v1": ROOT / "eval" / "baselines" / "suite-v1.json",
    "ragas-v1": ROOT / "eval" / "baselines" / "suite-ragas-v1.json",
}


def _baseline_payload(suite: str, payload: dict) -> dict:
    reports = payload.get("reports") or {}
    layered = reports.get("layered_tree") or {}
    metrics = layered.get("metrics") or {}
    return {
        "suite_version": suite,
        "updated_at": date.today().isoformat(),
        "mode": "retrieval",
        "k": 5,
        "n_cases": next(iter(payload["strategies"].values()), {}).get("n_cases"),
        "embeddings": "fixture_embed (deterministic hash, not bge-m3)",
        "note": (
            "夹具嵌入 + 内存向量。跨租户泄漏必须为 0。"
            "RAGAS faithfulness 不进本表。generation 未跑。"
            "规模集是 33 条源记忆上的问法扩张，不是大规模语料。"
        ),
        "strategies": payload["strategies"],
        "layered_tree_by_skill": metrics.get("by_skill"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arbor-eval")
    parser.add_argument("--suite", default="v1", choices=list(SUITE_DIRS))
    parser.add_argument("--mode", default="retrieval", choices=["retrieval", "generation"])
    parser.add_argument("--strategy", default="all", choices=["all", *STRATEGIES])
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="write eval/baselines/suite-<name>.json (requires --strategy all; omits per-case rows)",
    )
    args = parser.parse_args(argv)
    if args.mode == "generation":
        print("generation mode is nightly-only and not wired to DeepSeek in CI", file=sys.stderr)
        return 2
    suite_dir = SUITE_DIRS[args.suite]
    try:
        from arbor.application.evaluation.runner import resolve_world_path

        resolve_world_path(suite_dir)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    if args.strategy == "all":
        payload = run_all_strategies(suite_dir)
        print(json.dumps({"strategies": payload["strategies"]}, ensure_ascii=False, indent=2))
    else:
        payload = run_suite(suite_dir=suite_dir, strategy=args.strategy)
        print(
            json.dumps(
                {
                    "metrics": {k: v for k, v in payload["metrics"].items() if k != "by_skill"},
                    "by_skill": payload["metrics"].get("by_skill"),
                    "threshold_checks": payload["threshold_checks"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    if args.out:
        dumped = dict(payload)
        if args.strategy == "all" and "reports" in dumped:
            dumped = {
                "strategies": dumped["strategies"],
                "layered_tree_by_skill": (dumped.get("reports") or {})
                .get("layered_tree", {})
                .get("metrics", {})
                .get("by_skill"),
            }
        Path(args.out).write_text(json.dumps(dumped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.write_baseline:
        if args.strategy != "all":
            print("--write-baseline requires --strategy all", file=sys.stderr)
            return 1
        dest = BASELINE_FILES[args.suite]
        dest.write_text(json.dumps(_baseline_payload(args.suite, payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {dest}", file=sys.stderr)
    if args.strategy == "all":
        leaks = [payload["strategies"][name]["tenant_leak_count"] for name in payload["strategies"]]
        return 0 if all(x == 0 for x in leaks) else 1
    return 0 if payload["p0_tenant_leak_zero"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
