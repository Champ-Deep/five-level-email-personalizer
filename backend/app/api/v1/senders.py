from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenSubject, require_user
from app.db.models import SavedSender
from app.db.postgres import get_session

router = APIRouter(prefix="/senders", tags=["senders"])


class SavedSenderIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=200)
    company: str = Field(..., min_length=1, max_length=200)
    offer: str = Field(..., min_length=1, max_length=1000)
    is_default: bool = False


class SavedSenderOut(BaseModel):
    id: str
    label: str
    name: str
    company: str
    offer: str
    is_default: bool
    created_at: datetime


def _owner_email(subj: TokenSubject) -> str:
    """Saved senders are scoped per-user, identified by email.
    For API keys, use the owning user's email (which is what subj.sub is for api_key kind).
    For user JWTs, subj.sub is the UUID; we need the email — but we treat it as a stable key for now.
    """
    return subj.sub


def _to_out(s: SavedSender) -> SavedSenderOut:
    return SavedSenderOut(
        id=str(s.id), label=s.label, name=s.name, company=s.company, offer=s.offer,
        is_default=s.is_default, created_at=s.created_at,
    )


@router.get("", response_model=list[SavedSenderOut])
async def list_senders(
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> list[SavedSenderOut]:
    rows = (
        await session.execute(
            select(SavedSender)
            .where(SavedSender.owner_email == _owner_email(subj))
            .order_by(SavedSender.is_default.desc(), SavedSender.created_at.desc())
        )
    ).scalars().all()
    return [_to_out(s) for s in rows]


@router.post("", response_model=SavedSenderOut, status_code=201)
async def create_sender(
    body: SavedSenderIn,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> SavedSenderOut:
    owner = _owner_email(subj)
    if body.is_default:
        # Clear existing default
        await session.execute(
            update(SavedSender).where(SavedSender.owner_email == owner).values(is_default=False)
        )
    rec = SavedSender(
        owner_email=owner, label=body.label, name=body.name,
        company=body.company, offer=body.offer, is_default=body.is_default,
    )
    session.add(rec)
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Label already in use: {e}") from e
    await session.refresh(rec)
    return _to_out(rec)


@router.patch("/{sender_id}", response_model=SavedSenderOut)
async def update_sender(
    sender_id: str,
    body: SavedSenderIn,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> SavedSenderOut:
    try:
        sid = uuid.UUID(sender_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    rec = (await session.execute(select(SavedSender).where(SavedSender.id == sid))).scalar_one_or_none()
    if rec is None or rec.owner_email != _owner_email(subj):
        raise HTTPException(status_code=404, detail="Sender not found")
    if body.is_default and not rec.is_default:
        await session.execute(
            update(SavedSender).where(SavedSender.owner_email == _owner_email(subj)).values(is_default=False)
        )
    rec.label = body.label
    rec.name = body.name
    rec.company = body.company
    rec.offer = body.offer
    rec.is_default = body.is_default
    await session.commit()
    return _to_out(rec)


@router.delete("/{sender_id}", status_code=204)
async def delete_sender(
    sender_id: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        sid = uuid.UUID(sender_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    rec = (await session.execute(select(SavedSender).where(SavedSender.id == sid))).scalar_one_or_none()
    if rec is None or rec.owner_email != _owner_email(subj):
        raise HTTPException(status_code=404, detail="Sender not found")
    await session.delete(rec)
    await session.commit()
