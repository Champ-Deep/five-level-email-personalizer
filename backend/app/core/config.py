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
    openrouter_default_model: str = "anthropic/claude-sonnet-4.5"
    openrouter_research_model: str = "perplexity/sonar-pro"
    anthropic_api_key: str = ""

    # Storage
    database_url: str = "postgresql+asyncpg://personalizer:personalizer@localhost:5432/personalizer"
    redis_url: str = "redis://localhost:6379/0"

    # App
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_lead_ttl_hours: int = 24
    jwt_user_ttl_hours: int = 24 * 7
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"

    # Rate limits
    rate_limit_anon_per_day: int = 1
    rate_limit_lead_per_day: int = 20

    # Brands
    default_brand: str = "lakeb2b"
    brands_dir: str = "data/brands"

    # Personalizer
    max_concurrent_levels: int = Field(default=8, description="asyncio semaphore for OpenRouter fan-out")

    @property
    def brands_path(self) -> Path:
        path = Path(self.brands_dir)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
