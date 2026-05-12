from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


def _client_key(request) -> str:
    # If the request carries a lead/user token, use that as the bucket key —
    # otherwise fall back to remote IP for true anonymous traffic.
    token = getattr(request.state, "auth_subject", None)
    if token:
        return f"sub:{token}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_client_key)


def per_day_anon() -> str:
    s = get_settings()
    return f"{s.rate_limit_anon_per_day}/day"


def per_day_lead() -> str:
    s = get_settings()
    return f"{s.rate_limit_lead_per_day}/day"
