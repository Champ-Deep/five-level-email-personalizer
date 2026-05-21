"""Thin wrapper around the Resend transactional-email API.

Why Resend (not SES / Postmark / Mailgun)? It has the lowest-friction
deliverability story for product-led emails, an obvious dashboard for
non-engineers, and a one-endpoint HTTP API — no SDK to pin to a Python
version.

The wrapper is deliberately tiny: one async method, `send_email()`.
Everything caller-side (subject, HTML, text, recipient list) is built
in the route that originates the message so we don't grow a god-class
of template helpers in here. If a second email type lands (welcome,
trial-ending, etc.) we can lift the obvious helpers up at that point.

If `RESEND_API_KEY` is unset, `send_email()` logs the message body to
stderr instead of calling Resend. That lets local dev / Railway preview
environments run the forgot-password flow without burning a real email
send — the reset link still appears in the server logs.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)


class EmailError(Exception):
    """Raised when Resend returns a non-2xx. Caller decides whether to
    bubble it to the user or swallow + log (the forgot-password path
    deliberately swallows, to avoid leaking whether an account exists)."""


async def send_email(
    *,
    to: str | list[str],
    subject: str,
    html: str,
    text: Optional[str] = None,
    from_addr: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> Optional[str]:
    """Send a transactional email via Resend. Returns the Resend message
    id on success, or None when the service is unconfigured (dev mode).

    Recipients can be a single address or a list. We always pass it as a
    list to Resend so the API behaves consistently.
    """
    settings = get_settings()
    to_list = [to] if isinstance(to, str) else list(to)

    if not settings.resend_api_key:
        # Dev mode — log the email instead of sending. The reset link
        # ends up in the dev console so you can keep iterating without
        # a Resend account.
        log.warning(
            "[email-dev-mode] would send → %s | subject=%r\n%s",
            ", ".join(to_list), subject, text or html,
        )
        return None

    payload: dict = {
        "from": from_addr or settings.resend_from,
        "to": to_list,
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    if reply_to:
        payload["reply_to"] = reply_to

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{settings.resend_base_url.rstrip('/')}/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json=payload,
        )
    if r.status_code >= 300:
        raise EmailError(f"resend_failed status={r.status_code} body={r.text[:400]}")
    data = r.json()
    return data.get("id")
