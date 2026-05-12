from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenSubject, require_user
from app.db.models import WebhookDelivery, WebhookSubscription
from app.db.postgres import get_session
from app.services.webhook_service import generate_secret

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

SUPPORTED_EVENTS = (
    "personalize.completed",
    "batch.queued",
    "batch.prospect.completed",
    "batch.completed",
    "lead.captured",
    "*",
)


class CreateWebhook(BaseModel):
    target_url: HttpUrl
    events: list[str] = Field(..., min_length=1)
    brand: Optional[str] = None
    description: Optional[str] = None


class WebhookOut(BaseModel):
    id: str
    target_url: str
    events: list[str]
    brand: Optional[str]
    active: bool
    description: Optional[str]
    created_at: datetime


class CreateWebhookOut(WebhookOut):
    secret: str = Field(..., description="Shown ONCE. Store for HMAC verification of inbound payloads.")


def _ser(w: WebhookSubscription) -> WebhookOut:
    return WebhookOut(
        id=str(w.id), target_url=w.target_url, events=w.events or [], brand=w.brand,
        active=w.active, description=w.description, created_at=w.created_at,
    )


@router.post("", response_model=CreateWebhookOut, status_code=201)
async def create_subscription(
    body: CreateWebhook,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> CreateWebhookOut:
    for e in body.events:
        if e not in SUPPORTED_EVENTS:
            raise HTTPException(status_code=400, detail=f"Unsupported event '{e}'. Valid: {list(SUPPORTED_EVENTS)}")
    secret = generate_secret()
    sub = WebhookSubscription(
        api_key_id=uuid.UUID(subj.api_key_id) if subj.api_key_id else None,
        target_url=str(body.target_url),
        events=body.events,
        secret=secret,
        brand=body.brand,
        description=body.description,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    out = _ser(sub)
    return CreateWebhookOut(**out.model_dump(), secret=secret)


@router.get("", response_model=list[WebhookOut])
async def list_subscriptions(
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> list[WebhookOut]:
    stmt = select(WebhookSubscription).order_by(WebhookSubscription.created_at.desc())
    if subj.api_key_id:
        stmt = stmt.where(WebhookSubscription.api_key_id == uuid.UUID(subj.api_key_id))
    return [_ser(w) for w in (await session.execute(stmt)).scalars()]


@router.delete("/{wid}", status_code=204)
async def revoke(
    wid: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        u = uuid.UUID(wid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook id")
    sub = (await session.execute(select(WebhookSubscription).where(WebhookSubscription.id == u))).scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if subj.api_key_id and (not sub.api_key_id or str(sub.api_key_id) != subj.api_key_id):
        raise HTTPException(status_code=403, detail="Not your subscription")
    sub.active = False
    await session.commit()


@router.get("/{wid}/deliveries")
async def list_deliveries(
    wid: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
):
    try:
        u = uuid.UUID(wid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook id")
    stmt = (
        select(WebhookDelivery)
        .where(WebhookDelivery.subscription_id == u)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(min(limit, 200))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(d.id), "event_type": d.event_type, "status": d.status,
            "attempts": d.attempts, "response_status": d.response_status,
            "response_body": d.response_body, "created_at": d.created_at.isoformat(),
            "last_attempt_at": d.last_attempt_at.isoformat() if d.last_attempt_at else None,
        }
        for d in rows
    ]
