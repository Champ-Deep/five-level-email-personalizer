from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenSubject, require_user
from app.db.models import IntegrationCredential
from app.db.postgres import get_session
from app.services.connectors.registry import get_connector, list_providers
from app.services.secrets import decrypt_config, encrypt_config

router = APIRouter(prefix="/integrations", tags=["integrations"])


class CreateIntegration(BaseModel):
    provider: Literal["instantly", "champmail", "champiq"]
    label: str = Field(..., min_length=1, max_length=120)
    config: dict[str, Any]  # plaintext fields; encrypted at rest
    is_default: bool = False


class UpdateIntegration(BaseModel):
    label: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    is_default: Optional[bool] = None


class IntegrationOut(BaseModel):
    id: str
    provider: str
    label: str
    is_default: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    # Surface non-sensitive config fields (anything that doesn't end in
    # _key / _secret / _token / _password) so the UI can show what's set.
    config_preview: dict[str, str]


SENSITIVE_SUFFIXES = ("_key", "_secret", "_token", "_password")


def _preview(config: dict[str, Any]) -> dict[str, str]:
    """Mask sensitive fields to a "configured · ********" placeholder."""
    out: dict[str, str] = {}
    for k, v in config.items():
        s = str(v) if v is not None else ""
        if any(k.lower().endswith(suf) for suf in SENSITIVE_SUFFIXES):
            out[k] = "configured · " + ("•" * 8) + (s[-4:] if len(s) >= 4 else "")
        else:
            out[k] = s[:80]
    return out


def _to_out(rec: IntegrationCredential) -> IntegrationOut:
    return IntegrationOut(
        id=str(rec.id), provider=rec.provider, label=rec.label,
        is_default=rec.is_default, last_used_at=rec.last_used_at, created_at=rec.created_at,
        config_preview=_preview(decrypt_config(rec.config_encrypted)),
    )


def _validate_required(provider: str, config: dict[str, Any]) -> None:
    info = get_connector(provider)
    missing = [k for k in info["required"] if not config.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required field(s) for {provider}: {', '.join(missing)}")


@router.get("/providers")
async def list_supported_providers() -> list[dict[str, Any]]:
    return list_providers()


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> list[IntegrationOut]:
    rows = (
        await session.execute(
            select(IntegrationCredential)
            .where(IntegrationCredential.owner_email == subj.sub)
            .order_by(IntegrationCredential.is_default.desc(), IntegrationCredential.created_at.desc())
        )
    ).scalars().all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=IntegrationOut, status_code=201)
async def create_integration(
    body: CreateIntegration,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> IntegrationOut:
    _validate_required(body.provider, body.config)
    if body.is_default:
        await session.execute(
            update(IntegrationCredential)
            .where(
                IntegrationCredential.owner_email == subj.sub,
                IntegrationCredential.provider == body.provider,
            )
            .values(is_default=False)
        )
    rec = IntegrationCredential(
        owner_email=subj.sub, provider=body.provider, label=body.label,
        config_encrypted=encrypt_config(body.config), is_default=body.is_default,
    )
    session.add(rec)
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Label conflict: {e}") from e
    await session.refresh(rec)
    return _to_out(rec)


@router.patch("/{integration_id}", response_model=IntegrationOut)
async def update_integration(
    integration_id: str,
    body: UpdateIntegration,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> IntegrationOut:
    try:
        iid = uuid.UUID(integration_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    rec = (await session.execute(select(IntegrationCredential).where(IntegrationCredential.id == iid))).scalar_one_or_none()
    if rec is None or rec.owner_email != subj.sub:
        raise HTTPException(status_code=404, detail="Integration not found")
    if body.config is not None:
        existing = decrypt_config(rec.config_encrypted)
        merged = {**existing, **body.config}  # patch-style merge
        _validate_required(rec.provider, merged)
        rec.config_encrypted = encrypt_config(merged)
    if body.label is not None:
        rec.label = body.label
    if body.is_default is True and not rec.is_default:
        await session.execute(
            update(IntegrationCredential)
            .where(
                IntegrationCredential.owner_email == subj.sub,
                IntegrationCredential.provider == rec.provider,
            )
            .values(is_default=False)
        )
        rec.is_default = True
    await session.commit()
    return _to_out(rec)


@router.delete("/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        iid = uuid.UUID(integration_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    rec = (await session.execute(select(IntegrationCredential).where(IntegrationCredential.id == iid))).scalar_one_or_none()
    if rec is None or rec.owner_email != subj.sub:
        raise HTTPException(status_code=404, detail="Integration not found")
    await session.delete(rec)
    await session.commit()


@router.post("/{integration_id}/healthcheck")
async def healthcheck_integration(
    integration_id: str,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        iid = uuid.UUID(integration_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    rec = (await session.execute(select(IntegrationCredential).where(IntegrationCredential.id == iid))).scalar_one_or_none()
    if rec is None or rec.owner_email != subj.sub:
        raise HTTPException(status_code=404, detail="Integration not found")
    info = get_connector(rec.provider)
    config = decrypt_config(rec.config_encrypted)
    ok, message = await info["healthcheck"](config)
    return {"ok": ok, "message": message}
