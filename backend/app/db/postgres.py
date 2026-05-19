from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

log = logging.getLogger(__name__)

_settings = get_settings()
engine = create_async_engine(_settings.database_url, pool_pre_ping=True, future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# Idempotent "ALTER TABLE ... ADD COLUMN IF NOT EXISTS" statements for
# additive schema migrations that don't warrant a full alembic flow.
# Each entry should be safe to run on every boot.
_ADDITIVE_MIGRATIONS: tuple[str, ...] = (
    # Postgres 9.6+: ADD COLUMN IF NOT EXISTS is built-in.
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_filename VARCHAR(255)",
)


async def init_db() -> None:
    from app.db.models import Base  # noqa: WPS433
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Apply additive migrations. Each is wrapped to log + continue on
        # failure (e.g. table doesn't exist yet on a fresh install).
        for stmt in _ADDITIVE_MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                log.warning("Skipping additive migration %r: %s", stmt, e)


async def dispose_engine() -> None:
    await engine.dispose()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session
