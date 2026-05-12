from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1 import auth as auth_routes
from app.api.v1 import brands as brand_routes
from app.api.v1 import jobs as job_routes
from app.api.v1 import leads as lead_routes
from app.api.v1 import personalize as personalize_routes
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.postgres import init_db, dispose_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Five-Level Email Personalizer",
        version="0.1.0",
        description=(
            "White-labelable productisation of the Five Levels of Email Personalization framework "
            "(Industry → Company → Role → Individual → Hyper). All LLM calls go through OpenRouter."
        ),
        lifespan=lifespan,
    )

    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "detail": "Daily limit reached. Sign up to unlock 20 personalizations / day + CSV batch.",
            },
        )

    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(personalize_routes.router, prefix="/v1")
    app.include_router(brand_routes.router, prefix="/v1")
    app.include_router(lead_routes.router, prefix="/v1")
    app.include_router(job_routes.router, prefix="/v1")
    app.include_router(auth_routes.router, prefix="/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
