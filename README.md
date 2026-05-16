# SPAN Global Services · 5-Level Email Personalizer

Branded deployment of the Five Levels of Email Personalization framework for **SPAN Global Services**. Drop in any prospect — the system researches them live, fuses all five signal layers (Industry × Company × Role × Individual × Synthesis) into one cold email, and gives you three open-weight model-variant drafts (DeepSeek V4 Pro, Llama 4 Maverick, Mistral Large 3) to pick from.

**Brand:** SPAN Global Services · *Marketing Data Intelligence to Fuel Growth*
**Identity:** SPAN Green `#1B6B3A` + Span Mint `#E8F5ED` · Montserrat (headings) + Inter (body)
**Stat:** 25M+ verified business contacts across pharma, legal, energy, market research, and education.

## What's locked to SPAN on this branch

- `LOCKED_BRAND=span-global` in `.env.example` — backend ignores Host / query / `X-Brand` and always serves SPAN's tokens, sender defaults, and voice addendum.
- `/v1/brands` lists only `span-global`.
- Frontend index hard-routes to `/lead-magnet/span-global`. The internal app drops the brand selector.
- System-prompt addendum tuned for SPAN's voice: authoritative, precise, growth-oriented, global. Frames SPAN as a *data intelligence partner*, never a *data vendor*. Cites concrete scale (25M+ verified contacts).

For the multi-brand version, see [`main`](https://github.com/Champ-Deep/five-level-email-personalizer/tree/main). The sister branch [`lakeb2b`](https://github.com/Champ-Deep/five-level-email-personalizer/tree/lakeb2b) is the LakeB2B build.

## Quick start

```bash
cp .env.example .env                # fill in OPENROUTER_API_KEY
docker compose up --build
```

- Lead magnet (SPAN): <http://localhost:5173>
- Internal tool: <http://localhost:5173/app>
- API docs: <http://localhost:8000/docs>

## Deploying

Railway is the supported production target. See [`docs/railway.md`](docs/railway.md) for the full step-by-step (Postgres + Redis plugins, API + Worker + Frontend services, env var table). The OpenRouter key variable is **`OPENROUTER_API_KEY`** — set on both the API service and the Worker service.

## Integrating

Three integration surfaces. Full reference at [`docs/api.md`](docs/api.md):

1. **REST API** — `Bearer ck_live_…` auth, RFC-7807 errors, `Idempotency-Key` support, `X-Request-ID` echoed.
2. **Webhooks** — HMAC-SHA256 signed, 5-retry exponential backoff. Events: `personalize.completed`, `batch.queued`, `batch.prospect.completed`, `batch.completed`, `lead.captured`. Subscribe at `POST /v1/webhooks`.
3. **Python SDK** — `pip install -e ./sdk`. `PersonalizerClient(...).personalize(...)` for HTTP, `LocalPersonalizer(...).run(...)` for in-process (ChampMail co-deploy).

Every generated variation includes **deliverability** and **reply-likelihood** scores (0-100, with factor breakdown) so callers can gate sends instead of guessing. Tone presets (`casual`, `formal`, `founder`, `friendly`, `concise`) compose with per-call `style_rules` and the brand voice — none replaces another.

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

## License

Internal — Champions Group.
