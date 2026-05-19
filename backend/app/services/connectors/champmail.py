"""ChampMail connector.

ChampMail is Champions Group's self-hosted email engine
(/Users/deep/Apps&Projects/ChampMail). It exposes:
  POST /api/v1/prospects (single or bulk create + upsert by email)
  POST /api/v1/sequences/{sequence_id}/enrollments (enroll a prospect)

The connector pushes each row as a prospect, attaches the personalized
content via custom fields, then enrolls in the configured sequence.

Required config keys:
    base_url     — e.g. https://champmail.example.com
    api_token    — service JWT or API key with prospects:write + sequences:enroll
    sequence_id  — UUID of the destination sequence

Optional:
    team_id      — multi-tenant scoping (ChampMail uses team_id on
                   most resources)
"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.connectors import PushResult

PROVIDER = "champmail"
REQUIRED_FIELDS = ("base_url", "api_token", "sequence_id")


async def healthcheck(config: dict[str, Any]) -> tuple[bool, str]:
    base = config.get("base_url", "").rstrip("/")
    token = config.get("api_token")
    if not base or not token:
        return False, "Missing base_url or api_token"
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{base}/health", headers={"Authorization": f"Bearer {token}"})
        if r.status_code in (200, 401, 403):
            # 401/403 still proves the service is reachable — config just wrong.
            return r.status_code == 200, f"HTTP {r.status_code}"
        return False, f"HTTP {r.status_code}"
    except httpx.HTTPError as e:
        return False, f"Transport error: {e}"


async def push(config: dict[str, Any], rows: list[dict[str, Any]]) -> PushResult:
    base = config["base_url"].rstrip("/")
    token = config["api_token"]
    sequence_id = config["sequence_id"]
    team_id = config.get("team_id")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    pushed = 0
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=30) as c:
        for row in rows:
            if not row.get("email"):
                errors.append(f"{row.get('name', '?')}: no email, skipped")
                continue
            prospect_body: dict[str, Any] = {
                "email": row["email"],
                "first_name": (row.get("name") or "").split(" ", 1)[0] or "",
                "last_name":  " ".join((row.get("name") or "").split(" ")[1:]) or "",
                "title": row.get("title") or "",
                "linkedin_url": row.get("linkedin") or "",
                "company_domain": row.get("domain") or "",
                # Stash personalized content as custom fields the sequence template can read.
                "custom_fields": {
                    "personalized_subject": row.get("subject") or "",
                    "personalized_body":    row.get("body") or "",
                    "followup_subject":     row.get("followup_subject") or "",
                    "followup_body":        row.get("followup_body") or "",
                    "champ_slot":           row.get("slot") or "",
                    "champ_model":          row.get("model") or "",
                },
            }
            if team_id:
                prospect_body["team_id"] = team_id
            try:
                r1 = await c.post(f"{base}/api/v1/prospects", headers=headers, json=prospect_body)
                if r1.status_code not in (200, 201, 409):
                    errors.append(f"{row['email']}: prospect upsert HTTP {r1.status_code}: {(r1.text or '')[:160]}")
                    continue
                prospect_id = (r1.json() or {}).get("id") or (r1.json() or {}).get("prospect_id")
                if not prospect_id:
                    # Best-effort: enrollment by email if id wasn't returned.
                    enroll_body = {"prospect_email": row["email"]}
                else:
                    enroll_body = {"prospect_id": prospect_id}
                if team_id:
                    enroll_body["team_id"] = team_id
                r2 = await c.post(
                    f"{base}/api/v1/sequences/{sequence_id}/enrollments",
                    headers=headers, json=enroll_body,
                )
                if r2.status_code in (200, 201):
                    pushed += 1
                else:
                    errors.append(f"{row['email']}: enroll HTTP {r2.status_code}: {(r2.text or '')[:160]}")
            except httpx.HTTPError as e:
                errors.append(f"{row['email']}: transport error: {e}")

    return PushResult(ok=len(errors) == 0, pushed=pushed, failed=len(errors), errors=errors)
