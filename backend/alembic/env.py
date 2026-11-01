"""Alembic configuration for KNEXUS async PostgreSQL migrations."""
import asyncio
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
for import_path in (str(REPOSITORY_ROOT), str(BACKEND_ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from app.core.config import settings
from app.core.database import Base
import app.models  # noqa: F401  Registers all model tables on Base.metadata.

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render SQL without opening a database connection."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations only when an operator explicitly invokes Alembic."""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
