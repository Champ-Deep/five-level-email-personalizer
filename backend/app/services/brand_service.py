from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from app.core.config import get_settings


class BrandTokens(BaseModel):
    brand_accent: str
    brand_accent_soft: str
    brand_ink: str
    brand_muted: str
    brand_rule: str
    brand_bg: str
    font_primary: str = "Inter"
    font_secondary: str = "Inter"
    font_google_url: Optional[str] = None


class BrandSenderDefault(BaseModel):
    name: Optional[str] = None
    company: str
    offer: str


class BrandConfig(BaseModel):
    slug: str
    name: str
    tagline: str = ""
    logo_url: Optional[str] = None
    tokens: BrandTokens
    sender_default: BrandSenderDefault
    system_prompt_addendum: str = ""
    default_model: str = "anthropic/claude-sonnet-4.5"
    research_model: Optional[str] = None
    voice_keywords: list[str] = Field(default_factory=list)


class BrandNotFound(LookupError): ...


@lru_cache(maxsize=64)
def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_brand(slug: str) -> BrandConfig:
    settings = get_settings()
    brands_dir = settings.brands_path
    candidate = brands_dir / f"{slug}.yaml"
    if not candidate.exists():
        fallback = brands_dir / "_default.yaml"
        if not fallback.exists():
            raise BrandNotFound(f"No brand config for '{slug}' and no _default.yaml")
        data = _load_yaml(fallback)
        data["slug"] = slug
        data["name"] = data.get("name", slug.title())
        return BrandConfig(**data)
    return BrandConfig(**_load_yaml(candidate))


def list_brands() -> list[str]:
    brands_dir = get_settings().brands_path
    if not brands_dir.exists():
        return []
    return sorted(
        p.stem for p in brands_dir.glob("*.yaml") if not p.stem.startswith("_")
    )
