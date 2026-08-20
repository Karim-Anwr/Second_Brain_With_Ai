"""Alembic environment for migration-driven PostgreSQL schema changes."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.base import Base
from app.db.configuration import get_database_url_from_environment


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Models will be imported here as later Phase 2 steps introduce them.
target_metadata = Base.metadata


def _database_url() -> str:
    database_url = get_database_url_from_environment()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for Alembic migrations.")
    if not database_url.startswith("postgresql+psycopg://"):
        raise RuntimeError("DATABASE_URL must use a postgresql+psycopg URL for Alembic migrations.")
    return database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "pyformat"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool, future=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
