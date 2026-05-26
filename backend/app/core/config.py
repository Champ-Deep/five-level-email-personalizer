from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout: int = 120
    # Default generation model. Open-weight by policy (Champions Group standard).
    # Proprietary models (Anthropic, OpenAI) are only used by the eval harness
    # as an external quality benchmark — never in the product path.
    openrouter_default_model: str = "deepseek/deepseek-v4-pro"
    # Research model. Perplexity Sonar is closed-source but is the only viable
    # web-search-native option on OpenRouter today; flagged here as an exception.
    openrouter_research_model: str = "perplexity/sonar-pro"
    anthropic_api_key: str = ""

    # Three model slots for the variation pipeline. Each generates a full
    # 5-layer-fused email; the UI shows all 3 side-by-side so the user picks.
    # ALL THREE must be open-weight models. Override per environment via .env.
    variation_a_model: str = "deepseek/deepseek-v4-pro"
    variation_a_label: str = "DeepSeek V4 Pro"
    variation_b_model: str = "meta-llama/llama-4-maverick"
    variation_b_label: str = "Llama 4 Maverick"
    variation_c_model: str = "mistralai/mistral-large-2512"
    variation_c_label: str = "Mistral Large 3"

    # Storage
    database_url: str = "postgresql+asyncpg://personalizer:personalizer@localhost:5432/personalizer"
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"

    # Clerk — user-facing auth lives in Clerk's hosted dashboard. The backend
    # only needs to verify Clerk session tokens against the issuer's JWKS.
    # CLERK_ISSUER is optional but **strongly recommended** in production:
    # without it any Clerk-signed token from any other app would also verify.
    # The publishable key is only used to derive the issuer when CLERK_ISSUER
    # is empty (Clerk encodes it: `pk_test_<base64(domain)>...`).
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_issuer: str = ""

    # Public lead-magnet tokens (NOT user auth — just a "this IP supplied
    # an email" signal that bumps the anonymous rate limit). HMAC-signed
    # with this secret; nothing sensitive lives in them.
    lead_token_secret: str = "lead-token-dev-secret"
    lead_token_ttl_hours: int = 24

    # Rate limits
    rate_limit_anon_per_day: int = 1
    rate_limit_lead_per_day: int = 20

    # Brands
    default_brand: str = "lakeb2b"
    brands_dir: str = "data/brands"
    # When set, the backend ignores Host / query / header and always serves
    # this brand. Used on per-brand deploys (e.g. the `lakeb2b` and
    # `span-global` git branches set this in their .env.example).
    locked_brand: str = ""

    # Personalizer
    max_concurrent_levels: int = Field(default=8, description="asyncio semaphore for OpenRouter fan-out")

    # Transactional email (Resend). Optional in the Clerk world — Clerk
    # already mails verification + reset emails for us. Resend stays
    # configured so future transactional flows (e.g. "your batch finished")
    # have a delivery channel without re-plumbing.
    resend_api_key: str = ""
    resend_base_url: str = "https://api.resend.com"
    resend_from: str = "Champ Personalize <noreply@championsmail.com>"

    @property
    def brands_path(self) -> Path:
        path = Path(self.brands_dir)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path

    @property
    def default_variation_specs(self) -> list[dict]:
        return [
            {"slot": "A", "model": self.variation_a_model, "label": self.variation_a_label},
            {"slot": "B", "model": self.variation_b_model, "label": self.variation_b_label},
            {"slot": "C", "model": self.variation_c_model, "label": self.variation_c_label},
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
