from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenSubject, require_user
from app.db.models import IcpProfile
from app.db.postgres import get_session
from app.levels.schemas import ProspectInput
from app.services.icp_scorer import score_icp_fit
from app.services.llm.registry import get_provider

router = APIRouter(prefix="/icp-profiles", tags=["icp"])


class IcpProfileIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=20, max_length=2000)
    is_default: bool = False


class IcpProfileOut(BaseModel):
    id: str
    label: str
    description: str
    is_default: bool
    created_at: datetime


def _to_out(p: IcpProfile) -> IcpProfileOut:
    return IcpProfileOut(
        id=str(p.id), label=p.label, description=p.description,
        is_default=p.is_default, created_at=p.created_at,
    )


@router.get("", response_model=list[IcpProfileOut])
async def list_profiles(
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> list[IcpProfileOut]:
    rows = (
        await session.execute(
            select(IcpProfile)
            .where(IcpProfile.owner_email == subj.sub)
            .order_by(IcpProfile.is_default.desc(), IcpProfile.created_at.desc())
        )
    ).scalars().all()
    return [_to_out(p) for p in rows]


@router.post("", response_model=IcpProfileOut, status_code=201)
async def create_profile(
    body: IcpProfileIn,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> IcpProfileOut:
    if body.is_default:
        await session.execute(
            update(IcpProfile).where(IcpProfile.owner_email == subj.sub).values(is_default=False)
        )
    rec = IcpProfile(owner_email=subj.sub, label=body.label, description=body.description, is_default=body.is_default)
    session.add(rec)
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Label conflict: {e}") from e
    await session.refresh(rec)
    return _to_out(rec)


@router.patch("/{profile_id}", response_model=IcpProfileOut)
async def update_profile(
    profile_id: str,
    body: IcpProfileIn,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> IcpProfileOut:
    try:
        pid = uuid.UUID(profile_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    rec = (await session.execute(select(IcpProfile).where(IcpProfile.id == pid))).scalar_one_or_none()
    if rec is None or rec.owner_email != subj.sub:
        raise HTTPException(status_code=404, detail="Not found")
    if body.is_default and not rec.is_default:
        await session.execute(
            update(IcpProfile).where(IcpProfile.owner_email == subj.sub).values(is_default=False)
        )
    rec.label = body.label
    rec.description = body.description
    rec.is_default = body.is_default
    await session.commit()
    return _to_out(rec)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        pid = uuid.UUID(profile_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    rec = (await session.execute(select(IcpProfile).where(IcpProfile.id == pid))).scalar_one_or_none()
    if rec is None or rec.owner_email != subj.sub:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(rec)
    await session.commit()


class ScoreOneIn(BaseModel):
    prospect: ProspectInput
    icp_profile_id: Optional[str] = None
    icp_description: Optional[str] = None
    model: Optional[str] = None


@router.post("/score")
async def score_one(
    body: ScoreOneIn,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """One-off ICP scoring (no research call). Pass either a saved
    profile_id or a free-text description.
    """
    description = body.icp_description
    if body.icp_profile_id and not description:
        try:
            pid = uuid.UUID(body.icp_profile_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid icp_profile_id")
        rec = (await session.execute(select(IcpProfile).where(IcpProfile.id == pid))).scalar_one_or_none()
        if rec is None or rec.owner_email != subj.sub:
            raise HTTPException(status_code=404, detail="ICP profile not found")
        description = rec.description
    if not description:
        raise HTTPException(status_code=400, detail="Provide icp_profile_id or icp_description")

    provider = get_provider("openrouter")
    try:
        result = await score_icp_fit(body.prospect, description, provider, model=body.model or "meta-llama/llama-4-maverick")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scoring failed: {e}") from e
    return result
