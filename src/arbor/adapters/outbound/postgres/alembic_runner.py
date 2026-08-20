from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from arbor.paths import repo_root

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


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


def upgrade_head(url: str) -> None:
    if not url:
        raise RuntimeError("DATABASE_URL required for Alembic")
    command.upgrade(alembic_config(url), "head")
