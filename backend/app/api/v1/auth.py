"""Auth endpoints.

After the Clerk migration the **frontend** owns sign-in / sign-up /
password / sign-out via Clerk's hosted components. The backend keeps a
single endpoint, `/v1/auth/me`, that turns a verified Clerk session
token into the user-shaped JSON the rest of the app expects.

The old endpoints (`/signup`, `/login`, `/password`, `/logout`,
`/forgot-password`, `/reset-password`) now respond **410 Gone** with a
pointer to Clerk so any stale client knows what happened.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import TokenSubject, require_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class UserOut(BaseModel):
    id: str
    email: str | None
    name: str | None
    role: str
    created_at: datetime


@router.get("/me", response_model=UserOut)
async def me(subj: TokenSubject = Depends(require_user)) -> UserOut:
    """Return the currently authenticated principal.

    For Clerk-signed sessions this is derived from the verified JWT
    claims. For API keys it returns the key's owner. Either way the
    shape stays the same so the React app doesn't branch on auth type.
    """
    return UserOut(
        id=subj.sub,
        email=subj.email,
        name=None,
        role="api_key" if subj.kind == "api_key" else "user",
        created_at=datetime.now(timezone.utc),
    )


_GONE_DETAIL = (
    "This endpoint was retired with the Clerk migration. Sign in via the "
    "Clerk widget in the frontend (or use an API key for programmatic access)."
)


def _gone() -> None:  # pragma: no cover — just sugar
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_GONE_DETAIL)


@router.post("/signup", status_code=410)
async def _retired_signup() -> None: _gone()


@router.post("/login", status_code=410)
async def _retired_login() -> None: _gone()


@router.post("/password", status_code=410)
async def _retired_password() -> None: _gone()


@router.post("/forgot-password", status_code=410)
async def _retired_forgot() -> None: _gone()


@router.post("/reset-password", status_code=410)
async def _retired_reset() -> None: _gone()


@router.post("/logout", status_code=204)
async def logout() -> None:
    """No-op kept so the frontend's sign-out button can call it
    unconditionally while the Clerk session is being torn down. Clerk
    handles actual session revocation client-side via `signOut()`."""
    return None
