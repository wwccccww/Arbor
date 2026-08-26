from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, pool

from arbor.paths import repo_root

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
CONNECT_TIMEOUT_SECONDS = 10
LOCK_TIMEOUT = "15s"
STATEMENT_TIMEOUT = "60s"
log = logging.getLogger("arbor.alembic")


def sqlalchemy_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    return url


def psycopg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg://")
    return url


def alembic_config(url: str) -> Config:
    ini = repo_root() / "alembic.ini"
    cfg = Config(str(ini) if ini.exists() else None)
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", sqlalchemy_url(url))
    cfg.set_main_option("path_separator", "os")
    return cfg


def migration_connect_args() -> dict[str, str | int]:
    """Fail startup instead of waiting forever on a locked or half-dead Postgres."""
    return {
        "connect_timeout": CONNECT_TIMEOUT_SECONDS,
        "options": f"-c lock_timeout={LOCK_TIMEOUT} -c statement_timeout={STATEMENT_TIMEOUT}",
    }


def migration_engine(url: str):
    return create_engine(
        sqlalchemy_url(url),
        poolclass=pool.NullPool,
        connect_args=migration_connect_args(),
    )


def upgrade_head(url: str) -> None:
    if not url:
        raise RuntimeError("DATABASE_URL required for Alembic")
    log.info(
        "Running alembic upgrade head (connect_timeout=%ss lock_timeout=%s statement_timeout=%s)",
        CONNECT_TIMEOUT_SECONDS,
        LOCK_TIMEOUT,
        STATEMENT_TIMEOUT,
    )
    command.upgrade(alembic_config(url), "head")
    log.info("alembic upgrade head finished")
