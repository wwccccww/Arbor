"""Run ARQ worker: arbor-worker"""

from __future__ import annotations


def main() -> None:
    from arq.cli import run_worker

    run_worker(settings="arbor.adapters.outbound.arq.worker.WorkerSettings")


if __name__ == "__main__":
    main()
