from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.services.brand_service import BrandConfig, BrandNotFound, list_brands, load_brand

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("", response_model=list[str])
async def list_brand_slugs() -> list[str]:
    settings = get_settings()
    if settings.locked_brand:
        return [settings.locked_brand]
    return list_brands()


@router.get("/_tone_presets", tags=["meta"])
async def get_tone_presets() -> list[dict[str, str]]:
    """Available tone presets for the `tone_preset` field on /v1/personalize."""
    from app.levels.tone_presets import available_presets
    return available_presets()


@router.get("/{slug}", response_model=BrandConfig)
async def get_brand(slug: str) -> BrandConfig:
    settings = get_settings()
    # On locked deploys, any /v1/brands/<x> resolves to the locked brand so
    # the lead-magnet route can't accidentally serve a competitor's palette.
    target = settings.locked_brand or slug
    try:
        return load_brand(target)
    except BrandNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
