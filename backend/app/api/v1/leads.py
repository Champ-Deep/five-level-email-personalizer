from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_token
from app.core.rate_limit import limiter
from app.db.postgres import get_session
from app.services.brand_service import BrandConfig
from app.services.lead_service import upsert_lead
from app.services.webhook_service import emit as emit_webhook

from app.api.deps import resolve_brand

router = APIRouter(prefix="/leads", tags=["leads"])


class LeadRequest(BaseModel):
    email: EmailStr
    name: str | None = None


class LeadResponse(BaseModel):
    token: str
    lead_id: str


@router.post("", response_model=LeadResponse, status_code=201)
@limiter.limit("10/hour")
async def capture_lead(
    request: Request,
    body: LeadRequest,
    brand: BrandConfig = Depends(resolve_brand),
    session: AsyncSession = Depends(get_session),
) -> LeadResponse:
    lead = await upsert_lead(
        session,
        email=str(body.email),
        name=body.name,
        brand=brand.slug,
    )
    token = create_token(sub=str(lead.id), kind="lead", brand=brand.slug)

    try:
        await emit_webhook(
            "lead.captured",
            {
                "lead_id": str(lead.id),
                "email": lead.email,
                "name": lead.name,
                "brand": brand.slug,
                "source": lead.source,
                "request_id": getattr(request.state, "request_id", None),
            },
            brand=brand.slug,
        )
    except Exception as e:
        import logging
        logging.warning("Webhook emit failed for lead.captured: %s", e)

    return LeadResponse(token=token, lead_id=str(lead.id))
