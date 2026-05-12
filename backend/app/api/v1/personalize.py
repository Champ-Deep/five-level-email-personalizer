from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import resolve_brand
from app.core.auth import TokenSubject, optional_subject
from app.core.rate_limit import limiter
from app.db.models import Job
from app.db.postgres import async_session_maker, get_session
from app.levels.schemas import (
    BatchPersonalizeRequest,
    PersonalizeRequest,
    PersonalizeResponse,
)
from app.services.brand_service import BrandConfig
from app.services.llm.registry import get_provider
from app.services.personalizer import personalize

router = APIRouter(prefix="/personalize", tags=["personalize"])


def _rate_limit_for_subject(subj: Optional[TokenSubject]) -> str:
    if subj is None:
        return "1/day"
    if subj.kind == "lead":
        return "20/day"
    return "1000/day"


@router.post("", response_model=PersonalizeResponse)
@limiter.limit(lambda request: _rate_limit_for_subject(getattr(request.state, "subject", None)))
async def personalize_endpoint(
    request: Request,
    body: PersonalizeRequest,
    brand: BrandConfig = Depends(resolve_brand),
    subj: Optional[TokenSubject] = Depends(optional_subject),
) -> PersonalizeResponse:
    request.state.subject = subj
    provider = get_provider(body.provider)
    try:
        return await personalize(body, brand, provider)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post("/batch", status_code=202)
async def personalize_batch(
    request: Request,
    body: BatchPersonalizeRequest,
    brand: BrandConfig = Depends(resolve_brand),
    subj: Optional[TokenSubject] = Depends(optional_subject),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if subj is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign up or sign in to use batch personalization.",
        )
    if not body.prospects:
        raise HTTPException(status_code=400, detail="prospects must not be empty")
    if len(body.prospects) > 1000:
        raise HTTPException(status_code=413, detail="Batch limit is 1000 prospects.")

    job = Job(
        id=uuid.uuid4(),
        owner_email=subj.sub,
        brand=brand.slug,
        status="pending",
        total=len(body.prospects),
        done=0,
        failed_count=0,
        request_payload=json.loads(body.model_dump_json()),
    )
    session.add(job)
    await session.commit()

    # Lazy import to avoid a hard dep on arq when only the sync endpoint is used (e.g. tests).
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings

    redis_url = get_settings().redis_url
    pool = await create_pool(RedisSettings.from_dsn(redis_url))
    try:
        await pool.enqueue_job(
            "batch_personalize_task",
            str(job.id),
            brand.slug,
            json.loads(body.model_dump_json()),
        )
    finally:
        await pool.close()
    return {"job_id": str(job.id)}
