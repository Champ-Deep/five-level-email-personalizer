"""Authentication layer.

The user-facing auth is delegated to **Clerk** (clerk.com). The frontend
holds the session; on every request the React app sends the Clerk session
JWT as `Authorization: Bearer <jwt>` and this module verifies it against
Clerk's JWKS endpoint.

Programmatic callers (CI scripts, ChampMail, ChampIQ, etc.) use long-lived
**API keys** instead — those still hash to the local `api_keys` table.

The `TokenSubject` shape is preserved across the Clerk migration so all
14 call sites (history, senders, integrations, suppressions, icp,
replies, jobs, personalize, api-keys, webhooks, etc.) didn't have to
change typing. Only the *origin* of the subject changed: instead of a
locally-signed HS256 JWT keyed by a UUID user_id, `subj.sub` is now
either a Clerk `user_xxxx` ID (kind="user") or the API key's owner email
(kind="api_key").
"""
from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Literal, Optional

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

log = logging.getLogger(__name__)

# API keys are hashed with pbkdf2 (Clerk sessions are RS256 JWTs, separate path).
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)

API_KEY_PREFIX = "ck_live_"

# JWKS cache: one fetch per Clerk instance per `_JWKS_TTL` seconds. Clerk's
# signing keys rotate roughly yearly, so a 10-minute cache is conservative
# without making every request fan out to Clerk.
_JWKS_TTL = 600
_jwks_cache: dict[str, tuple[float, dict]] = {}


class TokenSubject(BaseModel):
    sub: str
    # "user"     -> verified Clerk session JWT (sub = clerk user_xxxx)
    # "api_key"  -> long-lived API key (sub = owner_email)
    # "lead"     -> public lead-magnet token (sub = lead UUID, brand-scoped)
    kind: Literal["user", "api_key", "lead"]
    brand: Optional[str] = None
    api_key_id: Optional[str] = None
    # The verified Clerk principal's email (when present in the JWT claims).
    # Used as the `owner_email` label on history/jobs/integrations.
    email: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────
# Clerk session JWT verification
# ─────────────────────────────────────────────────────────────────────


def _issuer_from_token(token: str) -> str:
    """Pull the `iss` claim from an unverified JWT.

    Clerk session JWTs carry their own issuer (e.g.
    `https://touched-pelican-12.clerk.accounts.dev`). The JWKS lives at
    `{iss}/.well-known/jwks.json`. We trust the issuer only AFTER signature
    verification, but we *route* the JWKS fetch by it — same pattern Clerk's
    own SDKs use.
    """
    try:
        claims = jwt.get_unverified_claims(token)
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid Clerk token") from e
    iss = claims.get("iss")
    if not iss or not isinstance(iss, str):
        raise HTTPException(status_code=401, detail="Clerk token missing `iss` claim")
    return iss.rstrip("/")


def _fetch_jwks(issuer: str) -> dict:
    """Fetch+cache the JWKS for a given Clerk issuer."""
    now = time.time()
    cached = _jwks_cache.get(issuer)
    if cached and (now - cached[0]) < _JWKS_TTL:
        return cached[1]
    url = f"{issuer}/.well-known/jwks.json"
    try:
        r = httpx.get(url, timeout=5.0)
        r.raise_for_status()
        jwks = r.json()
    except (httpx.HTTPError, ValueError) as e:
        # If we *had* a stale cache, keep using it rather than 503'ing the
        # whole app on a transient network blip.
        if cached:
            log.warning("JWKS fetch failed (%s) — using stale cache", e)
            return cached[1]
        raise HTTPException(status_code=503, detail="Cannot reach Clerk JWKS") from e
    _jwks_cache[issuer] = (now, jwks)
    return jwks


