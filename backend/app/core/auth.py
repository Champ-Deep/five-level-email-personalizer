from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


class TokenSubject(BaseModel):
    sub: str
    kind: Literal["lead", "user"]
    brand: Optional[str] = None


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


async def optional_subject(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> Optional[TokenSubject]:
    if creds is None:
        request.state.auth_subject = None
        return None
    subj = decode_token(creds.credentials)
    request.state.auth_subject = subj.sub
    return subj


async def require_user(subj: Optional[TokenSubject] = Depends(optional_subject)) -> TokenSubject:
    if subj is None or subj.kind != "user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User auth required")
    return subj
