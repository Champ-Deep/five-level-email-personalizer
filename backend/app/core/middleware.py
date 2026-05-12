"""HTTP middleware: Request-ID propagation and structured error responses.

Every request gets a request_id (extracted from `X-Request-ID` header or
generated). The same value is echoed on the response and attached to
`request.state.request_id` for handlers + log records.
"""

from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = rid
        try:
            response = await call_next(request)
        except Exception:
            logging.exception("Unhandled exception in request %s", rid)
            raise
        response.headers[REQUEST_ID_HEADER] = rid
        return response


def problem_response(status_code: int, title: str, detail: str | None = None, request_id: str | None = None) -> dict:
    """RFC 7807-shaped error body. Use everywhere we return errors."""
    body = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
    }
    if detail:
        body["detail"] = detail
    if request_id:
        body["request_id"] = request_id
    return body
