#!/usr/bin/env python3
"""arbor-eval CLI. Retrieval is default; generation needs DEEPSEEK_API_KEY."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from arbor.adapters.inbound.eval_runner import (
    ROOT,
    resolve_backend,
    resolve_embed,
    run_all_strategies,
    run_generation,
    run_suite,
)
from arbor.application.evaluation.runner import comparison_row
from arbor.application.retrieval import STRATEGIES
from arbor.env import chat_api_key, embedding_api_key, judge_status
from arbor.observability.eval_metrics import export_eval_run_metrics
from arbor.observability.runtime import build_observability

SUITE_DIRS = {
    "v1": ROOT / "eval" / "fixtures" / "suite-v1",
    "ragas-v1": ROOT / "eval" / "fixtures" / "suite-ragas-v1",
    "agent-v1": ROOT / "eval" / "fixtures" / "agent-v1",
    "agent-ablation-v1": ROOT / "eval" / "fixtures" / "agent-ablation-v1",
}
BASELINE_FILES = {
    "v1": ROOT / "eval" / "baselines" / "suite-v1.json",
    "ragas-v1": ROOT / "eval" / "baselines" / "suite-ragas-v1.json",
    "agent-v1": ROOT / "eval" / "baselines" / "agent-v1-smoke.json",
    "agent-ablation-v1": ROOT / "eval" / "baselines" / "agent-ablation-v1.json",
}


def _baseline_dest(suite: str, embed: str) -> Path:
    if embed == "bge" and suite == "ragas-v1":
        return ROOT / "eval" / "baselines" / "suite-ragas-v1-bge.json"
    return BASELINE_FILES[suite]


def _baseline_payload(suite: str, payload: dict, embed_label: str) -> dict:
    reports = payload.get("reports") or {}
    layered = reports.get("layered_tree") or {}
    metrics = layered.get("metrics") or {}
    return {
        "suite_version": suite,
        "updated_at": date.today().isoformat(),
        "mode": "retrieval",
        "k": 5,
        "n_cases": next(iter(payload["strategies"].values()), {}).get("n_cases"),
        "embeddings": embed_label,
        "note": (
            "夹具嵌入。向量后端见 backend 字段：memory 或 postgres/pgvector。"
            "跨租户泄漏必须为 0。"
            "RAGAS faithfulness 不进检索表。"
            "规模集是 33 条源记忆上的问法扩张，不是大规模语料。"
        ),
        "backend": payload.get("backend"),
        "strategies": payload["strategies"],
        "layered_tree_by_skill": metrics.get("by_skill"),
    }


def _export_metrics(*, suite: str, strategy: str, metrics: dict, p0_ok: bool) -> None:
    export_eval_run_metrics(
        build_observability(service="arbor-eval"),
        suite=suite,
        strategy=strategy,
        metrics=metrics,
        p0_tenant_leak_zero=p0_ok,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arbor-eval")
    parser.add_argument("--suite", default="v1", choices=list(SUITE_DIRS))
    parser.add_argument("--mode", default="retrieval", choices=["retrieval", "generation", "agent"])
    parser.add_argument("--strategy", default="all", choices=["all", *STRATEGIES])
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "memory", "postgres"],
        help="auto uses Postgres when DATABASE_URL is set",
    )
    parser.add_argument("--out", default="")
    parser.add_argument("--allow-large", action="store_true", help="allow generation on ragas-v1")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="write eval/baselines JSON (retrieval: four strategies; generation: suite-v1-generation.json)",
    )
    parser.add_argument(
        "--embed",
        default="fixture",
        choices=["fixture", "bge"],
        help="embedding backend for retrieval eval (bge needs EMBEDDING_API_KEY)",
    )
    args = parser.parse_args(argv)
    if args.mode == "agent":
        if args.suite not in ("agent-v1", "agent-ablation-v1"):
            print("agent mode requires --suite agent-v1 or agent-ablation-v1", file=sys.stderr)
            return 1
        from arbor.adapters.inbound.agent_eval_stack import (
            agent_fixture_path,
            build_agent_eval_stack,
        )
        from arbor.application.evaluation.agent_ablation import (
            ablation_fixture_path,
            run_agent_ablation_tracks,
        )
        from arbor.application.evaluation.agent_evolution import run_agent_evolution_tracks
        from arbor.application.evaluation.agent_runner import run_agent_smoke

        stack = build_agent_eval_stack()
        if args.suite == "agent-ablation-v1":
            ablation = run_agent_ablation_tracks(
                stack=build_agent_eval_stack(use_employee_templates=False),
                fixture_path=ablation_fixture_path(),
            )
            baseline_path = BASELINE_FILES["agent-ablation-v1"]
            baseline = {}
            if baseline_path.is_file():
                baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            _export_metrics(
                suite="agent-ablation-v1",
                strategy="agent-ablation",
                metrics={
                    "task_success_rate": max(
                        t.get("task_success_rate", 0.0) for t in ablation.get("tracks") or []
                    ),
                },
                p0_ok=all(
                    t.get("unauthorized_action_rate", 0.0) == 0.0
                    and t.get("approval_bypass_rate", 0.0) == 0.0
                    and t.get("duplicate_side_effect_rate", 0.0) == 0.0
                    for t in ablation.get("tracks") or []
                ),
            )
            print(json.dumps(ablation, ensure_ascii=False, indent=2))
            for track in ablation.get("tracks") or []:
                base_track = next(
                    (t for t in baseline.get("tracks") or [] if t.get("id") == track.get("id")),
                    None,
                )
                if base_track and track.get("task_success_rate", 0.0) < float(
                    base_track.get("task_success_rate", 0.0)
                ):
                    return 1
                if track.get("unauthorized_action_rate", 0.0) > 0:
                    return 1
                if track.get("approval_bypass_rate", 0.0) > 0:
                    return 1
                if track.get("duplicate_side_effect_rate", 0.0) > 0:
                    return 1
            return 0

        report = run_agent_smoke(
            fixture_path=agent_fixture_path(),
            start_run=stack["start_run"],
            approve_step=stack["approve_step"],
            reject_step=stack["reject_step"],
            resume_run=stack["resume_run"],
            personas=stack["personas"],
            runs=stack["runs"],
            flaky_ticket_tool=stack["flaky_ticket_tool"],
            counting_ticket_tool=stack["counting_ticket_tool"],
        )
        evolution = run_agent_evolution_tracks(
            stack=build_agent_eval_stack(use_employee_templates=False),
        )
        baseline_path = BASELINE_FILES["agent-v1"]
        baseline = {}
        if baseline_path.is_file():
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        report["baseline_task_success_rate"] = baseline.get("task_success_rate")
        report["evolution_tracks"] = evolution.get("tracks")
        _export_metrics(
            suite="agent-v1",
            strategy="agent-smoke",
            metrics={
                "task_success_rate": report.get("task_success_rate", 0.0),
                "duplicate_side_effect_rate": report.get("duplicate_side_effect_rate", 0.0),
            },
            p0_ok=(
                report.get("unauthorized_action_rate", 0.0) == 0.0
                and report.get("approval_bypass_rate", 0.0) == 0.0
                and report.get("duplicate_side_effect_rate", 0.0) == 0.0
            ),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report.get("task_success_rate", 0.0) < float(baseline.get("task_success_rate", 1.0)):
            return 1
        if report.get("unauthorized_action_rate", 0.0) > 0:
            return 1
        if report.get("approval_bypass_rate", 0.0) > 0:
            return 1
        if report.get("duplicate_side_effect_rate", 0.0) > 0:
            return 1
        return 0

    suite_dir = SUITE_DIRS[args.suite]
    try:
        from arbor.application.evaluation.runner import resolve_world_path

        resolve_world_path(suite_dir)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.mode == "generation":
        if args.suite != "v1" and not args.allow_large:
            print("generation defaults to suite-v1; pass --allow-large for ragas-v1", file=sys.stderr)
            return 1
        if not chat_api_key():
            print("generation needs DEEPSEEK_API_KEY in this process", file=sys.stderr)
            return 2
        strategy = "layered_tree" if args.strategy == "all" else args.strategy
        payload = run_generation(suite_dir=suite_dir, strategy=strategy, backend=args.backend)
        _export_metrics(
            suite=args.suite,
            strategy=strategy,
            metrics=dict(payload.get("metrics") or {}),
            p0_ok=not (payload.get("metrics") or {}).get("n_leaking_cases"),
        )
        print(json.dumps({"metrics": payload["metrics"]}, ensure_ascii=False, indent=2))
        if args.out:
            slim = {"metrics": payload["metrics"], "cases": payload["cases"]}
            Path(args.out).write_text(json.dumps(slim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.write_baseline:
            dest = ROOT / "eval" / "baselines" / "suite-v1-generation.json"
            dest.write_text(
                json.dumps(
                    {
                        "suite_version": args.suite,
                        "updated_at": date.today().isoformat(),
                        "mode": "generation",
                        "strategy": strategy,
                        "generator": "deepseek-chat",
                        "judge": judge_status(),
                        "metrics": payload["metrics"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"wrote {dest}", file=sys.stderr)
        metrics = payload["metrics"]
        if metrics["n_leaking_cases"] or metrics["refuse_text_leak_count"]:
            return 1
        if metrics["citation_subset_rate"] < 1.0:
            return 1
        return 0

    if args.embed == "bge" and not embedding_api_key():
        print("bge embed needs EMBEDDING_API_KEY in this process", file=sys.stderr)
        return 2

    try:
        backend = resolve_backend(args.backend)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 2

    _, embed_label = resolve_embed(args.embed)

    if args.strategy == "all":
        payload = run_all_strategies(suite_dir, backend=backend, embed=args.embed)
        for name, row in (payload.get("strategies") or {}).items():
            _export_metrics(
                suite=args.suite,
                strategy=name,
                metrics=dict(row),
                p0_ok=int(row.get("tenant_leak_count") or 0) == 0,
            )
        print(json.dumps({"backend": payload.get("backend"), "strategies": payload["strategies"]}, ensure_ascii=False, indent=2))
    else:
        payload = run_suite(suite_dir=suite_dir, strategy=args.strategy, backend=backend, embed=args.embed)
        _export_metrics(
            suite=args.suite,
            strategy=args.strategy,
            metrics=comparison_row(payload),
            p0_ok=bool(payload.get("p0_tenant_leak_zero")),
        )
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
            print("--write-baseline retrieval requires --strategy all", file=sys.stderr)
            return 1
        dest = _baseline_dest(args.suite, args.embed)
        dest.write_text(
            json.dumps(_baseline_payload(args.suite, payload, embed_label), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {dest}", file=sys.stderr)
    if args.strategy == "all":
        leaks = [payload["strategies"][name]["tenant_leak_count"] for name in payload["strategies"]]
        return 0 if all(x == 0 for x in leaks) else 1
    return 0 if payload["p0_tenant_leak_zero"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
