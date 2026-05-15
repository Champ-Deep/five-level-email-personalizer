# Deploying to Railway

End-to-end recipe for a per-brand production deploy. Repeat for each brand (`lakeb2b`, `span-global`, `ampliz` when it's ready) — each one is one Railway **project** with five **services** + two plugins.

## TL;DR — variable you asked for

The OpenRouter API key environment variable is:

```
OPENROUTER_API_KEY
```

Set it as a **Service Variable** on the **API service** AND on the **Worker service** (both call OpenRouter). Don't set it on Postgres / Redis / Frontend. Get the key at <https://openrouter.ai>.

## Architecture on Railway

```
┌──────────────────────────────────────────────────────────────────────┐
│  Railway project: personalize-<brand>                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐             │
│   │  API         │   │  Worker      │   │  Frontend    │  ← public   │
│   │  (FastAPI)   │   │  (arq)       │   │  (Vite)      │             │
│   └──────┬───────┘   └──────┬───────┘   └──────────────┘             │
│          │                  │                                        │
│          ▼                  ▼                                        │
│   ┌──────────────┐   ┌──────────────┐                                │
│   │ Postgres     │   │ Redis        │  ← Railway-managed plugins     │
│   │ (plugin)     │   │ (plugin)     │                                │
│   └──────────────┘   └──────────────┘                                │
└──────────────────────────────────────────────────────────────────────┘
```

| Service | Source | Root Directory | Start command |
|---|---|---|---|
| **API** | this repo, branch `lakeb2b` (or `span-global`) | `backend` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (set in `backend/railway.toml`) |
| **Worker** | same repo, same branch | `backend` | `arq app.workers.arq_worker.WorkerSettings` (override in dashboard) |
| **Frontend** | same repo, same branch | `frontend` | `serve -s dist -l $PORT` (set in `frontend/railway.toml`) |
| **Postgres** | Railway plugin | — | — |
| **Redis** | Railway plugin | — | — |

## Why this Just Works on Railway

The repo ships with both:

- **Root** `Dockerfile` + `railway.toml` (the default — Railway sees these immediately, builds the API. Zero config needed.)
- **Per-service** `backend/Dockerfile` + `backend/railway.toml` and `frontend/Dockerfile` + `frontend/railway.toml` (used when a service sets a Root Directory.)

If you point a Railway service at the repo without setting Root Directory, it deploys the **API**. The Worker is a sibling service with one Start Command override. The Frontend is a separate service with Root Directory set to `frontend`.

If you see Railway falling back to Railpack with "could not determine how to build the app", it means the root Dockerfile + railway.toml aren't visible — make sure the branch you're deploying has them (this branch does as of commit ${LAKEB2B_DEPLOY_COMMIT}).

## Step-by-step (first time)

### 1 · Provision plugins

In your Railway project: **+ New → Database → PostgreSQL**, then **+ New → Database → Redis**. Note their internal variable references (you'll wire them in step 4):

- `${{Postgres.DATABASE_URL}}`
- `${{Redis.REDIS_URL}}`

### 2 · Deploy the API service (zero-config)

1. **+ New → GitHub Repo → `Champ-Deep/lakeb2b-email-personalizer`** (or whichever repo you're using).
2. Pick the branch (`main` on the standalone repo, or `lakeb2b`/`span-global`/`main` on the multi-brand repo).
3. **Root Directory: leave as default (`.`)**. Railway will read `railway.toml` + `Dockerfile` from the root and build the API automatically.
4. Set Service Variables (see table in §4).
5. **Settings → Networking → Generate Domain**.

### 3 · Deploy the Worker service

1. **+ New Service → same repo, same branch**.
2. **Root Directory: leave as default (`.`)** — uses the same root Dockerfile.
3. **Settings → Deploy → Start Command → `arq app.workers.arq_worker.WorkerSettings`** (overrides the railway.toml default).
4. Disable the public domain (Worker is internal-only).
5. Copy the SAME service variables as the API (`OPENROUTER_API_KEY`, `DATABASE_URL`, `REDIS_URL`, etc.).

### 4 · Deploy the Frontend service

1. **+ New Service → same repo, same branch**.
2. **Settings → Source → Root Directory = `frontend`**. (This service is a separate Vite/static build, distinct from the backend.)
3. **Settings → Build → Build Args**: `VITE_API_BASE_URL=https://<api-service>.up.railway.app` (use the URL from step 2's Generate Domain). This is baked into the bundle at build time.
4. **Settings → Networking → Generate Domain**, or add your custom domain (`personalize.lakeb2b.com`).

### 5 · Wire CORS

On the API service, set `FRONTEND_BASE_URL` to the frontend's public URL. Comma-separate to allow multiple origins (Railway-generated + custom domain):

```
FRONTEND_BASE_URL=https://<frontend>.up.railway.app,https://personalize.lakeb2b.com
```

## Service Variables — full table

### API service

| Variable | Required | Where it comes from | Notes |
|---|---|---|---|
| `OPENROUTER_API_KEY` | ✅ | <https://openrouter.ai> | The one you're asking about. |
| `DATABASE_URL` | ✅ | `${{Postgres.DATABASE_URL}}` | If Railway hands you `postgres://`, prepend `postgresql+asyncpg://`. |
| `REDIS_URL` | ✅ | `${{Redis.REDIS_URL}}` | |
| `JWT_SECRET` | ✅ | `openssl rand -hex 32` | Don't reuse across brands. |
| `FRONTEND_BASE_URL` | ✅ | frontend service URLs | Comma-separated; CORS. |
| `APP_BASE_URL` | ✅ | the API service's URL | Echoed in webhook payloads. |
| `OPENROUTER_DEFAULT_MODEL` | optional | default `deepseek/deepseek-v4-pro` | |
| `OPENROUTER_RESEARCH_MODEL` | optional | default `perplexity/sonar-pro` | |
| `VARIATION_A_MODEL` / `_LABEL` | optional | three slot defaults in `.env.example` | |
| `VARIATION_B_MODEL` / `_LABEL` | optional | | |
| `VARIATION_C_MODEL` / `_LABEL` | optional | | |
| `LOCKED_BRAND` | per-branch | `lakeb2b` / `span-global` / empty | Already set in branch's `.env.example`. |
| `DEFAULT_BRAND` | optional | default `lakeb2b` | |
| `RATE_LIMIT_ANON_PER_DAY` | optional | default `1` | |
| `RATE_LIMIT_LEAD_PER_DAY` | optional | default `20` | |
| `ANTHROPIC_API_KEY` | optional | eval-harness only | Leave empty for production. |

### Worker service

Same vars as API except CORS/URL ones aren't strictly needed. Easiest: clone the API service's variables wholesale (Railway dashboard supports this).

### Frontend service (build-time)

| Variable | Required | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | ✅ at **build time** | The API service's public URL. Set as a Build Arg, not just a runtime env var. |

### Postgres + Redis plugins

No manual config — Railway provisions them and exposes URLs via the `${{Postgres.DATABASE_URL}}` / `${{Redis.REDIS_URL}}` template syntax.

## DATABASE_URL gotcha

Railway's PostgreSQL plugin returns `postgresql://user:pass@host:port/db`. SQLAlchemy's async stack needs the asyncpg dialect — prefix it with `+asyncpg`:

```
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
```

Easiest pattern in Railway: set the variable as a literal-with-reference:

```
DATABASE_URL=postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
```

(Railway exposes each Postgres credential as a separate variable.)

## After first deploy

- **Smoke test**: `curl https://<api>.up.railway.app/health` → `{"status":"ok"}`.
- **Mint an API key**: signup → `POST /v1/auth/signup`, then `POST /v1/api-keys`. See [`api.md`](api.md) for the curl flow.
- **Watch deliveries**: the Worker logs every webhook attempt — Railway's Logs tab shows them in real time.

## Updates

`git push` to the branch → Railway auto-deploys every service tracking that branch. Worker and API rebuild from the same image cache.

## Schema migrations (future)

The backend currently runs `Base.metadata.create_all()` on startup (idempotent — only creates missing tables). For destructive schema changes, add an alembic step before `startCommand` in `backend/railway.toml`:

```toml
startCommand = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

Not wired yet — flagged in the BACKLOG.

## Cost note

Three open-weight models per personalize call. Approximate token usage per call (DeepSeek V4 Pro + Llama 4 Maverick + Mistral Large 3 + Perplexity research):

- Research: ~3000 tokens
- 3 variations: ~6000 tokens combined
- Pricing varies — check OpenRouter's per-model rates. Rough average ≈ $0.01–0.03 per fully-fused personalize call.

The Worker rate is purely Railway compute — no LLM cost when idle. Postgres + Redis on the Hobby plan are free up to the included quotas.

## To switch off proprietary models entirely

Already the default. The product path uses zero proprietary models. Perplexity Sonar Pro (the research step) is the only closed-source dependency and is flagged in `backend/app/core/config.py` — to drop it, replace `OPENROUTER_RESEARCH_MODEL` with an open-weight `:online` slug like `deepseek/deepseek-v4-pro:online`. Expect slightly weaker research signal recovery.
