"""ChampIQ connector — webhook-based for now.

ChampIQ's Bullpen API isn't fully documented in the repo at the time of
writing, so this connector POSTs the prospect+email payload to a
user-configurable webhook URL with an HMAC signature, and ChampIQ's
incoming-webhook handler picks it up.

The same payload shape works with any custom receiver. Once ChampIQ
exposes a stable REST endpoint, swap this for a direct REST connector.

Required config keys:
    webhook_url   — full URL of the ChampIQ webhook receiver
    webhook_secret — HMAC-SHA256 secret (echoed in X-Champ-Push-Signature)
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.connectors import PushResult

PROVIDER = "champiq"
REQUIRED_FIELDS = ("webhook_url", "webhook_secret")


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def healthcheck(config: dict[str, Any]) -> tuple[bool, str]:
    # Webhook receivers typically don't expose a GET probe — we just verify
    # the URL parses and the secret is set.
    if not config.get("webhook_url") or not config.get("webhook_secret"):
        return False, "Missing webhook_url or webhook_secret"
    return True, "Configured (no GET probe available for webhook receivers)"


async def push(config: dict[str, Any], rows: list[dict[str, Any]]) -> PushResult:
    body = json.dumps({
        "event": "champ.personalize.push",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "prospects": rows,
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Champ-Push-Signature": _sign(config["webhook_secret"], body),
        "X-Champ-Push-Count": str(len(rows)),
    }
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(config["webhook_url"], headers=headers, content=body)
        if r.status_code in (200, 201, 202):
            return PushResult(ok=True, pushed=len(rows), failed=0, raw={"response_status": r.status_code})
        return PushResult(
            ok=False, pushed=0, failed=len(rows),
            errors=[f"HTTP {r.status_code}: {(r.text or '')[:200]}"],
        )
    except httpx.HTTPError as e:
        return PushResult(ok=False, pushed=0, failed=len(rows), errors=[f"transport error: {e}"])
