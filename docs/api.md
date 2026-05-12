# REST API + Webhook Integration

Stable v1 API. Designed for ChampMail / ChampIQ / ChampOracle integration plus any external CRM or sequencer.

- **Base URL:** `https://personalize.<your-brand>.com/v1` (or `http://localhost:8000/v1` in dev)
- **Auth:** `Authorization: Bearer ck_live_…` (API key)
- **Tracing:** every request echoes its `X-Request-ID` header. Generate your own or let the server mint one.
- **Errors:** RFC-7807-shaped JSON with `request_id`.
- **Versioning:** breaking changes ship under `/v2`. `/v1` is supported for at least 12 months after `/v2` GA.

## 1 — Provision an API key

API keys are minted by signed-in users. The full key is returned **once** at creation; store it like a password.

```bash
# 1. Sign up (one-time)
curl -X POST https://personalize.lakeb2b.com/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@company.com","password":"<min 8 chars>","name":"You"}'
# → { "token": "eyJ…", "email": "you@company.com" }

# 2. Mint a key
curl -X POST https://personalize.lakeb2b.com/v1/api-keys \
  -H "Authorization: Bearer <jwt from step 1>" \
  -H 'Content-Type: application/json' \
  -d '{"name":"production","brand":"lakeb2b","rate_limit_per_day":2000}'
# → { "id":"…", "key":"ck_live_xxxxxxxx…", "prefix":"xxxxxxxx", … }
```

The `key` field is the one you store. Subsequent `GET /v1/api-keys` lists only the prefix.

To revoke: `DELETE /v1/api-keys/{id}` with the user JWT.

## 2 — Personalize one prospect

```bash
curl -X POST https://personalize.lakeb2b.com/v1/personalize \
  -H "Authorization: Bearer ck_live_xxxxxxxx…" \
  -H "Content-Type: application/json" \
  -H "X-Brand: lakeb2b" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "prospect": {
      "name": "Priya Sharma",
      "title": "VP of Sales",
      "domain": "stripe.com",
      "linkedin": "https://linkedin.com/in/priya-sharma"
    },
    "sender": {
      "name": "Deep",
      "company": "LakeB2B",
      "offer": "B2B data intelligence and demand generation."
    },
    "tone_preset": "founder",
    "style_rules": "No exclamation marks. Reference their most recent product launch if available."
  }'
```

Response shape:

```jsonc
{
  "brand": "lakeb2b",
  "brief": {
    "name": "Priya Sharma",
    "title": "VP of Sales",
    "company": "Stripe, Inc.",
    "industry": "Fintech / Payment Processing",
    "company_signals": ["…", "…", "…"],
    "individual_signals": ["…"],
    "industry_trends": ["…"],
    "role_pain_points": ["…"],
    "strongest_trigger": "…",
    "likely_pain_point": "…"
  },
  "variations": [
    {
      "slot": "A",
      "label": "DeepSeek V4 Pro",
      "model": "deepseek/deepseek-v4-pro",
      "email": {
        "subject": "Stripe's Dublin expansion and outbound clarity",
        "body": "Priya, …",
        "word_count": 87,
        "anchor_signal": "Stripe's Series I close",
        "warnings": [],
        "scores": {
          "deliverability":    { "score": 96, "factors": {} },
          "reply_likelihood":  { "score": 78, "factors": { "specifics": "+15 (3 signals)", "soft_cta": "+12", "length": "+8" } }
        }
      }
    },
    { "slot": "B", "model": "meta-llama/llama-4-maverick", … },
    { "slot": "C", "model": "mistralai/mistral-large-2512", … }
  ],
  "emails": { "5": { /* slot A, kept for back-compat */ } }
}
```

### Idempotency

Set `Idempotency-Key: <unique id>` on any request you might retry. Re-sending the same key within 24 hours replays the original response. Keys are scoped per API key — clashes across tenants are impossible.

### Tone presets

`tone_preset` accepts one of `casual` / `formal` / `founder` / `friendly` / `concise`. Composes with `style_rules` (additive — neither replaces the brand voice or the hard anti-slop rules). Full list via `GET /v1/brands/_tone_presets`.

### Quality scores

Every variation carries two scores (0-100):

- **Deliverability** — heuristic spam-filter friendliness. Starts at 100, deducts for spam triggers, ALL-CAPS subjects, links, excessive punctuation, dollar signs, body length out of range.
- **Reply likelihood** — heuristic "would a busy human reply?" score starting at 50, adjusting for brief-signal specificity, CTA softness, opener strength, AI-tell vocabulary.

`factors` is a transparent breakdown: every score has the reasons it landed where it did. Surface them in your UI or use them as a gate ("only send if reply_likelihood ≥ 70").

## 3 — Bulk: `/v1/personalize/batch`

