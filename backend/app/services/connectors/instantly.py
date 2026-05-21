"""Instantly.ai connector.

Instantly's v2 API (https://developer.instantly.ai/api/v2) accepts new
leads at POST /api/v2/leads with a JSON body. We push one lead per
prospect, attaching the generated subject + body as `personalization`
fields (also setting `custom_variables.first_line` for use in their
sequence templates).

Required config keys:
    api_key      — Bearer token from Instantly dashboard
    campaign_id  — UUID of the destination campaign

Optional:
    base_url     — defaults to https://api.instantly.ai
"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.connectors import PushResult

PROVIDER = "instantly"
REQUIRED_FIELDS = ("api_key", "campaign_id")
DEFAULT_BASE = "https://api.instantly.ai"


async def healthcheck(config: dict[str, Any]) -> tuple[bool, str]:
    api_key = config.get("api_key")
    campaign_id = config.get("campaign_id")
    if not api_key or not campaign_id:
        return False, "Missing api_key or campaign_id"
    base = (config.get("base_url") or DEFAULT_BASE).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"{base}/api/v2/campaigns/{campaign_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if r.status_code in (200, 201):
            return True, "Campaign reachable"
        return False, f"HTTP {r.status_code}: {(r.text or '')[:200]}"
    except httpx.HTTPError as e:
        return False, f"Transport error: {e}"


async def push(config: dict[str, Any], rows: list[dict[str, Any]]) -> PushResult:
    api_key = config["api_key"]
    campaign_id = config["campaign_id"]
    base = (config.get("base_url") or DEFAULT_BASE).rstrip("/")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    pushed = 0
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=30) as c:
        for row in rows:
            if not row.get("email"):
                errors.append(f"{row.get('name', '?')}: no email address, skipped")
                continue
            payload = {
                "campaign": campaign_id,
                "email": row["email"],
                "first_name": (row.get("name") or "").split(" ", 1)[0] or None,
                "last_name":  " ".join((row.get("name") or "").split(" ")[1:]) or None,
                "company_name": row.get("domain") or None,
                "personalization": row.get("body") or "",
                "custom_variables": {
                    "first_line":       row.get("subject") or "",
                    "personalized_body": row.get("body") or "",
                    "followup_subject": row.get("followup_subject") or "",
                    "followup_body":    row.get("followup_body") or "",
                    "champ_slot":       row.get("slot") or "",
                    "champ_model":      row.get("model") or "",
                },
            }
            try:
                r = await c.post(f"{base}/api/v2/leads", headers=headers, json=payload)
                if r.status_code in (200, 201):
                    pushed += 1
                else:
                    errors.append(f"{row.get('email')}: HTTP {r.status_code}: {(r.text or '')[:160]}")
            except httpx.HTTPError as e:
                errors.append(f"{row.get('email')}: transport error: {e}")

    return PushResult(ok=len(errors) == 0, pushed=pushed, failed=len(errors), errors=errors)
