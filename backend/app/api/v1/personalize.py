from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
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
from app.services.idempotency import find_record, save_record
from app.services.llm.registry import get_provider
from app.services.personalizer import personalize
from app.services.webhook_service import emit as emit_webhook

router = APIRouter(prefix="/personalize", tags=["personalize"])


@router.post("", response_model=PersonalizeResponse)
@limiter.limit("30/day")
async def personalize_endpoint(
    request: Request,
    body: PersonalizeRequest,
    brand: BrandConfig = Depends(resolve_brand),
    subj: Optional[TokenSubject] = Depends(optional_subject),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> PersonalizeResponse:
    request.state.subject = subj
    api_key_id = subj.api_key_id if subj else None

    # Idempotency: replay cached response if we've already processed this key.
    if idempotency_key:
        cached = await find_record(session, idem_key=idempotency_key, api_key_id=api_key_id)
        if cached:
            return PersonalizeResponse(**cached.response_payload)

    provider = get_provider(body.provider)
    try:
        result = await personalize(body, brand, provider)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    if idempotency_key:
        await save_record(
            session,
            idem_key=idempotency_key,
            api_key_id=api_key_id,
            status_code=200,
            response_payload=json.loads(result.model_dump_json()),
        )

    # Persist run to history table for authenticated callers only.
    # Anonymous lead-magnet runs are NOT stored (privacy + DB hygiene).
    if subj is not None and subj.kind in ("user", "api_key"):
        try:
            from app.db.models import PersonalizationRun

            run = PersonalizationRun(
                owner_sub=subj.sub,
                owner_kind=subj.kind,
                brand=result.brand,
                prospect_name=body.prospect.name,
                prospect_title=body.prospect.title,
                prospect_domain=body.prospect.domain,
                sender_company=(body.sender.company if body.sender else None),
                sender_name=(body.sender.name if body.sender else None),
                tone_preset=body.tone_preset,
                style_rules=body.style_rules,
                request_payload=json.loads(body.model_dump_json()),
                response_payload=json.loads(result.model_dump_json()),
            )
            session.add(run)
            await session.commit()
        except Exception as e:
            import logging
            logging.warning("Failed to persist personalization run to history: %s", e)
            await session.rollback()

    # Emit webhook event (best-effort, fire-and-forget shape on the request path).
    try:
        await emit_webhook(
            "personalize.completed",
            {
                "brand": result.brand,
                "request_id": getattr(request.state, "request_id", None),
                "prospect": body.prospect.model_dump(mode="json"),
                "brief": result.brief.model_dump(mode="json"),
                "variations": [v.model_dump(mode="json") for v in result.variations],
            },
            brand=result.brand,
        )
    except Exception as e:
        import logging
        logging.warning("Webhook emit failed for personalize.completed: %s", e)

    return result


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

    try:
        await emit_webhook(
            "batch.queued",
            {
                "job_id": str(job.id),
                "brand": brand.slug,
                "total": job.total,
                "request_id": getattr(request.state, "request_id", None),
            },
            brand=brand.slug,
        )
    except Exception as e:
        import logging
        logging.warning("Webhook emit failed for batch.queued: %s", e)

    return {"job_id": str(job.id)}
