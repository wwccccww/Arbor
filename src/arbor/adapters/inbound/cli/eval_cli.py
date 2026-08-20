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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arbor-eval")
    parser.add_argument("--suite", default="v1", choices=["v1", "ragas-v1"])
    parser.add_argument("--mode", default="retrieval", choices=["retrieval", "generation"])
    parser.add_argument("--strategy", default="all", choices=["all", *STRATEGIES])
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="write eval/baselines/suite-v1.json (v1 + all strategies only)",
    )
    args = parser.parse_args(argv)
    if args.mode == "generation":
        print("generation mode is nightly-only and not wired to DeepSeek in CI", file=sys.stderr)
        return 2
    suite_dir = ROOT / "eval" / "fixtures" / ("suite-v1" if args.suite == "v1" else "suite-ragas-v1")
    if not (suite_dir / "world.json").exists():
        print(
            f"missing {suite_dir / 'world.json'}; CI/demo retrieval uses suite-v1",
            file=sys.stderr,
        )
        return 1
    if args.strategy == "all":
        payload = run_all_strategies(suite_dir)
        print(json.dumps({"strategies": payload["strategies"]}, ensure_ascii=False, indent=2))
    else:
        payload = run_suite(suite_dir=suite_dir, strategy=args.strategy)
        print(
            json.dumps(
                {"metrics": payload["metrics"], "threshold_checks": payload["threshold_checks"]},
                ensure_ascii=False,
                indent=2,
            )
        )
    if args.out:
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.write_baseline:
        if args.suite != "v1" or args.strategy != "all":
            print("--write-baseline requires --suite v1 --strategy all", file=sys.stderr)
            return 1
        baseline = {
            "suite_version": "v1",
            "updated_at": date.today().isoformat(),
            "mode": "retrieval",
            "k": 5,
            "note": "夹具嵌入 + 内存向量。跨租户泄漏必须为 0。RAGAS 不进本表。",
            "strategies": payload["strategies"],
        }
        dest = ROOT / "eval" / "baselines" / "suite-v1.json"
        dest.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {dest}", file=sys.stderr)
    if args.strategy == "all":
        leaks = [payload["strategies"][name]["tenant_leak_count"] for name in payload["strategies"]]
        return 0 if all(x == 0 for x in leaks) else 1
    return 0 if payload["p0_tenant_leak_zero"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
