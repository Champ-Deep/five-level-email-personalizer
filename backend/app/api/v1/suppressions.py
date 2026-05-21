from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenSubject, require_user
from app.db.models import SuppressionEntry
from app.db.postgres import get_session

router = APIRouter(prefix="/suppressions", tags=["suppressions"])


class SuppressionIn(BaseModel):
    email: Optional[str] = None
    domain: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=200)
    source: str = Field("manual", max_length=40)

    def normalized(self) -> tuple[Optional[str], Optional[str]]:
        e = (self.email or "").strip().lower() or None
        d = (self.domain or "").strip().lower().lstrip(".") or None
        if not e and not d:
            raise ValueError("either email or domain is required")
        if e and "@" not in e:
            raise ValueError("email must contain @")
        return e, d


class SuppressionOut(BaseModel):
    id: str
    email: Optional[str]
    domain: Optional[str]
    reason: Optional[str]
    source: str
    created_at: datetime


def _to_out(s: SuppressionEntry) -> SuppressionOut:
    return SuppressionOut(
        id=str(s.id), email=s.email, domain=s.domain, reason=s.reason,
        source=s.source, created_at=s.created_at,
    )


@router.get("", response_model=list[SuppressionOut])
async def list_suppressions(
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> list[SuppressionOut]:
    rows = (
        await session.execute(
            select(SuppressionEntry)
            .where(SuppressionEntry.owner_email == subj.sub)
            .order_by(SuppressionEntry.created_at.desc())
        )
    ).scalars().all()
    return [_to_out(s) for s in rows]


@router.post("", response_model=SuppressionOut, status_code=201)
async def create_suppression(
    body: SuppressionIn,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> SuppressionOut:
    try:
        e, d = body.normalized()
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    rec = SuppressionEntry(owner_email=subj.sub, email=e, domain=d, reason=body.reason, source=body.source)
    session.add(rec)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Already on your suppression list")
    await session.refresh(rec)
    return _to_out(rec)


@router.delete("/{entry_id}", status_code=204)
async def delete_suppression(
    entry_id: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        eid = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    rec = (await session.execute(select(SuppressionEntry).where(SuppressionEntry.id == eid))).scalar_one_or_none()
    if rec is None or rec.owner_email != subj.sub:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(rec)
    await session.commit()


@router.post("/bulk", status_code=201)
async def bulk_upload(
    file: UploadFile = File(..., description="CSV with one column (email or domain) or two columns (target, reason)"),
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if (file.filename or "").lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Upload a .csv file (one target per line). For Excel, paste the column into a .csv.")
    raw = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(raw))
    added = 0
    skipped = 0
    for row in reader:
        if not row or all(c.strip() == "" for c in row):
            continue
        target = (row[0] or "").strip().lower()
        if target.lower() in {"email", "domain", "target", "address"}:
            continue  # header row
        reason = (row[1].strip() if len(row) > 1 else "") or "csv_upload"
        if not target:
            skipped += 1
            continue
        is_email = "@" in target
        kwargs = dict(owner_email=subj.sub, source="csv_upload", reason=reason)
        if is_email:
            kwargs["email"] = target
        else:
            kwargs["domain"] = target.lstrip(".")
        rec = SuppressionEntry(**kwargs)
        session.add(rec)
        try:
            await session.flush()
            added += 1
        except IntegrityError:
            await session.rollback()
            skipped += 1
    await session.commit()
    return {"added": added, "skipped": skipped}
