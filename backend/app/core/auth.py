import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)

API_KEY_PREFIX = "ck_live_"


class TokenSubject(BaseModel):
    sub: str
    kind: Literal["lead", "user", "api_key"]
    brand: Optional[str] = None
    api_key_id: Optional[str] = None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_token(sub: str, kind: Literal["lead", "user"], brand: Optional[str] = None) -> str:
    s = get_settings()
    ttl_hours = s.jwt_lead_ttl_hours if kind == "lead" else s.jwt_user_ttl_hours
    payload = {
        "sub": sub,
        "kind": kind,
        "brand": brand,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> TokenSubject:
    s = get_settings()
    try:
        data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        return TokenSubject(sub=data["sub"], kind=data["kind"], brand=data.get("brand"))
    except (JWTError, KeyError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, hash). Show full_key to the user ONCE."""
    raw = secrets.token_urlsafe(32)
    full = f"{API_KEY_PREFIX}{raw}"
    prefix = raw[:8]
    return full, prefix, hash_password(full)


async def _verify_api_key(token: str, session: AsyncSession) -> Optional[TokenSubject]:
    if not token.startswith(API_KEY_PREFIX):
        return None
    raw = token[len(API_KEY_PREFIX):]
    if len(raw) < 16:
        return None
    prefix = raw[:8]
    from app.db.models import ApiKey  # local import to avoid circular

    result = await session.execute(
        select(ApiKey).where(ApiKey.prefix == prefix, ApiKey.revoked_at.is_(None))
    )
    for candidate in result.scalars():
        if pwd_context.verify(token, candidate.key_hash):
            candidate.last_used_at = datetime.now(timezone.utc)
            await session.commit()
            return TokenSubject(
                sub=candidate.owner_email or str(candidate.id),
                kind="api_key",
                brand=candidate.brand,
                api_key_id=str(candidate.id),
            )
    return None


async def optional_subject(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> Optional[TokenSubject]:
    if creds is None:
        request.state.auth_subject = None
        return None
    token = creds.credentials
    # Try API key first (zero-DB JWT path is the fallback).
    if token.startswith(API_KEY_PREFIX):
        from app.db.postgres import async_session_maker
        async with async_session_maker() as session:
            subj = await _verify_api_key(token, session)
        if subj is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        request.state.auth_subject = subj.sub
        return subj
    subj = decode_token(token)
    request.state.auth_subject = subj.sub
    return subj


async def require_user(subj: Optional[TokenSubject] = Depends(optional_subject)) -> TokenSubject:
    if subj is None or subj.kind not in {"user", "api_key"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User or API key auth required")
    return subj


async def require_api_key(subj: Optional[TokenSubject] = Depends(optional_subject)) -> TokenSubject:
    if subj is None or subj.kind != "api_key":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    return subj