def _verify_clerk_jwt(token: str) -> TokenSubject:
    """Verify a Clerk session JWT against the issuer's JWKS, return a
    TokenSubject. Raises 401 on any verification failure.
    """
    settings = get_settings()
    iss = _issuer_from_token(token)

    # Optional pinned-issuer guard: when the operator has set CLERK_ISSUER
    # in the env, reject tokens from any other Clerk instance. This stops a
    # signed-but-foreign token from a different Clerk app from being honored
    # against our DB — and it's how production should run.
    if settings.clerk_issuer and iss != settings.clerk_issuer.rstrip("/"):
        raise HTTPException(status_code=401, detail="Clerk token issuer mismatch")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid Clerk token header") from e

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Clerk token missing `kid`")

    jwks = _fetch_jwks(iss)
    matching = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if matching is None:
        # The key might have rotated since our last cache hit — bust and retry once.
        _jwks_cache.pop(iss, None)
        jwks = _fetch_jwks(iss)
        matching = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if matching is None:
        raise HTTPException(status_code=401, detail="Clerk signing key not found")

    try:
        public_key = jwk.construct(matching)
        payload = jwt.decode(
            token,
            public_key.to_pem().decode("utf-8") if hasattr(public_key, "to_pem") else matching,
            algorithms=[matching.get("alg", "RS256")],
            # Clerk session JWTs don't carry an `aud` claim by default; skip
            # audience verification rather than fail every request.
            options={"verify_aud": False},
            issuer=iss,
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Clerk token: {e}") from e

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Clerk token missing `sub`")

    # Clerk doesn't put the email in the default session token. The
    # frontend can request a `email_primary` template that adds it, but
    # we don't require it — falling back to None is fine.
    email = payload.get("email") or payload.get("primary_email_address")

    return TokenSubject(sub=str(sub), kind="user", email=email, brand=None)


# ─────────────────────────────────────────────────────────────────────
# API key path (unchanged from pre-Clerk; programmatic clients use these)
# ─────────────────────────────────────────────────────────────────────


def hash_api_key(token: str) -> str:
    """Used by /v1/api-keys when minting a fresh key."""
    return pwd_context.hash(token)


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, hash). Show full_key to the user ONCE."""
    raw = secrets.token_urlsafe(32)
    full = f"{API_KEY_PREFIX}{raw}"
    prefix = raw[:8]
    return full, prefix, pwd_context.hash(full)


# ─────────────────────────────────────────────────────────────────────
# Lead-magnet tokens (HMAC, not user auth — see TokenSubject docstring)
# ─────────────────────────────────────────────────────────────────────


LEAD_TOKEN_PREFIX = "lead_"


def create_lead_token(*, sub: str, brand: str) -> str:
    """Mint a short-lived HMAC lead token. Plain string format
    `lead_<base64(payload)>_<sig>`. No PII inside the payload."""
    import base64
    import hmac
    import hashlib
    import json
    from datetime import timedelta as _td

    s = get_settings()
    payload = {
        "sub": sub,
        "brand": brand,
        "exp": int((datetime.now(timezone.utc) + _td(hours=s.lead_token_ttl_hours)).timestamp()),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = hmac.new(s.lead_token_secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{LEAD_TOKEN_PREFIX}{body}.{sig}"


def create_token(*, sub: str, kind: str, brand: Optional[str] = None) -> str:
    """Back-compat shim. Only `kind="lead"` is supported now — user
    auth comes from Clerk and api keys come from `generate_api_key()`.
    """
    if kind != "lead":
        raise ValueError(f"create_token only supports kind='lead' now; got {kind!r}")
    return create_lead_token(sub=sub, brand=brand or "")


def _verify_lead_token(token: str) -> Optional[TokenSubject]:
    import base64
    import hmac
    import hashlib
    import json

    if not token.startswith(LEAD_TOKEN_PREFIX):
        return None
    raw = token[len(LEAD_TOKEN_PREFIX):]
    if "." not in raw:
        return None
    body, sig = raw.rsplit(".", 1)
    s = get_settings()
    expected = hmac.new(s.lead_token_secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=401, detail="Invalid lead token")
    try:
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=401, detail="Malformed lead token") from e
    if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=401, detail="Lead token expired")
    return TokenSubject(sub=str(payload.get("sub")), kind="lead", brand=payload.get("brand"))


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
                email=candidate.owner_email,
            )
    return None


# ─────────────────────────────────────────────────────────────────────
# FastAPI dependencies (interface unchanged from the JWT era)
# ─────────────────────────────────────────────────────────────────────


async def optional_subject(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> Optional[TokenSubject]:
    if creds is None:
        request.state.auth_subject = None
        return None
    token = creds.credentials
    # Lead-magnet token (public, low-trust)
    if token.startswith(LEAD_TOKEN_PREFIX):
        subj = _verify_lead_token(token)
        if subj is not None:
            request.state.auth_subject = subj.sub
            return subj
    # API key path
    if token.startswith(API_KEY_PREFIX):
        from app.db.postgres import async_session_maker
        async with async_session_maker() as session:
            subj = await _verify_api_key(token, session)
        if subj is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        request.state.auth_subject = subj.sub
        return subj
    # Clerk session JWT path
    subj = _verify_clerk_jwt(token)
    request.state.auth_subject = subj.sub
    return subj


async def require_user(subj: Optional[TokenSubject] = Depends(optional_subject)) -> TokenSubject:
    if subj is None or subj.kind not in {"user", "api_key"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in or use an API key.",
        )
    return subj


async def require_api_key(subj: Optional[TokenSubject] = Depends(optional_subject)) -> TokenSubject:
    if subj is None or subj.kind != "api_key":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    return subj
