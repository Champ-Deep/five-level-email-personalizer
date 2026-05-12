"""Webhook subscription + delivery system.

Pattern (Stripe-style):
- Subscribers register a `target_url` plus a list of event types and a secret
  (returned at create time, used to HMAC-SHA256 sign every delivery).
- When an event fires, we enqueue one `WebhookDelivery` row per matching
  subscription. The arq worker `deliver_webhook` picks it up, POSTs the
  payload, retries up to 5 times with exponential backoff on failure.
- Receivers verify the `X-Champ-Signature` header to authenticate the
  delivery.

Event types currently emitted:
  - `personalize.completed`     (sync POST /v1/personalize)
  - `batch.queued`              (POST /v1/personalize/batch)
  - `batch.prospect.completed`  (per-prospect inside an arq batch job)
  - `batch.completed`           (after the final prospect)
  - `lead.captured`             (POST /v1/leads)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WebhookDelivery, WebhookSubscription
from app.db.postgres import async_session_maker

log = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-Champ-Signature"
EVENT_HEADER = "X-Champ-Event"
DELIVERY_HEADER = "X-Champ-Delivery-Id"

DEFAULT_TIMEOUT = 15.0
MAX_ATTEMPTS = 5


def generate_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


def sign_payload(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def verify_signature(secret: str, body: bytes, signature_header: str) -> bool:
    """Helper for receiver-side verification. Exposed for SDK users."""
    expected = sign_payload(secret, body)
    return hmac.compare_digest(expected, signature_header)


async def emit(
    event_type: str,
    payload: dict[str, Any],
    *,
    brand: Optional[str] = None,
) -> int:
    """Enqueue webhook deliveries for every active subscription that listens
    to this event. Returns the number of deliveries queued.

    Safe to call from any handler — on success, the arq worker handles the
    actual HTTP POST out-of-band. If arq isn't available (e.g. in tests
    without a worker), we degrade silently — the delivery row stays
    `pending` and can be drained later.
    """
    queued = 0
    async with async_session_maker() as session:
        stmt = select(WebhookSubscription).where(WebhookSubscription.active.is_(True))
        if brand is not None:
            stmt = stmt.where(
                (WebhookSubscription.brand == brand) | (WebhookSubscription.brand.is_(None))
            )
        subs = (await session.execute(stmt)).scalars().all()

        for sub in subs:
            if event_type not in (sub.events or []) and "*" not in (sub.events or []):
                continue
            delivery = WebhookDelivery(
                subscription_id=sub.id,
                event_type=event_type,
                target_url=sub.target_url,
                payload=payload,
                status="pending",
                attempts=0,
            )
            session.add(delivery)
            await session.flush()
            await session.commit()
            queued += 1
            await _enqueue_arq_delivery(str(delivery.id))
    return queued


async def _enqueue_arq_delivery(delivery_id: str) -> None:
    """Best-effort enqueue. Logged-and-swallowed if Redis is unavailable."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        from app.core.config import get_settings

        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        try:
            await pool.enqueue_job("deliver_webhook_task", delivery_id)
        finally:
            await pool.close()
    except Exception as e:
        log.warning("Could not enqueue webhook delivery %s: %s", delivery_id, e)


async def deliver_once(delivery_id: str) -> bool:
    """Make one delivery attempt. Returns True on 2xx.

    Called by the arq worker. Updates the WebhookDelivery row with the
    outcome. On non-2xx with attempts < MAX_ATTEMPTS, reschedules itself
    with exponential backoff (1m, 5m, 30m, 2h, 12h).
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(WebhookDelivery).where(WebhookDelivery.id == uuid.UUID(delivery_id))
        )
        delivery = result.scalar_one_or_none()
        if delivery is None:
            log.warning("WebhookDelivery %s not found", delivery_id)
            return False
        if delivery.status == "delivered":
            return True

        # Resolve subscription for the secret.
        sub_result = await session.execute(
            select(WebhookSubscription).where(WebhookSubscription.id == delivery.subscription_id)
        )
        sub = sub_result.scalar_one_or_none()
        if sub is None or not sub.active:
            delivery.status = "failed"
            delivery.response_body = "subscription inactive or deleted"
            await session.commit()
            return False

        envelope = {
            "id": str(delivery.id),
            "event": delivery.event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "data": delivery.payload,
        }
        body = json.dumps(envelope, default=str).encode("utf-8")
        signature = sign_payload(sub.secret, body)
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: signature,
            EVENT_HEADER: delivery.event_type,
            DELIVERY_HEADER: str(delivery.id),
            "User-Agent": "champ-personalize-webhooks/0.1",
        }

        delivery.attempts += 1
        delivery.last_attempt_at = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                r = await client.post(sub.target_url, headers=headers, content=body)
            delivery.response_status = r.status_code
            delivery.response_body = (r.text or "")[:3900]
            ok = 200 <= r.status_code < 300
        except httpx.HTTPError as e:
            delivery.response_status = 0
            delivery.response_body = f"transport error: {e}"[:3900]
            ok = False

        if ok:
            delivery.status = "delivered"
            await session.commit()
            return True

        if delivery.attempts >= MAX_ATTEMPTS:
            delivery.status = "failed"
            await session.commit()
            return False

        # Reschedule with backoff (handled in the arq worker module).
        delivery.status = "pending"
        await session.commit()
        return False
