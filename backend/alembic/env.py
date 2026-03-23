from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ensure project root on path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from app.core.config import settings
from app.core.database import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_sync_url() -> str:
    """Return a sync SQLAlchemy URL derived from settings.DATABASE_URL.

    If the URL uses an async driver (e.g. postgresql+asyncpg) replace it with
    a common sync driver (postgresql+psycopg2) so Alembic can run migrations.
    """
    # prefer explicit settings, but fall back to environment variable
    url = settings.DATABASE_URL or os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL not set in environment")

    # convert async drivers to their sync equivalents for Alembic
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg2")
    # convert async sqlite driver to plain sqlite for Alembic
    if "+aiosqlite" in url:
        return url.replace("+aiosqlite", "")

    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_sync_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
