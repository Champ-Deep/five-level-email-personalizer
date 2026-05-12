"""arq worker — processes batch personalization jobs.

Run with:

    arq app.workers.arq_worker.WorkerSettings
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Job
from app.db.postgres import async_session_maker
from app.levels.schemas import BatchPersonalizeRequest, ProspectInput, SenderInput
from app.services.brand_service import load_brand
from app.services.llm.registry import get_provider
from app.services.personalizer import personalize_one
from app.services.webhook_service import emit as emit_webhook

log = logging.getLogger(__name__)


async def batch_personalize_task(
    ctx: dict[str, Any],
    job_id: str,
    brand_slug: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    redis = ctx["redis"]
    body = BatchPersonalizeRequest(**payload)
    brand = load_brand(brand_slug)
    provider = get_provider(body.provider)
    sender = body.sender

    total = len(body.prospects)
    done = 0
    failed: list[int] = []

    await _set_status(redis, job_id, {"status": "running", "done": 0, "total": total})
    await _update_job_status(job_id, "running", done=0, failed_count=0, total=total)

    for idx, raw in enumerate(body.prospects):
        prospect = raw if isinstance(raw, ProspectInput) else ProspectInput(**raw)
        try:
            result = await personalize_one(
                prospect,
                brand,
                provider,
                sender=sender if isinstance(sender, SenderInput) or sender is None else SenderInput(**sender),
                levels=body.levels,
                model=body.model,
                system_prompt_override=body.system_prompt_override,
            )
            await redis.set(
                f"pipeline:{job_id}:results:{idx}",
                result.model_dump_json(),
                ex=60 * 60 * 24 * 7,
            )
            try:
                await emit_webhook(
                    "batch.prospect.completed",
                    {
                        "job_id": job_id,
                        "brand": brand_slug,
                        "index": idx,
                        "prospect": prospect.model_dump(mode="json"),
                        "result": json.loads(result.model_dump_json()),
                    },
                    brand=brand_slug,
                )
            except Exception:
                log.exception("Webhook emit failed for batch.prospect.completed")
        except Exception as e:
            log.exception("Personalize failed for prospect %s in job %s", idx, job_id)
            failed.append(idx)
            await redis.set(
                f"pipeline:{job_id}:results:{idx}",
                json.dumps({"error": str(e), "prospect": prospect.model_dump(mode="json")}),
                ex=60 * 60 * 24 * 7,
            )
        finally:
            done += 1
            await _set_status(
                redis,
                job_id,
                {"status": "running", "done": done, "total": total, "failed": len(failed)},
            )
            await _update_job_status(job_id, "running", done=done, failed_count=len(failed))

    final_status = "completed" if not failed else "completed_with_failures"
    await _set_status(
        redis,
        job_id,
        {"status": final_status, "done": done, "total": total, "failed": len(failed)},
    )
    await _update_job_status(job_id, final_status, done=done, failed_count=len(failed))

    try:
        await emit_webhook(
            "batch.completed",
            {
                "job_id": job_id,
                "brand": brand_slug,
                "total": total,
                "done": done,
                "failed": len(failed),
                "status": final_status,
            },
            brand=brand_slug,
        )
    except Exception:
        log.exception("Webhook emit failed for batch.completed")

    return {"job_id": job_id, "total": total, "done": done, "failed": len(failed)}


async def _set_status(redis, job_id: str, payload: dict[str, Any]) -> None:
    await redis.set(f"pipeline:{job_id}:status", json.dumps(payload), ex=60 * 60 * 24 * 7)


async def _update_job_status(
    job_id: str,
    status: str,
    *,
    done: int | None = None,
    failed_count: int | None = None,
    total: int | None = None,
) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
        job = result.scalar_one_or_none()
        if job is None:
            return
        job.status = status
        if done is not None:
            job.done = done
        if failed_count is not None:
            job.failed_count = failed_count
        if total is not None:
            job.total = total
        await session.commit()


async def deliver_webhook_task(ctx: dict[str, Any], delivery_id: str) -> dict[str, Any]:
    """arq task: deliver a single webhook with exponential backoff on failure.

    Backoff schedule (seconds, indexed by attempts): 60, 300, 1800, 7200, 43200.
    """
    from app.services.webhook_service import MAX_ATTEMPTS, deliver_once

    ok = await deliver_once(delivery_id)
    if ok:
        return {"delivery_id": delivery_id, "status": "delivered"}

    # Re-fetch to inspect attempt count
    from sqlalchemy import select as _select

    from app.db.models import WebhookDelivery

    async with async_session_maker() as session:
        result = await session.execute(_select(WebhookDelivery).where(WebhookDelivery.id == uuid.UUID(delivery_id)))
        delivery = result.scalar_one_or_none()
        if delivery is None or delivery.status == "failed":
            return {"delivery_id": delivery_id, "status": "failed"}
        if delivery.attempts >= MAX_ATTEMPTS:
            return {"delivery_id": delivery_id, "status": "failed"}

        # Schedule next attempt
        backoff = [60, 300, 1800, 7200, 43200]
        delay = backoff[min(delivery.attempts, len(backoff) - 1)]
        redis = ctx["redis"]
        from datetime import timedelta as _td
        await redis.enqueue_job(
            "deliver_webhook_task",
            delivery_id,
            _defer_by=_td(seconds=delay),
        )
        return {"delivery_id": delivery_id, "status": "retry_scheduled", "delay_s": delay}


class WorkerSettings:
    functions = [batch_personalize_task, deliver_webhook_task]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 10
    job_timeout = 60 * 30
