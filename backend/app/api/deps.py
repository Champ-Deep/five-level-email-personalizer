from __future__ import annotations

from fastapi import HTTPException, Query, Request, status

from app.core.config import get_settings
from app.services.brand_service import BrandConfig, BrandNotFound, load_brand


def resolve_brand(
    request: Request,
    brand: str | None = Query(default=None, description="Brand slug; overrides Host/X-Brand"),
) -> BrandConfig:
    """Resolve brand from LOCKED_BRAND (per-brand deploys), then explicit ?brand=,
    then `X-Brand`, then `Host` subdomain, then `default_brand`.
    """
    settings = get_settings()
    if settings.locked_brand:
        try:
            return load_brand(settings.locked_brand)
        except BrandNotFound as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"LOCKED_BRAND points to missing brand '{settings.locked_brand}': {e}") from e

    slug = brand or request.headers.get("X-Brand")
    if not slug:
        host = (request.headers.get("host") or "").split(":")[0]
        if host and "." in host:
            sub = host.split(".")[0]
            if sub and sub not in {"localhost", "www", "personalize"}:
                slug = sub
    if not slug:
        slug = settings.default_brand
    try:
        return load_brand(slug)
    except BrandNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
