# Five-Level Email Personalizer

White-labelable tool that productises the **Five Levels of Email Personalization** framework for the Champions Group ecosystem (LakeB2B, Ampliz, SPAN Global Services, Champions Group parent).

Ships as three surfaces backed by one service:

1. **Public lead-magnet** per brand domain — `personalize.lakeb2b.com`, `personalize.ampliz.com`, etc. Free: 1 prospect/IP/day. Signup unlocks 20/day + CSV batch.
2. **Internal tool** at `/app` for sales/marketing teams — auth-gated, CSV upload, batch personalize, CSV/JSON export.
3. **`champ-personalize` SDK** — pip-installable Python client + in-process adapter so ChampMail and ChampIQ can integrate later without code duplication.

Every call goes through OpenRouter, so the underlying model is swappable per request (default: `anthropic/claude-sonnet-4.5`). An eval harness measures any candidate model against a frozen Claude baseline so you can validate ≥80–90% quality before swapping the default.

## Quick start

```bash
cp .env.example .env                # fill in OPENROUTER_API_KEY
docker compose up --build
```

- API: <http://localhost:8000> (Swagger at `/docs`)
- Frontend: <http://localhost:5173>
- Lead magnet (LakeB2B): <http://localhost:5173/lead-magnet/lakeb2b>
- Internal app: <http://localhost:5173/app>

## Integrating

Three integration surfaces. Full reference at [`docs/api.md`](docs/api.md):

1. **REST API** — `Bearer ck_live_…` auth, RFC-7807 errors, `Idempotency-Key` support, `X-Request-ID` echoed. See `docs/api.md` for the full contract.
2. **Webhooks** — HMAC-SHA256 signed, 5-retry exponential backoff. Events: `personalize.completed`, `batch.queued`, `batch.prospect.completed`, `batch.completed`, `lead.captured`. Subscribe at `POST /v1/webhooks`.
3. **Python SDK** — `pip install -e ./sdk`. `PersonalizerClient(...).personalize(...)` for HTTP, `LocalPersonalizer(...).run(...)` for in-process (ChampMail co-deploy).

Every generated variation includes **deliverability** and **reply-likelihood** scores (0-100, with factor breakdown) so callers can gate sends instead of guessing. Tone presets (`casual`, `formal`, `founder`, `friendly`, `concise`) compose with per-call `style_rules` and the brand voice — none replaces another.

## Repo layout

```
backend/    FastAPI service + arq worker (webhook delivery, batch) + brand YAMLs + tests
frontend/   Vite + React + TS + Tailwind
sdk/        champ-personalize Python package (HTTP + local clients)
docs/       api.md (REST + webhooks), brand-onboarding, llm-tuning, integration-v2
```

See `/Users/deep/.claude/plans/users-deep-downloads-five-levels-cheat-spicy-glacier.md` for the full implementation plan and architecture rationale.

## Adding a brand

1. Drop a new `backend/data/brands/<slug>.yaml` with tokens + sender defaults.
2. Visit `/lead-magnet/<slug>` — colors and copy update with zero code change.
3. See `docs/brand-onboarding.md`.

## License

Internal — Champions Group.
