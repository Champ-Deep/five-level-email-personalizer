from fastapi import APIRouter, HTTPException, status

from app.services.brand_service import BrandConfig, BrandNotFound, list_brands, load_brand

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("", response_model=list[str])
async def list_brand_slugs() -> list[str]:
    return list_brands()


@router.get("/{slug}", response_model=BrandConfig)
async def get_brand(slug: str) -> BrandConfig:
    try:
        return load_brand(slug)
    except BrandNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
