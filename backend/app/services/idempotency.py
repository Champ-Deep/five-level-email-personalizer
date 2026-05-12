"""Idempotency support: replay-safe responses keyed by an Idempotency-Key header.

Pattern matches Stripe's. A caller sends `Idempotency-Key: <unique>`; if the
same key arrives within the TTL, we replay the cached response without
re-running the underlying handler. Scope is per API key (or anonymous bucket).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IdempotencyRecord

IDEMPOTENCY_TTL_HOURS = 24


async def find_record(
    session: AsyncSession,
    *,
    idem_key: str,
    api_key_id: Optional[str],
) -> Optional[IdempotencyRecord]:
    api_uuid = uuid.UUID(api_key_id) if api_key_id else None
    stmt = select(IdempotencyRecord).where(
        IdempotencyRecord.idem_key == idem_key,
        IdempotencyRecord.api_key_id == api_uuid,
        IdempotencyRecord.expires_at > datetime.now(timezone.utc),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def save_record(
    session: AsyncSession,
    *,
    idem_key: str,
    api_key_id: Optional[str],
    status_code: int,
    response_payload: dict[str, Any],
) -> None:
    api_uuid = uuid.UUID(api_key_id) if api_key_id else None
    rec = IdempotencyRecord(
        idem_key=idem_key,
        api_key_id=api_uuid,
        status_code=status_code,
        response_payload=response_payload,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=IDEMPOTENCY_TTL_HOURS),
    )
    session.add(rec)
    await session.commit()
