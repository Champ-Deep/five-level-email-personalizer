import re
import pytest

from app.services.brand_service import list_brands, load_brand

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@pytest.mark.parametrize("slug", ["lakeb2b", "ampliz", "champions-group", "span-global"])
def test_each_brand_loads_with_required_tokens(slug):
    brand = load_brand(slug)
    assert brand.slug == slug
    assert brand.name
    assert brand.default_model
    for field in ("brand_accent", "brand_accent_soft", "brand_ink", "brand_muted", "brand_rule", "brand_bg"):
        value = getattr(brand.tokens, field)
        assert HEX_RE.match(value), f"{slug}.{field}={value!r} is not a 7-char hex"


def test_default_brand_fallback_when_unknown_slug():
    brand = load_brand("non-existent-brand-xyz")
    assert brand.slug == "non-existent-brand-xyz"
    assert brand.name


def test_list_brands_excludes_default_and_returns_known_slugs():
    slugs = list_brands()
    assert "lakeb2b" in slugs
    assert "ampliz" in slugs
    assert "champions-group" in slugs
    assert "span-global" in slugs
    assert all(not s.startswith("_") for s in slugs)
