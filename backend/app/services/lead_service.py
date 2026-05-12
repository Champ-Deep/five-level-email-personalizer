from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Lead


async def upsert_lead(
    session: AsyncSession,
    *,
    email: str,
    name: str | None,
    brand: str,
    source: str = "lead_magnet",
) -> Lead:
    stmt = (
        pg_insert(Lead)
        .values(email=email.lower(), name=name, brand=brand, source=source)
        .on_conflict_do_update(
            index_elements=[Lead.email, Lead.brand],
            set_={"name": name, "source": source},
        )
        .returning(Lead)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def get_lead(session: AsyncSession, *, email: str, brand: str) -> Lead | None:
    stmt = select(Lead).where(Lead.email == email.lower(), Lead.brand == brand)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
