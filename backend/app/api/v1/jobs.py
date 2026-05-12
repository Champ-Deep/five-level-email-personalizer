from __future__ import annotations

import json
import uuid
from typing import Any

import redis.asyncio as redis_asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenSubject, require_user
from app.core.config import get_settings
from app.db.models import Job
from app.db.postgres import get_session

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid job id") from e

    result = await session.execute(select(Job).where(Job.id == job_uuid))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.owner_email and subj.sub != job.owner_email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your job")

    r = redis_asyncio.from_url(get_settings().redis_url, decode_responses=True)
    try:
        keys = await r.keys(f"pipeline:{job_id}:results:*")
        results: dict[int, dict[str, Any]] = {}
        for key in keys:
            idx = int(key.rsplit(":", 1)[-1])
            payload = await r.get(key)
            if payload:
                results[idx] = json.loads(payload)
        status_payload = await r.get(f"pipeline:{job_id}:status")
        live = json.loads(status_payload) if status_payload else {}
    finally:
        await r.close()

    return {
        "job_id": job_id,
        "status": job.status,
        "brand": job.brand,
        "total": job.total,
        "done": job.done,
        "failed_count": job.failed_count,
        "live": live,
        "results": results,
    }
