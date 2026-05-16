from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenSubject, require_user
from app.db.models import PersonalizationRun
from app.db.postgres import get_session

router = APIRouter(prefix="/history", tags=["history"])


class HistoryItem(BaseModel):
    id: str
    brand: str
    prospect_name: str
    prospect_title: str
    prospect_domain: str
    sender_company: Optional[str]
    sender_name: Optional[str]
    tone_preset: Optional[str]
    picked_slot: Optional[str]
    created_at: datetime


class HistoryDetail(HistoryItem):
    style_rules: Optional[str]
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]


class HistoryList(BaseModel):
    items: list[HistoryItem]
    total: int
    limit: int
    offset: int


class PickRequest(BaseModel):
    picked_slot: str  # "A" | "B" | "C" — which variation the user picked


def _owner_filter(subj: TokenSubject) -> tuple:
    return (PersonalizationRun.owner_sub == subj.sub,)


def _to_item(r: PersonalizationRun) -> HistoryItem:
    return HistoryItem(
        id=str(r.id),
        brand=r.brand,
        prospect_name=r.prospect_name,
        prospect_title=r.prospect_title,
        prospect_domain=r.prospect_domain,
        sender_company=r.sender_company,
        sender_name=r.sender_name,
        tone_preset=r.tone_preset,
        picked_slot=r.picked_slot,
        created_at=r.created_at,
    )


@router.get("", response_model=HistoryList)
async def list_history(
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    brand: Optional[str] = None,
    q: Optional[str] = Query(None, description="Substring match on prospect_name / domain / company"),
) -> HistoryList:
    where_clauses: list = list(_owner_filter(subj))
    if brand:
        where_clauses.append(PersonalizationRun.brand == brand)
    if q:
        like = f"%{q.lower()}%"
        where_clauses.append(
            func.lower(PersonalizationRun.prospect_name).like(like)
            | func.lower(PersonalizationRun.prospect_domain).like(like)
            | func.lower(PersonalizationRun.sender_company).like(like)
        )

    total = (
        await session.execute(
            select(func.count()).select_from(PersonalizationRun).where(*where_clauses)
        )
    ).scalar() or 0

    rows = (
        await session.execute(
            select(PersonalizationRun)
            .where(*where_clauses)
            .order_by(PersonalizationRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()

    return HistoryList(items=[_to_item(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/{run_id}", response_model=HistoryDetail)
async def get_history_item(
    run_id: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> HistoryDetail:
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    r = (await session.execute(select(PersonalizationRun).where(PersonalizationRun.id == rid))).scalar_one_or_none()
    if r is None or r.owner_sub != subj.sub:
        raise HTTPException(status_code=404, detail="Run not found")
    return HistoryDetail(
        **_to_item(r).model_dump(),
        style_rules=r.style_rules,
        request_payload=r.request_payload,
        response_payload=r.response_payload,
    )


@router.patch("/{run_id}", response_model=HistoryDetail)
async def update_history_item(
    run_id: str,
    body: PickRequest,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> HistoryDetail:
    """Record which variation the user picked (for outcome tracking)."""
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    r = (await session.execute(select(PersonalizationRun).where(PersonalizationRun.id == rid))).scalar_one_or_none()
    if r is None or r.owner_sub != subj.sub:
        raise HTTPException(status_code=404, detail="Run not found")
    if body.picked_slot not in {"A", "B", "C"}:
        raise HTTPException(status_code=400, detail="picked_slot must be A, B, or C")
    r.picked_slot = body.picked_slot
    await session.commit()
    return HistoryDetail(
        **_to_item(r).model_dump(),
        style_rules=r.style_rules,
        request_payload=r.request_payload,
        response_payload=r.response_payload,
    )


@router.delete("/{run_id}", status_code=204)
async def delete_history_item(
    run_id: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    r = (await session.execute(select(PersonalizationRun).where(PersonalizationRun.id == rid))).scalar_one_or_none()
    if r is None or r.owner_sub != subj.sub:
        raise HTTPException(status_code=404, detail="Run not found")
    await session.delete(r)
    await session.commit()
