# LakeB2B · 5-Level Email Personalizer

Standalone production deployment of the Five Levels of Email Personalization framework, branded and locked to **LakeB2B**. Drop in any prospect, the system researches them live, fuses all five signal layers (Industry × Company × Role × Individual × Synthesis) into one cold email, and gives you three open-weight model variants (DeepSeek V4 Pro, Llama 4 Maverick, Mistral Large 3) to pick from.

**Brand:** LakeB2B · *Enabling Growth*
**Identity:** Purple `#6D08BE` + Gold `#FFB703` + Red `#E8033A` · Montserrat + Alata
**Production target:** Railway. See [`docs/railway.md`](docs/railway.md).

## What's locked to LakeB2B in this repo

- `LOCKED_BRAND=lakeb2b` in `.env.example`. Backend ignores Host / query / `X-Brand` and always serves LakeB2B's tokens, sender defaults, and voice addendum.
- `/v1/brands` lists only `lakeb2b`.
- Frontend index hard-routes to `/lead-magnet/lakeb2b`. The internal app drops the brand selector.
- All user-facing copy is em-dash-free; the validator that policies generated emails policies the UI strings too.

The multi-brand source repo (LakeB2B + SPAN Global Services + Ampliz + Champions Group) lives at [`Champ-Deep/five-level-email-personalizer`](https://github.com/Champ-Deep/five-level-email-personalizer). This repo is the LakeB2B production branch promoted to its own repository.

## Quick start (local)

```bash
cp .env.example .env                # fill in OPENROUTER_API_KEY
docker compose up --build
```

- Lead magnet (LakeB2B): <http://localhost:5173>
- Internal tool: <http://localhost:5173/app>
- API docs: <http://localhost:8000/docs>

## Deploying to Railway

See [`docs/railway.md`](docs/railway.md) for the full step-by-step (Postgres + Redis plugins, API + Worker + Frontend services, env var table).

**The OpenRouter env var is `OPENROUTER_API_KEY`** — set on both the API service and the Worker service.

## Integrating

Three integration surfaces. Full reference at [`docs/api.md`](docs/api.md):

1. **REST API** — `Bearer ck_live_…` auth, RFC-7807 errors, `Idempotency-Key` support, `X-Request-ID` echoed.
2. **Webhooks** — HMAC-SHA256 signed, 5-retry exponential backoff. Events: `personalize.completed`, `batch.queued`, `batch.prospect.completed`, `batch.completed`, `lead.captured`. Subscribe at `POST /v1/webhooks`.
3. **Python SDK** — `pip install -e ./sdk`. `PersonalizerClient(...).personalize(...)` for HTTP, `LocalPersonalizer(...).run(...)` for in-process co-deploy.

Every generated variation includes **deliverability** and **reply-likelihood** scores (0-100, with factor breakdown) so callers can gate sends instead of guessing. Tone presets (`casual`, `formal`, `founder`, `friendly`, `concise`) compose with per-call `style_rules` and the brand voice; none replaces another.

## How it ships

| Layer | Stack |
|---|---|
| Backend | FastAPI · SQLAlchemy[asyncio] · Postgres · Redis · `arq` worker (batch + webhook delivery) |
| LLM | OpenRouter, **open-weight only**: DeepSeek V4 Pro / Llama 4 Maverick / Mistral Large 3 |
| Research | Perplexity Sonar Pro (closed; only viable web-search-native option) |
| Frontend | Vite · React · TypeScript · Tailwind |
| Validator | Server-side gate: no em-dashes, no AI-slop vocab, no "not X but Y" |
| Scoring | Deliverability + reply-likelihood heuristics on every output |
| Eval | Pairwise blind judge via Claude Opus 4.1, `python -m app.eval_cli` |

## Latest eval

≥100% of Chief's Claude-direct baseline across 4 prospects (Patrick Sherwin / GoSun, Brian Halligan / HubSpot, Toby Lütke / Shopify, Wade Foster / Zapier). Full reports in `runs/`.

## License

Internal · Champions Group.
