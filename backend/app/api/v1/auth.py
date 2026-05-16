from __future__ import annotations

import uuid
from datetime import datetime

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
from app.db.models import User
from app.db.postgres import get_session

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
