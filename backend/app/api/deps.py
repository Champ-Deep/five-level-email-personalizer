from __future__ import annotations

from fastapi import HTTPException, Query, Request, status

from app.core.config import get_settings
from app.services.brand_service import BrandConfig, BrandNotFound, load_brand


def resolve_brand(
    request: Request,
    brand: str | None = Query(default=None, description="Brand slug; overrides Host/X-Brand"),
) -> BrandConfig:
    """Resolve brand from explicit ?brand=, then `X-Brand`, then `Host` subdomain, then default."""
    slug = brand or request.headers.get("X-Brand")
    if not slug:
        host = (request.headers.get("host") or "").split(":")[0]
        if host and "." in host:
            sub = host.split(".")[0]
            if sub and sub not in {"localhost", "www", "personalize"}:
                slug = sub
    if not slug:
        slug = get_settings().default_brand
    try:
        return load_brand(slug)
    except BrandNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
