from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from arbor.adapters.outbound.postgres.alembic_runner import sqlalchemy_url
from arbor.env import database_url

config = context.config
if config.config_file_name:
    try:
        fileConfig(config.config_file_name)
    except KeyError:
        pass


def _url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    if configured and not configured.startswith("driver://"):
        return sqlalchemy_url(configured)
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL required for Alembic")
    return sqlalchemy_url(url)


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
