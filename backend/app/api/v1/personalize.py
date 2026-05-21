from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile, status
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
    ProspectInput,
)
from app.services.brand_service import BrandConfig
from app.services.excel_service import parse_excel
from app.services.idempotency import find_record, save_record
from app.services.llm.registry import get_provider
from app.services.personalizer import personalize
from app.services.suppression import load_matcher
from app.services.webhook_service import emit as emit_webhook

router = APIRouter(prefix="/personalize", tags=["personalize"])


# ── Rewrite actions (A2) ──────────────────────────────────────────────
# Quick "make it X" calls that don't re-research. Used from the
# VariationCard / history detail in the UI.
from pydantic import BaseModel as _BM, Field as _F


class RewriteIn(_BM):
    subject: str = _F(..., max_length=400)
    body: str = _F(..., max_length=4000)
    instruction: str = _F(..., min_length=2, max_length=400,
        description="What to change. E.g. '30% shorter', 'soften the CTA', 'remove paragraph 2'.")
    model: Optional[str] = None


class RewriteOut(_BM):
    subject: str
    body: str
    word_count: int
    instruction: str


REWRITE_SYSTEM = (
    "You are an elite B2B copy editor. You rewrite cold emails to match a specific "
    "instruction WITHOUT inventing facts or removing the original anchor signal. "
    "Always keep: first-name greeting, single soft permission-ask CTA, "
    "and the 'Best,\\n<sender>' sign-off if present. "
    "NEVER use em-dashes, en-dashes, 'not X, but Y' constructions, "
    "or AI-slop vocabulary (delve, leverage, navigate, robust, holistic, seamless, "
    "transformative, paradigm, cutting-edge). Return ONLY valid JSON."
)


REWRITE_PROMPT = """Rewrite the email below according to this instruction:

INSTRUCTION: {instruction}

Current subject: {subject}
Current body:
{body}

Return ONLY this JSON (no fences):
{{
  "subject": "<new subject (or same if unchanged)>",
  "body": "<new body — plain prose>",
  "word_count": <integer body word count>
}}"""


@router.post("/rewrite", response_model=RewriteOut)
async def rewrite_email(
    body: RewriteIn,
    subj: Optional[TokenSubject] = Depends(optional_subject),
) -> RewriteOut:
    if subj is None:
        raise HTTPException(status_code=401, detail="Sign in to rewrite emails")
    provider = get_provider("openrouter")
    prompt = REWRITE_PROMPT.format(
        instruction=body.instruction.strip(),
        subject=body.subject.strip(),
        body=body.body.strip(),
    )
    try:
        raw = await provider.chat(
            [{"role": "user", "content": prompt}],
            model=body.model or "deepseek/deepseek-v4-pro",
            max_tokens=2000,
            temperature=0.5,
            system=REWRITE_SYSTEM,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Rewrite failed: {e}") from e
    from app.services.llm.openrouter import extract_json as _extract
    data = _extract(raw)
    return RewriteOut(
        subject=str(data.get("subject", body.subject)).strip(),
        body=str(data.get("body", body.body)).strip(),
        word_count=int(data.get("word_count") or len(str(data.get("body", "")).split())),
        instruction=body.instruction,
    )


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

    # Resolve icp_profile_id → icp_description for the personalizer.
    if body.icp_profile_id and not body.icp_description and subj:
        from app.db.models import IcpProfile
        from sqlalchemy import select as _sel
        try:
            pid = uuid.UUID(body.icp_profile_id)
            rec = (await session.execute(_sel(IcpProfile).where(IcpProfile.id == pid))).scalar_one_or_none()
            if rec and rec.owner_email == subj.sub:
                body.icp_description = rec.description
        except ValueError:
            pass

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

    # Suppression filter — strip out DNC-listed prospects before we spend tokens.
    matcher = await load_matcher(session, subj.sub)
    kept: list = []
    suppressed_count = 0
    for p in body.prospects:
        reason = matcher.reason_for(getattr(p, "email", None), p.domain)
        if reason is None:
            kept.append(p)
        else:
            suppressed_count += 1
    if not kept:
        raise HTTPException(status_code=400, detail=f"All {suppressed_count} prospects were on your suppression list.")
    body.prospects = kept

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


@router.post("/excel", status_code=202)
async def personalize_excel(
    request: Request,
    file: UploadFile = File(..., description="Upload an .xlsx workbook. First sheet must have columns: name, title, domain (linkedin + email optional)."),
    sender_name: str = Form(...),
    sender_company: str = Form(...),
    sender_offer: str = Form(...),
    include_followup: bool = Form(False),
    tone_preset: Optional[str] = Form(None),
    style_rules: Optional[str] = Form(None),
    brand: BrandConfig = Depends(resolve_brand),
    subj: Optional[TokenSubject] = Depends(optional_subject),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Multipart Excel upload → queued batch job. Original workbook is
    stashed on the Job row so /v1/jobs/{id}/export?format=xlsx can return
    the same workbook with personalized columns appended.
    """
    if subj is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign up or sign in to upload an Excel batch.",
        )
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Upload must be an .xlsx file")

    raw = await file.read()
    if len(raw) > 25_000_000:
        raise HTTPException(status_code=413, detail="Excel file too large (max 25 MB)")
    try:
        prospects = parse_excel(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not prospects:
        raise HTTPException(status_code=400, detail="No valid rows found in the sheet.")
    if len(prospects) > 1000:
        raise HTTPException(status_code=413, detail="Batch limit is 1000 prospects.")

    # Suppression filter
    matcher = await load_matcher(session, subj.sub)
    kept = [p for p in prospects if matcher.reason_for(getattr(p, "email", None), p.domain) is None]
    suppressed_count = len(prospects) - len(kept)
    if not kept:
        raise HTTPException(status_code=400, detail=f"All {suppressed_count} rows were on your suppression list.")
    prospects = kept

    from app.levels.schemas import SenderInput as _SI
    body = BatchPersonalizeRequest(
        prospects=prospects,
        sender=_SI(name=sender_name, company=sender_company, offer=sender_offer),
        levels=[5],
        include_followup=include_followup,
        tone_preset=tone_preset,
        style_rules=style_rules,
    )

    job = Job(
        id=uuid.uuid4(),
        owner_email=subj.sub,
        brand=brand.slug,
        status="pending",
        total=len(body.prospects),
        done=0,
        failed_count=0,
        request_payload=json.loads(body.model_dump_json()),
        source_filename=file.filename,
    )
    session.add(job)
    await session.commit()

    from arq import create_pool
    from arq.connections import RedisSettings
    from app.core.config import get_settings
    import redis.asyncio as redis_asyncio

    redis_url = get_settings().redis_url

    # Stash original Excel bytes in Redis with 7-day TTL so /export can rebuild
    # the user's workbook with personalized columns appended.
    r = redis_asyncio.from_url(redis_url)
    try:
        await r.set(f"job:{str(job.id)}:source_excel", raw, ex=60 * 60 * 24 * 7)
    finally:
        await r.aclose()

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
                "source": "excel",
                "filename": file.filename,
                "request_id": getattr(request.state, "request_id", None),
            },
            brand=brand.slug,
        )
    except Exception as e:
        import logging
        logging.warning("Webhook emit failed for batch.queued (excel): %s", e)

    return {"job_id": str(job.id), "total": str(job.total), "include_followup": str(include_followup)}
