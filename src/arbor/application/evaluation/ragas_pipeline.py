"""RAGAS official pipeline: batched generations/scores, resume, per-metric cache."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from arbor.adapters.inbound.eval_runner import (
    ROOT,
    load_suite_files,
    load_world,
    resolve_backend,
    resolve_embed,
)
from arbor.adapters.outbound.inmemory import (
    InMemoryInboxRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    ScriptedReasoner,
    SeqIdGenerator,
)
from arbor.adapters.outbound.ragas_scorer import RAGAS_METRIC_NAMES, RagasSample
from arbor.application.conversation.send_message import SendMessage
from arbor.application.evaluation.generation import aggregate_generation, score_generation_case
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId, UserId
from arbor.env import chat_model, judge_embedding_model, judge_model
from arbor.paths import repo_root

DEFAULT_BATCH_SIZE = 10
PIPELINE_VERSION = "v1"
DEFAULT_RUNS_ROOT = repo_root() / "eval" / "runs" / "ragas-official"
RAGAS_OFFICIAL_DIR = ROOT / "eval" / "fixtures" / "suite-ragas-official"
Phase = Literal["all", "generate", "score"]


def default_run_dir(run_id: str | None = None) -> Path:
    rid = run_id or datetime.now(UTC).date().isoformat()
    return DEFAULT_RUNS_ROOT / rid


def generation_fingerprint(record: dict[str, Any]) -> str:
    payload = {
        "case_id": record.get("case_id"),
        "query": record.get("query"),
        "reference": record.get("reference"),
        "contexts": record.get("contexts"),
        "answer": record.get("answer"),
        "generator": record.get("generator"),
        "strategy": record.get("strategy"),
        "embed": record.get("embed"),
        "pipeline": PIPELINE_VERSION,
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class RagasRunStore:
    def __init__(self, run_dir: Path, *, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self.run_dir = run_dir
        self.batch_size = batch_size
        self.generations_dir = run_dir / "generations"
        self.scores_dir = run_dir / "scores"
        self.cache_dir = run_dir / "cache"
        self.manifest_path = run_dir / "manifest.json"

    def ensure_dirs(self) -> None:
        self.generations_dir.mkdir(parents=True, exist_ok=True)
        self.scores_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def batch_path(self, kind: Literal["generations", "scores"], batch_idx: int) -> Path:
        base = self.generations_dir if kind == "generations" else self.scores_dir
        return base / f"batch-{batch_idx:03d}.jsonl"

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def write_jsonl(self, path: Path, records: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(record, ensure_ascii=False, allow_nan=False) for record in records]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def is_generation_batch_complete(self, batch_idx: int, case_ids: list[str]) -> bool:
        records = self.read_jsonl(self.batch_path("generations", batch_idx))
        by_id = {row["case_id"]: row for row in records}
        return all(case_id in by_id for case_id in case_ids)

    def is_scores_batch_complete(self, batch_idx: int, case_ids: list[str]) -> bool:
        records = self.read_jsonl(self.batch_path("scores", batch_idx))
        by_id = {row["case_id"]: row for row in records}
        if not all(case_id in by_id for case_id in case_ids):
            return False
        for case_id in case_ids:
            metrics = by_id[case_id].get("metrics") or {}
            if not all(metric in metrics for metric in RAGAS_METRIC_NAMES):
                return False
        return True

    def load_metric_cache(self, case_id: str, metric: str, fingerprint: str) -> float | None:
        path = self.cache_dir / case_id / f"{metric}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("generation_fingerprint") != fingerprint:
            return None
        if data.get("judge_model") != judge_model():
            return None
        if data.get("judge_embedding") != judge_embedding_model():
            return None
        value = data.get("value")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def save_metric_cache(
        self,
        case_id: str,
        metric: str,
        value: float | None,
        fingerprint: str,
    ) -> None:
        path = self.cache_dir / case_id / f"{metric}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "case_id": case_id,
            "metric": metric,
            "value": value,
            "generation_fingerprint": fingerprint,
            "judge_model": judge_model(),
            "judge_embedding": judge_embedding_model(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

    def write_manifest(self, payload: dict[str, Any]) -> None:
        self.ensure_dirs()
        existing: dict[str, Any] = {}
        if self.manifest_path.is_file():
            existing = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        existing.update(payload)
        existing["updated_at"] = datetime.now(UTC).isoformat()
        self.manifest_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    def load_all_generations(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.generations_dir.glob("batch-*.jsonl")):
            rows.extend(self.read_jsonl(path))
        return rows

    def load_all_scores(self) -> dict[str, dict[str, float | None]]:
        by_case: dict[str, dict[str, float | None]] = {}
        for path in sorted(self.scores_dir.glob("batch-*.jsonl")):
            for row in self.read_jsonl(path):
                case_id = str(row["case_id"])
                metrics = row.get("metrics") or {}
                by_case[case_id] = {str(k): v for k, v in metrics.items()}
        return by_case


@dataclass
class _GenerationSession:
    send: SendMessage
    mem_index: dict[str, dict]
    strategy: str
    embed_label: str
    generator: str
    stores: InMemoryStores | None
    session: object | None


def _open_generation_session(
    *,
    suite_dir: Path,
    strategy: str,
    llm,
    backend: str,
    embed: str,
) -> _GenerationSession:
    from arbor.adapters.inbound.eval_runner import _open_postgres, _ports, _postgres_ports
    from arbor.adapters.outbound.deepseek import DeepSeekChatLLM

    world, _cases_doc, _thresholds, _k, world_path = load_suite_files(suite_dir)
    backend = resolve_backend(backend)
    session = None
    stores = None
    embed_client, embed_label = resolve_embed(embed)
    if backend == "postgres":
        session = _open_postgres(world_path, embed_client=embed_client)
        memories, events, threads, index, embed_fn, _summary = _postgres_ports(session)
        personas = session.personas
        inbox = session.inbox
    else:
        stores = InMemoryStores()
        load_world(world_path, stores, embed_client=embed_client)
        memories, events, threads, index, embed_fn, _summary = _ports(stores, embed_client=embed_client)
        personas = InMemoryPersonaRepository(stores)
        inbox = InMemoryInboxRepository(stores)
    send = SendMessage(
        personas=personas,
        memories=memories,
        threads=threads,
        events=events,
        inbox=inbox,
        vectors=index,
        llm=llm or DeepSeekChatLLM(),
        reasoner=ScriptedReasoner(),
        embed=embed_fn,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
        strategy=strategy,
    )
    return _GenerationSession(
        send=send,
        mem_index={item["id"]: item for item in world["memories"]},
        strategy=strategy,
        embed_label=embed_label,
        generator=chat_model(),
        stores=stores,
        session=session,
    )


def _close_generation_session(session: _GenerationSession) -> None:
    if session.session is not None:
        session.session.close()


def _generate_case(session: _GenerationSession, case: dict[str, Any]) -> dict[str, Any]:
    actor = case["actor"]
    tenant_id = TenantId(actor["tenant_id"])
    persona_id = PersonaId(actor["persona_id"])
    if session.stores is not None:
        thread = next(
            (item for item in session.stores.threads.values() if item.persona_id == persona_id),
            None,
        )
    else:
        thread = session.send.threads.get_by_persona(tenant_id, persona_id)
    thread_id = thread.id if thread else ThreadId(f"eval-{persona_id.value}")
    result = session.send(
        tenant_id=tenant_id,
        user_id=UserId(actor["user_id"]),
        thread_id=thread_id,
        persona_id=persona_id,
        text=case["query"],
        capabilities=list(Capability),
    )
    leak_ids = [
        mid for mid in result["injected_memory_ids"] if mid in (case.get("forbidden_memory_ids") or [])
    ]
    result["leak_ids"] = leak_ids
    contexts = [ctx for ctx in result.get("injected_contexts") or [] if ctx]
    row = score_generation_case(case, result, session.mem_index)
    record = {
        "case_id": case["id"],
        "query": str(case["query"]),
        "reference": str(case.get("reference") or ""),
        "reference_contexts": [str(x) for x in case.get("reference_contexts") or []],
        "answer": str(result.get("text") or ""),
        "text": str(result.get("text") or ""),
        "contexts": contexts,
        "behavior": case.get("expected_behavior"),
        "skill": case.get("skill"),
        "injected_memory_ids": list(result.get("injected_memory_ids") or []),
        "citations": list(result.get("citations") or []),
        "leaked": bool(row.get("leaked")),
        "strategy": session.strategy,
        "embed": session.embed_label,
        "generator": session.generator,
    }
    record["fingerprint"] = generation_fingerprint(record)
    record["_row"] = row
    record["_sample"] = None
    if case.get("expected_behavior") in {"answer", "cite"} and not leak_ids and contexts:
        record["_sample"] = RagasSample(
            question=record["query"],
            answer=record["answer"],
            contexts=contexts,
            ground_truth=record["reference"],
            reference_contexts=record["reference_contexts"],
        )
    return record


def _chunk_cases(cases: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [cases[i : i + batch_size] for i in range(0, len(cases), batch_size)]


def run_ragas_official_generate(
    *,
    strategy: str = "layered_tree",
    llm=None,
    backend: str = "auto",
    embed: str = "fixture",
    case_limit: int | None = None,
    run_dir: Path | None = None,
    run_id: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    resume: bool = True,
) -> Path:
    store = RagasRunStore(run_dir or default_run_dir(run_id), batch_size=batch_size)
    store.ensure_dirs()
    _world, cases_doc, _thresholds, _k, _world_path = load_suite_files(RAGAS_OFFICIAL_DIR)
    cases = list(cases_doc["cases"])
    if case_limit is not None:
        cases = cases[:case_limit]
    store.write_manifest(
        {
            "pipeline_version": PIPELINE_VERSION,
            "phase": "generate",
            "strategy": strategy,
            "embed": embed,
            "backend": backend,
            "generator": chat_model(),
            "n_cases": len(cases),
            "batch_size": batch_size,
        }
    )
    session = _open_generation_session(
        suite_dir=RAGAS_OFFICIAL_DIR,
        strategy=strategy,
        llm=llm,
        backend=backend,
        embed=embed,
    )
    try:
        for batch_idx, batch_cases in enumerate(_chunk_cases(cases, batch_size)):
            case_ids = [case["id"] for case in batch_cases]
            batch_path = store.batch_path("generations", batch_idx)
            if resume and store.is_generation_batch_complete(batch_idx, case_ids):
                continue
            records: list[dict[str, Any]] = []
            for case in batch_cases:
                record = _generate_case(session, case)
                public = {k: v for k, v in record.items() if not k.startswith("_")}
                records.append(public)
            store.write_jsonl(batch_path, records)
    finally:
        _close_generation_session(session)
    return store.run_dir


def _record_to_sample(record: dict[str, Any]) -> RagasSample | None:
    if record.get("leaked"):
        return None
    if record.get("behavior") not in {"answer", "cite"}:
        return None
    if not (record.get("answer") or "").strip() or not record.get("contexts"):
        return None
    return RagasSample(
        question=str(record["query"]),
        answer=str(record["answer"]),
        contexts=list(record["contexts"]),
        ground_truth=str(record.get("reference") or ""),
        reference_contexts=[str(x) for x in record.get("reference_contexts") or []],
    )


def run_ragas_official_score(
    *,
    run_dir: Path,
    scorer=None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    resume: bool = True,
) -> Path:
    from arbor.adapters.outbound.ragas_scorer import RagasMetricsScorer

    store = RagasRunStore(run_dir, batch_size=batch_size)
    store.ensure_dirs()
    scorer = scorer or RagasMetricsScorer()
    generations = store.load_all_generations()
    if not generations:
        raise FileNotFoundError(f"no generations found under {store.generations_dir}")
    store.write_manifest({"phase": "score", "judge": judge_model(), "judge_embedding": judge_embedding_model()})
    batches = _chunk_cases(generations, batch_size)
    for batch_idx, batch_records in enumerate(batches):
        case_ids = [str(record["case_id"]) for record in batch_records]
        scores_path = store.batch_path("scores", batch_idx)
        if resume and store.is_scores_batch_complete(batch_idx, case_ids):
            continue
        batch_scores: dict[str, dict[str, float | None]] = {}
        pending_records: list[dict[str, Any]] = []
        pending_metrics: set[str] = set()
        for record in batch_records:
            case_id = str(record["case_id"])
            fingerprint = str(record.get("fingerprint") or generation_fingerprint(record))
            metrics: dict[str, float | None] = {}
            missing_metrics: list[str] = []
            for metric in RAGAS_METRIC_NAMES:
                cached = store.load_metric_cache(case_id, metric, fingerprint)
                if cached is not None:
                    metrics[metric] = cached
                else:
                    missing_metrics.append(metric)
            batch_scores[case_id] = metrics
            if missing_metrics:
                pending_records.append(record)
                pending_metrics.update(missing_metrics)
        if pending_records and pending_metrics:
            samples = [_record_to_sample(record) for record in pending_records]
            metric_list = [metric for metric in RAGAS_METRIC_NAMES if metric in pending_metrics]
            scored = scorer.score_batch(samples, metric_names=metric_list)
            for record, metric_row in zip(pending_records, scored, strict=True):
                case_id = str(record["case_id"])
                fingerprint = str(record.get("fingerprint") or generation_fingerprint(record))
                for metric in metric_list:
                    value = metric_row.get(metric)
                    if batch_scores[case_id].get(metric) is None:
                        batch_scores[case_id][metric] = value
                    store.save_metric_cache(case_id, metric, batch_scores[case_id].get(metric), fingerprint)
        score_rows = []
        for record in batch_records:
            case_id = str(record["case_id"])
            fingerprint = str(record.get("fingerprint") or generation_fingerprint(record))
            for metric in RAGAS_METRIC_NAMES:
                batch_scores[case_id].setdefault(metric, None)
            score_rows.append(
                {
                    "case_id": case_id,
                    "generation_fingerprint": fingerprint,
                    "metrics": batch_scores[case_id],
                }
            )
        store.write_jsonl(scores_path, score_rows)
    return store.run_dir


def build_report_from_artifacts(
    *,
    run_dir: Path,
    strategy: str,
    backend: str,
    embed_label: str,
) -> dict[str, Any]:
    store = RagasRunStore(run_dir)
    generations = store.load_all_generations()
    scores_by_case = store.load_all_scores()
    rows: list[dict[str, Any]] = []
    for record in generations:
        case_id = str(record["case_id"])
        row = {
            "id": case_id,
            "behavior": record.get("behavior"),
            "skill": record.get("skill"),
            "citation_subset": set(record.get("citations") or []) <= set(record.get("injected_memory_ids") or []),
            "text_leak": False,
            "retrieval_leak": bool(record.get("leaked")),
            "leaked": bool(record.get("leaked")),
            "query": record.get("query"),
            "text": record.get("text"),
            "injected_memory_ids": record.get("injected_memory_ids") or [],
            "citations": record.get("citations") or [],
        }
        metric_row = scores_by_case.get(case_id) or {}
        for metric in RAGAS_METRIC_NAMES:
            key = f"ragas_{metric}"
            value = metric_row.get(metric)
            if row["leaked"] or row["behavior"] == "refuse":
                value = None
            row[key] = value
        rows.append(row)
    metrics = aggregate_generation(rows)
    manifest_path = ROOT / "eval" / "public" / "manifests" / "ragas-official.json"
    return {
        "suite_version": "ragas-official-v1",
        "strategy": strategy,
        "mode": "generation",
        "backend": backend,
        "embeddings": embed_label,
        "metrics": metrics,
        "p0_tenant_leak_zero": metrics.get("generation_p0_pass", False),
        "cases": rows,
        "protocol": str(manifest_path.relative_to(ROOT)) if manifest_path.is_file() else None,
        "benchmark_id": "ragas-official",
        "n_cases": len(rows),
        "run_dir": str(run_dir),
    }


def run_ragas_official_pipeline(
    *,
    phase: Phase = "all",
    strategy: str = "layered_tree",
    llm=None,
    scorer=None,
    backend: str = "auto",
    embed: str = "fixture",
    case_limit: int | None = None,
    run_dir: Path | None = None,
    run_id: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    resume: bool = True,
    use_disk: bool = True,
) -> dict[str, Any]:
    if not use_disk:
        from arbor.adapters.inbound.eval_runner import run_ragas_official_generation

        return run_ragas_official_generation(
            strategy=strategy,
            llm=llm,
            scorer=scorer,
            backend=backend,
            embed=embed,
            case_limit=case_limit,
        )
    resolved_run_dir = run_dir or default_run_dir(run_id)
    _embed_client, embed_label = resolve_embed(embed)
    if phase in {"all", "generate"}:
        run_ragas_official_generate(
            strategy=strategy,
            llm=llm,
            backend=backend,
            embed=embed,
            case_limit=case_limit,
            run_dir=resolved_run_dir,
            batch_size=batch_size,
            resume=resume,
        )
    if phase in {"all", "score"}:
        run_ragas_official_score(
            run_dir=resolved_run_dir,
            scorer=scorer,
            batch_size=batch_size,
            resume=resume,
        )
    return build_report_from_artifacts(
        run_dir=resolved_run_dir,
        strategy=strategy,
        backend=resolve_backend(backend),
        embed_label=embed_label,
    )