```bash
curl -X POST https://personalize.lakeb2b.com/v1/personalize/batch \
  -H "Authorization: Bearer ck_live_…" \
  -H "Content-Type: application/json" \
  -d '{
    "prospects": [
      { "name": "P1", "title": "VP Sales", "domain": "co1.com" },
      { "name": "P2", "title": "Founder",  "domain": "co2.io" }
    ],
    "sender": { "name": "Deep", "company": "LakeB2B", "offer": "…" }
  }'
# → 202 { "job_id": "…" }
```

Poll progress with `GET /v1/jobs/{job_id}`. Each prospect emits a `batch.prospect.completed` webhook as it finishes. `batch.completed` fires once the whole job ends.

## 4 — Webhooks

Subscribe a URL to events. Every delivery is HMAC-SHA256 signed with a secret shown once at subscribe time.

### Subscribe

```bash
curl -X POST https://personalize.lakeb2b.com/v1/webhooks \
  -H "Authorization: Bearer ck_live_…" \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://crm.acme.com/webhooks/personalize",
    "events": ["personalize.completed", "batch.completed", "lead.captured"],
    "description": "CRM sync"
  }'
# → { "id": "…", "secret": "whsec_xxxxxxxx…", "events": […] }
```

Use `"events": ["*"]` to subscribe to every event.

### Event types

| Event | Fires when | Payload `data` |
|---|---|---|
| `personalize.completed` | sync `POST /v1/personalize` returns 200 | brand, prospect, brief, variations[] |
| `batch.queued` | `POST /v1/personalize/batch` accepts a job | job_id, brand, total |
| `batch.prospect.completed` | one prospect finishes inside a batch job | job_id, index, prospect, result |
| `batch.completed` | a batch job's last prospect finishes | job_id, total, done, failed, status |
| `lead.captured` | someone signs up on the lead-magnet | lead_id, email, name, brand, source |

### Delivery format

Each POST is JSON:

```json
{
  "id": "<delivery uuid>",
  "event": "personalize.completed",
  "created_at": "2026-05-13T…Z",
  "data": { … event-specific payload … }
}
```

Headers:

| Header | Meaning |
|---|---|
| `Content-Type: application/json` | always |
| `X-Champ-Event` | event name (`personalize.completed`, etc) |
| `X-Champ-Delivery-Id` | UUID — handy for de-duping retries |
| `X-Champ-Signature` | `sha256=<hex>` HMAC of the raw body |
| `User-Agent` | `champ-personalize-webhooks/0.1` |

### Verify signature (Python)

```python
import hmac, hashlib
def verify(secret: str, raw_body: bytes, signature_header: str) -> bool:
    mac = hmac.new(secret.encode(), msg=raw_body, digestmod=hashlib.sha256)
    expected = f"sha256={mac.hexdigest()}"
    return hmac.compare_digest(expected, signature_header)
```

### Verify signature (Node)

```js
import crypto from "node:crypto";

export function verify(secret, rawBody, signatureHeader) {
  const mac = crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
  const expected = `sha256=${mac}`;
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signatureHeader));
}
```

### Retries

Failed deliveries (non-2xx response or transport error) retry **up to 5 times** with exponential backoff: **1 min → 5 min → 30 min → 2 h → 12 h**. After the 5th failure the delivery is marked `failed`. Listed via `GET /v1/webhooks/{id}/deliveries`.

### Manage subscriptions

```bash
GET    /v1/webhooks                                # list yours
DELETE /v1/webhooks/{id}                           # deactivate
GET    /v1/webhooks/{id}/deliveries?limit=50       # debug log
```

## 5 — Python SDK

The `champ-personalize` package wraps the API. Install:

```bash
pip install -e ./sdk
```

```python
import asyncio
from champ_personalize import PersonalizerClient

async def main():
    client = PersonalizerClient("https://personalize.lakeb2b.com", token="ck_live_…")
    result = await client.personalize(
        brand="lakeb2b",
        prospect={"name": "Priya Sharma", "title": "VP Sales", "domain": "stripe.com"},
    )
    best = max(result.variations, key=lambda v: v.email.scores["reply_likelihood"]["score"])
    print(best.model, "→", best.email.subject)

asyncio.run(main())
```

## 6 — Errors

All errors are `Content-Type: application/json`, RFC 7807 shape:

```json
{
  "type": "about:blank",
  "title": "Rate limit exceeded",
  "status": 429,
  "detail": "Daily limit reached. Sign up to unlock 20 personalizations / day + CSV batch.",
  "request_id": "8c1c…"
}
```

Common status codes:

| Status | When |
|---|---|
| 200 | Success |
| 202 | Batch accepted |
| 401 | Missing / invalid API key |
| 404 | Brand or resource not found |
| 409 | Resource already exists (signup with existing email) |
| 413 | Batch too large (>1000) |
| 429 | Daily rate limit hit |
| 502 | LLM provider error (upstream) |

## 7 — Versioning + uptime

- **`/v1` stability**: schema additions are non-breaking. Renames and removals only land in `/v2`.
- **Idempotency** + **request IDs** are guaranteed on every endpoint that accepts an `Idempotency-Key`.
- All deploys roll forward; webhook deliveries that fail during a deploy continue retrying on the next worker boot — no data loss.
