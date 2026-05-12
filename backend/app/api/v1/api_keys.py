from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenSubject, generate_api_key, require_user
from app.db.models import ApiKey
from app.db.postgres import get_session

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    brand: Optional[str] = Field(None, description="Lock key to a single brand (optional)")
    rate_limit_per_day: int = Field(1000, ge=1, le=100_000)


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    brand: Optional[str]
    rate_limit_per_day: int
    created_at: datetime
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]


class CreateApiKeyResponse(ApiKeyOut):
    key: str = Field(..., description="Full key — store securely. Shown ONCE.")


def _serialize(k: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=str(k.id), name=k.name, prefix=k.prefix, brand=k.brand,
        rate_limit_per_day=k.rate_limit_per_day, created_at=k.created_at,
        last_used_at=k.last_used_at, revoked_at=k.revoked_at,
    )


@router.post("", response_model=CreateApiKeyResponse, status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> CreateApiKeyResponse:
    if subj.kind != "user":
        raise HTTPException(status_code=403, detail="Only users (not API keys) can mint API keys")
    full_key, prefix, key_hash = generate_api_key()
    rec = ApiKey(
        name=body.name, prefix=prefix, key_hash=key_hash, owner_email=subj.sub,
        brand=body.brand, rate_limit_per_day=body.rate_limit_per_day,
    )
    session.add(rec)
    await session.commit()
    await session.refresh(rec)
    out = _serialize(rec)
    return CreateApiKeyResponse(**out.model_dump(), key=full_key)


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> list[ApiKeyOut]:
    result = await session.execute(
        select(ApiKey).where(ApiKey.owner_email == subj.sub).order_by(ApiKey.created_at.desc())
    )
    return [_serialize(k) for k in result.scalars()]


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        kid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key id")
    result = await session.execute(select(ApiKey).where(ApiKey.id == kid))
    rec = result.scalar_one_or_none()
    if rec is None or rec.owner_email != subj.sub:
        raise HTTPException(status_code=404, detail="API key not found")
    rec.revoked_at = datetime.now(timezone.utc)
    await session.commit()
