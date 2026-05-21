from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1 import api_keys as api_key_routes
from app.api.v1 import auth as auth_routes
from app.api.v1 import brands as brand_routes
from app.api.v1 import history as history_routes
from app.api.v1 import icp as icp_routes
from app.api.v1 import integrations as integration_routes
from app.api.v1 import jobs as job_routes
from app.api.v1 import leads as lead_routes
from app.api.v1 import personalize as personalize_routes
from app.api.v1 import replies as reply_routes
from app.api.v1 import senders as sender_routes
from app.api.v1 import suppressions as suppression_routes
from app.api.v1 import webhooks as webhook_routes
from app.core.config import get_settings
from app.core.middleware import RequestIdMiddleware
from app.core.rate_limit import limiter
from app.db.postgres import init_db, dispose_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # DB is only needed by /leads, /auth, /personalize/batch, /jobs. Lead-magnet
    # and single /personalize work without it — degrade gracefully so the
    # frontend is testable before infra is set up.
    import logging
    try:
        await init_db()
    except Exception as e:
        logging.warning("Skipping DB init (Postgres unreachable): %s", e)
    yield
    try:
        await dispose_engine()
    except Exception:
        pass


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
    app.add_middleware(RequestIdMiddleware)
    # FRONTEND_BASE_URL may be a single URL or comma-separated. Useful on
    # Railway where typically you have <service>.up.railway.app plus a
    # custom domain to allow. We also auto-allow any *.up.railway.app
    # origin via a regex fallback so a fresh deploy isn't bricked the
    # moment someone forgets to set the var.
    allowed_origins = [
        o.strip() for o in (settings.frontend_base_url or "").split(",") if o.strip()
    ]
    # Browsers reject `allow_origins=["*"]` + `allow_credentials=True`.
    # If we ended up with the wildcard, drop credentials so preflight
    # still works (auth is via Bearer header, not cookies, so credentials
    # aren't actually needed — but Authorization headers do still flow).
    use_wildcard = not allowed_origins or "*" in allowed_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if use_wildcard else allowed_origins,
        # Permit any Railway preview / production host. Belt + suspenders
        # so an unset FRONTEND_BASE_URL doesn't black-hole sign-in.
        allow_origin_regex=r"^https?://[a-z0-9-]+\.up\.railway\.app$" if not use_wildcard else None,
        allow_credentials=not use_wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    app.include_router(personalize_routes.router, prefix="/v1")
    app.include_router(brand_routes.router, prefix="/v1")
    app.include_router(lead_routes.router, prefix="/v1")
    app.include_router(job_routes.router, prefix="/v1")
    app.include_router(auth_routes.router, prefix="/v1")
    app.include_router(api_key_routes.router, prefix="/v1")
    app.include_router(webhook_routes.router, prefix="/v1")
    app.include_router(history_routes.router, prefix="/v1")
    app.include_router(sender_routes.router, prefix="/v1")
    app.include_router(integration_routes.router, prefix="/v1")
    app.include_router(suppression_routes.router, prefix="/v1")
    app.include_router(icp_routes.router, prefix="/v1")
    app.include_router(reply_routes.router, prefix="/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def root():
        """Friendly landing page for anyone who pokes the API URL directly.

        The actual UI lives on the separate Frontend service. This just
        confirms the API is alive and points the user at the docs.
        """
        return {
            "service": "Five-Level Email Personalizer",
            "version": "0.1.0",
            "status": "ok",
            "docs": "/docs",
            "health": "/health",
            "api_root": "/v1",
            "note": "This is the API service. The user-facing app is the Frontend service.",
        }

    return app


app = create_app()
