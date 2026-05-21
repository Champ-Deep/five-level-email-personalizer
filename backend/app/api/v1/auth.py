from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    TokenSubject,
    create_token,
    hash_password,
    require_user,
    revoke_token,
    verify_password,
)
from app.core.config import get_settings
from app.db.models import PasswordResetToken, User
from app.db.postgres import get_session
from app.services.email_service import EmailError, send_email

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    name: str | None = None
    password: str = Field(..., min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    email: str
    name: str | None = None


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=200)


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    existing = await session.execute(select(User).where(User.email == str(body.email).lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=str(body.email).lower(),
        name=body.name,
        password_hash=hash_password(body.password),
        role="user",
    )
    session.add(user)
    await session.commit()
    return TokenResponse(token=create_token(str(user.id), kind="user"), email=user.email, name=user.name)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == str(body.email).lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(token=create_token(str(user.id), kind="user"), email=user.email, name=user.name)


@router.get("/me", response_model=UserOut)
async def me(
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """Return the currently authenticated user's profile.

    Works for both user JWTs and API keys. For API keys, returns the
    profile of the user who owns the key.
    """
    email = subj.sub if subj.kind == "user" else None
    if subj.kind == "user":
        # subj.sub is the user UUID; look up by id
        try:
            uid = uuid.UUID(subj.sub)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user token")
        result = await session.execute(select(User).where(User.id == uid))
    else:
        # API key: sub is the owner_email
        result = await session.execute(select(User).where(User.email == subj.sub))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        created_at=user.created_at,
    )


@router.post("/password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    subj: TokenSubject = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    if subj.kind != "user":
        raise HTTPException(status_code=403, detail="API keys can't change a user's password — use a user JWT")
    try:
        uid = uuid.UUID(subj.sub)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user token")
    result = await session.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is wrong")
    user.password_hash = hash_password(body.new_password)
    await session.commit()


@router.post("/logout", status_code=204)
async def logout(subj: TokenSubject = Depends(require_user)) -> None:
    """Server-side revoke the JWT (adds the token's fingerprint to a Redis
    blacklist for its remaining TTL). Clients should also drop the token
    from localStorage.
    """
    if subj.raw_token:
        await revoke_token(subj.raw_token)


# ─────────────────────────────────────────────────────────────────────
# Forgot / reset password
#
# We intentionally return the same 202 whether or not the email exists,
# so an attacker can't enumerate accounts by trying random emails. The
# actual reset link only goes to a real, registered address.
# ─────────────────────────────────────────────────────────────────────


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)


def _hash_reset_token(raw: str) -> str:
    """SHA-256 fingerprint of a reset token. We only persist the hash so
    a leaked DB row can't be replayed against an account — the only path
    to a reset is the link mailed to the user."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@router.post("/forgot-password", status_code=202)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mail a single-use, 60-min-TTL reset link to the user.

    Always returns 202 — even when the email isn't on file — so that a
    drive-by can't probe for valid accounts.
    """
    settings = get_settings()
    result = await session.execute(select(User).where(User.email == str(body.email).lower()))
    user = result.scalar_one_or_none()
    if user is not None:
        raw_token = secrets.token_urlsafe(32)
        token_row = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_reset_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_ttl_minutes),
        )
        session.add(token_row)
        await session.commit()
        # The link lives on the frontend (which renders the reset form
        # and calls /v1/auth/reset-password on submit). `frontend_base_url`
        # may be comma-separated for CORS purposes — take the first entry.
        frontend = (settings.frontend_base_url or "").split(",")[0].strip().rstrip("/") or "http://localhost:5173"
        reset_url = f"{frontend}/reset-password?token={raw_token}"
        try:
            await send_email(
                to=user.email,
                subject="Reset your Champ Personalize password",
                html=_reset_email_html(user.name or "there", reset_url, settings.password_reset_ttl_minutes),
                text=_reset_email_text(user.name or "there", reset_url, settings.password_reset_ttl_minutes),
            )
        except EmailError as e:
            # Don't leak Resend failures to the caller — they look the
            # same as "email not on file" by design.
            log.error("Password-reset email failed for user_id=%s: %s", user.id, e)
    return {"status": "ok"}


@router.post("/reset-password", response_model=TokenResponse)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Consume a reset token and set a new password. Returns a fresh
    user JWT so the frontend can drop them straight into the app without
    a separate login round-trip."""
    token_hash = _hash_reset_token(body.token)
    result = await session.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    if row.used_at is not None:
        raise HTTPException(status_code=400, detail="This reset link has already been used")
    now = datetime.now(timezone.utc)
    # `expires_at` is timezone-aware coming back from Postgres TIMESTAMPTZ.
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status_code=400, detail="This reset link has expired")
    user_result = await session.execute(select(User).where(User.id == row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    user.password_hash = hash_password(body.new_password)
    row.used_at = now
    await session.commit()
    return TokenResponse(
        token=create_token(str(user.id), kind="user"),
        email=user.email,
        name=user.name,
    )


# ───── Email templates (kept inline; if we add a third template they
#       graduate to a `templates/email/` folder with Jinja). ───────────


def _reset_email_html(first_name: str, reset_url: str, ttl_min: int) -> str:
    return f"""<!doctype html><html><body style="font-family:Inter,Arial,sans-serif;background:#f7f7f8;padding:24px;color:#0a0a0a">
  <div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #e5e5e8;border-radius:14px;padding:28px">
    <h1 style="font-size:18px;margin:0 0 12px;font-weight:800">Reset your password</h1>
    <p style="margin:0 0 16px;color:#3a3a44">Hi {first_name}, click the button below to choose a new password. This link expires in {ttl_min} minutes and can only be used once.</p>
    <p style="margin:24px 0"><a href="{reset_url}" style="display:inline-block;background:#0a0a0a;color:#fff;text-decoration:none;padding:12px 20px;border-radius:10px;font-weight:700">Reset password</a></p>
    <p style="margin:0 0 8px;color:#5c5c66;font-size:12px">If the button doesn't work, paste this URL into your browser:</p>
    <p style="margin:0;color:#5c5c66;font-size:12px;word-break:break-all">{reset_url}</p>
    <hr style="border:none;border-top:1px solid #e5e5e8;margin:24px 0">
    <p style="margin:0;color:#5c5c66;font-size:11px">Didn't request this? You can safely ignore the email. Your password stays the same until somebody actually uses a link.</p>
  </div>
</body></html>"""


def _reset_email_text(first_name: str, reset_url: str, ttl_min: int) -> str:
    return (
        f"Hi {first_name},\n\n"
        f"Use this link to reset your Champ Personalize password (expires in {ttl_min} minutes):\n\n"
        f"{reset_url}\n\n"
        "If you didn't request a reset you can ignore this email — your password stays as it is.\n"
    )
