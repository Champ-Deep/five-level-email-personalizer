from __future__ import annotations

import io
import json
import uuid
from typing import Any, Literal

import redis.asyncio as redis_asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenSubject, require_user
from app.core.config import get_settings
from app.db.models import Job
from app.db.postgres import get_session
from app.services.excel_service import write_excel_with_results

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
        "has_source_excel": bool(job.source_filename),  # filename presence proxies for Excel upload
        "source_filename": job.source_filename,
    }


def _pick_best_variation(variations: list[dict[str, Any]], slot_hint: str | None = None) -> dict[str, Any] | None:
    """Return the chosen variation dict, picking by hint if given, otherwise
    the one with the highest reply_likelihood (with deliverability as tie-break).
    """
    if not variations:
        return None
    if slot_hint and slot_hint != "auto":
        for v in variations:
            if v.get("slot") == slot_hint:
                return v
    def key(v):
        scores = (v.get("email") or {}).get("scores") or {}
        rl = (scores.get("reply_likelihood") or {}).get("score", 0)
        d  = (scores.get("deliverability")  or {}).get("score", 0)
        return (rl, d)
    return max(variations, key=key)


@router.get("/{job_id}/export")
async def export_job(
    job_id: str,
    format: Literal["xlsx", "csv"] = Query("xlsx"),
    pick: Literal["A", "B", "C", "auto"] = Query("auto", description="Which variation to include per row"),
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Export results. Default: .xlsx, with original sheet preserved + new
    columns appended. `pick=auto` chooses the highest-scoring variation per row.
    """
    try:
        jid = uuid.UUID(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid job id") from e
    job = (await session.execute(select(Job).where(Job.id == jid))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_email and subj.sub != job.owner_email:
        raise HTTPException(status_code=403, detail="Not your job")

    # Pull per-prospect results from Redis.
    r = redis_asyncio.from_url(get_settings().redis_url, decode_responses=True)
    try:
        keys = await r.keys(f"pipeline:{job_id}:results:*")
        by_idx: dict[int, dict[str, Any]] = {}
        for k in keys:
            idx = int(k.rsplit(":", 1)[-1])
            payload = await r.get(k)
            if payload:
                by_idx[idx] = json.loads(payload)
    finally:
        await r.close()

    # Pull the source Excel bytes (binary — separate connection without decode_responses).
    source_excel: bytes | None = None
    rb = redis_asyncio.from_url(get_settings().redis_url)
    try:
        source_excel = await rb.get(f"job:{job_id}:source_excel")
    finally:
        await rb.aclose()

    # Index 0 in Redis corresponds to row 2 in Excel (row 1 is the header).
    flattened: dict[int, dict[str, Any]] = {}
    for idx, result in sorted(by_idx.items()):
        if "error" in result:
            flattened[idx + 2] = {"warnings": [result.get("error", "error")]}
            continue
        variations = result.get("variations", [])
        chosen = _pick_best_variation(variations, slot_hint=pick)
        if chosen is None:
            continue
        email = chosen.get("email") or {}
        followup = chosen.get("followup") or {}
        scores = email.get("scores") or {}
        flattened[idx + 2] = {
            "subject": email.get("subject", ""),
            "body": email.get("body", ""),
            "followup_subject": followup.get("subject", "") if followup else "",
            "followup_body":    followup.get("body", "") if followup else "",
            "model": chosen.get("model", ""),
            "slot": chosen.get("slot", ""),
            "deliverability": (scores.get("deliverability") or {}).get("score"),
            "reply_likelihood": (scores.get("reply_likelihood") or {}).get("score"),
            "warnings": email.get("warnings") or [],
        }

    if format == "xlsx":
        if source_excel:
            # Round-trip the user's own workbook with columns appended.
            data = write_excel_with_results(source_excel, flattened)
        else:
            # Synthesize a workbook from the original request payload.
            from openpyxl import Workbook
            wb = Workbook(); ws = wb.active; ws.title = "Prospects"
            ws.append(["Name", "Title", "Domain", "LinkedIn"])
            prospects = (job.request_payload or {}).get("prospects") or []
            for p in prospects:
                ws.append([p.get("name", ""), p.get("title", ""), p.get("domain", ""), p.get("linkedin", "")])
            buf = io.BytesIO(); wb.save(buf)
            data = write_excel_with_results(buf.getvalue(), flattened)
        filename = (job.source_filename or f"personalize-{job_id[:8]}.xlsx").rsplit(".", 1)[0] + "-personalized.xlsx"
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # CSV path (one row per prospect, one variation per row).
    lines: list[str] = [
        '"name","title","domain","subject","body","followup_subject","followup_body","model","slot","deliverability","reply_likelihood","warnings"'
    ]
    prospects = (job.request_payload or {}).get("prospects") or []
    for idx, p in enumerate(prospects):
        row = flattened.get(idx + 2, {})
        def q(s: Any) -> str:
            return '"' + str(s or "").replace('"', '""').replace("\n", "\\n") + '"'
        lines.append(",".join([
            q(p.get("name")), q(p.get("title")), q(p.get("domain")),
            q(row.get("subject")), q(row.get("body")),
            q(row.get("followup_subject")), q(row.get("followup_body")),
            q(row.get("model")), q(row.get("slot")),
            str(row.get("deliverability") or ""), str(row.get("reply_likelihood") or ""),
            q(" | ".join(row.get("warnings") or [])),
        ]))
    csv_bytes = "\n".join(lines).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="personalize-{job_id[:8]}.csv"'},
    )


@router.post("/{job_id}/regenerate/{prospect_index}")
async def regenerate_one_row(
    job_id: str,
    prospect_index: int,
    payload: dict[str, Any] | None = None,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Re-run /v1/personalize for a single prospect in this batch.

    Body (all optional):
      { "tone_preset": "...", "style_rules": "...", "include_followup": bool, "model": "..." }

    Updates the cached pipeline result so the next GET /v1/jobs/{id}
    surfaces the new variations for that row.
    """
    payload = payload or {}
    try:
        jid = uuid.UUID(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid job id") from e
    job = (await session.execute(select(Job).where(Job.id == jid))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_email and subj.sub != job.owner_email:
        raise HTTPException(status_code=403, detail="Not your job")

    prospects = (job.request_payload or {}).get("prospects") or []
    if prospect_index < 0 or prospect_index >= len(prospects):
        raise HTTPException(status_code=400, detail=f"prospect_index out of range (0..{len(prospects)-1})")

    from app.levels.schemas import PersonalizeRequest, ProspectInput, SenderInput
    from app.services.brand_service import load_brand
    from app.services.llm.registry import get_provider
    from app.services.personalizer import personalize

    sender_dict = (job.request_payload or {}).get("sender") or {}
    sender_obj = SenderInput(**sender_dict) if sender_dict else None
    base = (job.request_payload or {})
    req = PersonalizeRequest(
        prospect=ProspectInput(**prospects[prospect_index]),
        sender=sender_obj,
        levels=[5],
        provider="openrouter",
        tone_preset=payload.get("tone_preset") or base.get("tone_preset"),
        style_rules=payload.get("style_rules") or base.get("style_rules"),
        include_followup=bool(payload.get("include_followup", base.get("include_followup", False))),
        model=payload.get("model"),
    )
    brand_cfg = load_brand(job.brand)
    provider = get_provider("openrouter")
    try:
        result = await personalize(req, brand_cfg, provider)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Regenerate failed: {e}") from e

    r = redis_asyncio.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await r.set(
            f"pipeline:{job_id}:results:{prospect_index}",
            result.model_dump_json(),
            ex=60 * 60 * 24 * 7,
        )
    finally:
        await r.close()
    return json.loads(result.model_dump_json())


@router.post("/{job_id}/push")
async def push_job_to_integration(
    job_id: str,
    payload: dict[str, Any],
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Push the picked variation of each row to a configured integration.

    Body shape:
        { "integration_id": "<uuid>", "pick": "auto"|"A"|"B"|"C" }
    """
    integration_id = payload.get("integration_id")
    pick = payload.get("pick", "auto")
    if not integration_id:
        raise HTTPException(status_code=400, detail="integration_id required")

    try:
        jid = uuid.UUID(job_id)
        iid = uuid.UUID(integration_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid id: {e}") from e

    from app.db.models import IntegrationCredential
    job = (await session.execute(select(Job).where(Job.id == jid))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_email and subj.sub != job.owner_email:
        raise HTTPException(status_code=403, detail="Not your job")

    integ = (await session.execute(select(IntegrationCredential).where(IntegrationCredential.id == iid))).scalar_one_or_none()
    if integ is None or integ.owner_email != subj.sub:
        raise HTTPException(status_code=404, detail="Integration not found")

    from app.services.connectors.registry import get_connector
    from app.services.secrets import decrypt_config
    info = get_connector(integ.provider)
    config = decrypt_config(integ.config_encrypted)

    # Build the rows.
    r = redis_asyncio.from_url(get_settings().redis_url, decode_responses=True)
    try:
        keys = await r.keys(f"pipeline:{job_id}:results:*")
        by_idx: dict[int, dict[str, Any]] = {}
        for k in keys:
            idx = int(k.rsplit(":", 1)[-1])
            payload_str = await r.get(k)
            if payload_str:
                by_idx[idx] = json.loads(payload_str)
    finally:
        await r.close()

    prospects = (job.request_payload or {}).get("prospects") or []
    rows: list[dict[str, Any]] = []
    for idx, prospect in enumerate(prospects):
        result = by_idx.get(idx)
        if result is None or "error" in result:
            continue
        chosen = _pick_best_variation(result.get("variations", []), slot_hint=pick)
        if chosen is None:
            continue
        email = chosen.get("email") or {}
        followup = chosen.get("followup") or {}
        rows.append({
            "name": prospect.get("name"),
            "title": prospect.get("title"),
            "domain": prospect.get("domain"),
            "linkedin": prospect.get("linkedin"),
            "email": prospect.get("email"),
            "subject": email.get("subject", ""),
            "body": email.get("body", ""),
            "followup_subject": followup.get("subject", "") if followup else "",
            "followup_body":    followup.get("body", "") if followup else "",
            "model": chosen.get("model", ""),
            "slot":  chosen.get("slot", ""),
        })

    if not rows:
        raise HTTPException(status_code=409, detail="No completed rows to push yet.")

    result = await info["push"](config, rows)
    # Stamp last_used_at
    from datetime import datetime as _dt, timezone as _tz
    integ.last_used_at = _dt.now(_tz.utc)
    await session.commit()

    return {
        "ok": result.ok,
        "pushed": result.pushed,
        "failed": result.failed,
        "errors": result.errors[:50],  # cap noise
        "provider": integ.provider,
    }
