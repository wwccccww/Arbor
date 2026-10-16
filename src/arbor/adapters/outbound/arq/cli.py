"""Run ARQ worker: arbor-worker"""

from __future__ import annotations


def main() -> None:
    from arq.cli import run_worker

    from arbor.adapters.outbound.arq.worker import WorkerSettings

    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()
