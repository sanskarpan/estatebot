# 08 — Docker, Deployment & Operations

## Implemented build decision

The current implementation uses a single Python 3.12 FastAPI runtime image that serves the vanilla static frontend. It also contains the scraper and ingestion packages so the same build can run the Compose tool profiles. SQLite plus the FTS5/BM25 index lives under `/app/data`; a checked-in normalized two-source seed snapshot at `/app/seed_corpus.json` bootstraps a fresh API volume. The public release runs as a Render free web service from the root `render.yaml` configuration. Exact local and public evidence is in [`IMPLEMENTATION-STATUS.md`](IMPLEMENTATION-STATUS.md) and [`DEPLOYED-QA.md`](DEPLOYED-QA.md).

## 1. Containerisation requirements

- A `Dockerfile` per service that needs one: `backend/Dockerfile` (FastAPI app; also serves the built static frontend if the single-container approach is chosen — recommended, see §1.3), optionally `frontend/Dockerfile` if served as its own container/static host instead.
- Multi-stage builds: a `builder` stage installs build-only dependencies (compilers, dev packages, `npm install && npm run build` for the frontend if bundled in) and a slim `runtime` stage (e.g. `python:3.12-slim`) copies only what's needed to run — keeps the final image small and reduces attack surface.
- `docker-compose.yml` at the repo root orchestrates: the `api` service, and a one-off `scraper` / `ingestion` profile/service that can be run on demand (`docker compose run --rm scraper`, `docker compose run --rm ingestion`) without being part of the always-on stack.
- A named Docker volume (or bind mount for local dev) persists `data/` (SQLite file + vector store directory) across container restarts — losing the scraped corpus on every redeploy would defeat the point of scraping at all.
- `.dockerignore` excludes `data/raw/`, local venvs, node_modules, `.git`, `.env` (never bake secrets into an image layer).

### 1.1 `Dockerfile` — backend (illustrative shape; adapt exact base image/versions during implementation)

```dockerfile
# ---- builder stage ----
FROM python:3.12-slim AS builder
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# (optional) frontend build stage, if bundling the SPA into this same image
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---- runtime stage ----
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY backend/ /app/backend
COPY --from=frontend-builder /frontend/dist /app/backend/static
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 1.2 `docker-compose.yml` — illustrative shape

```yaml
services:
  api:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - estatebot_data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 30s
      timeout: 5s
      retries: 3

  scraper:
    build:
      context: .
      dockerfile: scraper/Dockerfile
    env_file: .env
    volumes:
      - estatebot_data:/app/data
    profiles: ["tools"]     # not started by default `docker compose up`
    command: ["python", "-m", "scraper.run_all"]

  ingestion:
    build:
      context: .
      dockerfile: backend/Dockerfile   # can reuse backend image if deps overlap sufficiently
    env_file: .env
    volumes:
      - estatebot_data:/app/data
    profiles: ["tools"]
    command: ["python", "-m", "ingestion.build_index"]

volumes:
  estatebot_data:
```

Local full pipeline after the initial seeded boot: `docker compose run --rm scraper`, then `docker compose run --rm ingestion`, then restart `api`. For a clean local API demo, `docker compose up --build api` is sufficient because the seed snapshot is loaded automatically.

### 1.3 Single-container vs multi-container decision

**Recommended for this assignment: single deployed container (`api`) that also serves the built static frontend**, because most zero-cost hosting targets (see §2) bill/provision per *service*, and running two long-lived services (a separate frontend host + a separate backend host) adds cross-origin/CORS complexity and doubles the chance of one half sleeping while the other is awake. The scraper/ingestion remain separate *tool* profiles run on demand (locally, in CI, or as a one-off job on the host if supported), not long-running services — this matches their actual usage pattern (run occasionally to refresh data, not continuously).

## 2. Hosting target comparison (evaluate at build time — this list reflects research as of September 2026; free-tier terms change frequently, re-verify before committing)

| Platform | Free tier reality (as researched) | Fit for this project |
|---|---|---|
| **Render** | Maintains a genuine no-card-required free "Hobby" web-service tier (Docker-deployable), ~512MB RAM, that stays deployed indefinitely but **sleeps after a period of inactivity** and cold-starts on the next request (typically tens of seconds). | **Primary recommendation.** No credit card, straightforward Docker deploy from a GitHub repo, persistent free hosting (not a time-limited trial). The sleep behaviour must be surfaced honestly in the UI (§3 of `docs/07-FRONTEND-SPEC.md` "cold-start" state) rather than hidden. |
| **Hugging Face Spaces (Docker SDK)** | Free CPU-tier Spaces support arbitrary Dockerfiles, are commonly used for exactly this kind of AI-demo deployment, and give a stable public URL; free-tier Spaces can also idle/sleep after inactivity depending on visibility/tier. | **Strong alternative/backup**, especially well-suited to an "AI demo" framing and a natural fit for a portfolio-style submission; verify current Space resource limits (RAM/CPU/storage) accommodate the embedding model + vector store at build time. |
| **Google Cloud Run** | Has a genuinely permanent (not time-limited-trial) free monthly allowance of requests/compute for a container-based service; requires a Google Cloud account (card on file for the broader account, but the free allowance itself doesn't require spend for light usage) and scales to zero between requests (cold starts similar in spirit to Render's sleep). | Good backup if Render/HF don't fit resource needs; more setup steps (project/IAM/artifact registry) than Render or HF Spaces, which matters for a time-boxed assignment. |
| **Railway** | As of 2026, no longer offers a persistent free tier — usage-based billing after a short trial/credit. | Not recommended as the primary target given the "must run within free tiers" constraint in `docs/01-SPEC.md` §6, unless the builder has existing credits; acceptable only as a documented exception with cost noted. |
| **Fly.io** | As of 2026, no longer offers an always-on free tier — trial-only, then pay-per-second. | Same caveat as Railway; keep as a documented "if paying a few dollars is acceptable" fallback, not the default plan. |

**Recorded decision:** Render was selected for its no-cost Docker service and straightforward repository integration. BM25/SQLite FTS5 was selected after resource measurement to preserve comfortable headroom on a 512 MB instance. The actual URL, cost, and cold-start limitation are recorded in `SUBMISSION.md`.

### 2.1 Prepared Render deployment

`render.yaml` is the concrete deployment manifest. It uses the Docker runtime, free 512 MB plan, `/api/health`, CI-gated automatic deploys, BM25 retrieval, the configured free-model chain, and dashboard-provided secrets. Render's free service filesystem is ephemeral, so the application intentionally reconstructs SQLite and its FTS5 index from the checked-in seed on each clean instance start; chat history is consequently demo-session data rather than durable product data. This avoids claiming persistent free disk support that the platform does not provide.

The active service is configured with `OPENROUTER_API_KEY` in the host secret store and its assigned HTTPS URL in `OPENROUTER_HTTP_REFERER` and `CORS_ALLOWED_ORIGINS`. Reproductions should create a web service from the manifest and supply those secret/environment values without writing them to the repository.

## 3. Resource sizing

- Target runtime RAM budget: fit comfortably within **512MB** (the common denominator across free tiers above) — this directly drives the embedding-model-vs-BM25 decision in `docs/05-CHATBOT-RAG-SPEC.md` §9: measure the actual resident memory of the chosen `sentence-transformers` model + FastAPI + Chroma at the target corpus size before committing; if it doesn't comfortably fit with headroom, switch to the BM25/SQLite-FTS5 fallback, which has a negligible memory footprint.
- Target image size: keep the final runtime image lean (aim well under 1GB) by using slim base images, multi-stage builds, and excluding dev/test dependencies from the runtime `requirements.txt` (split into `requirements.txt` and `requirements-dev.txt`).
- Disk: SQLite DB + vector store + (dev-only) raw HTML snapshots should stay in the low tens of MB to low hundreds of MB at the corpus sizes in `docs/01-SPEC.md` §7 — well within any free tier's disk allowance; raw snapshots may be excluded from the production image/volume entirely if disk becomes a concern (they're a dev/audit aid, not required at runtime).

## 4. Environment variables

See `.env.example` for the authoritative, complete list with inline documentation. Summary of the most important ones:

| Variable | Required | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | Auth for OpenRouter calls. Never committed; set via host secret manager. |
| `OPENROUTER_MODEL_PRIMARY` | Yes | Primary free model ID, verified live per `docs/05-CHATBOT-RAG-SPEC.md` §1. |
| `OPENROUTER_MODEL_FALLBACK_1` / `_2` | Recommended | Fallback chain models. |
| `DATABASE_PATH` | Yes | Path to the SQLite file inside the mounted volume, e.g. `/app/data/estatebot.db`. |
| `VECTOR_STORE_PATH` | Yes | Path to the Chroma persistence directory inside the mounted volume. |
| `RETRIEVAL_MODE` | No (default `bm25_only`) | `hybrid` \| `vector_only` \| `bm25_only` — the current build uses the low-memory FTS5/BM25 path. |
| `MAX_WASALT_LISTINGS` | No (default 400) | Scrape scope cap, per `docs/01-SPEC.md` §7. |
| `MAX_DARGLOBAL_PRESS` | No (default 25) | Scrape scope cap. |
| `CHAT_RATE_LIMIT_REQUESTS` / `CHAT_RATE_LIMIT_WINDOW_SECONDS` | No | Per `docs/06-API-SPEC.md` §6. |
| `CHAT_HISTORY_TURNS` | No (default 8) | Per `docs/05-CHATBOT-RAG-SPEC.md` §2.3. |
| `CORS_ALLOWED_ORIGINS` | Yes if split-origin deploy | Explicit allow-list, never `*` in production. |
| `LOG_LEVEL` | No (default `INFO`) | Standard logging verbosity. |

## 5. Deployment procedure (Render-style; adapt mechanically for the actually-chosen platform)

1. Push the repository to GitHub (public or with the reviewer granted access).
2. In the hosting platform, create a new Web Service from the repo, select "Docker" as the environment, point at `backend/Dockerfile` (or the compose-equivalent config the platform supports).
3. Set all required environment variables (§4) in the platform's dashboard/secret manager — never in the Dockerfile or repo.
4. Attach a persistent disk/volume for `/app/data` if the platform supports it, so the corpus survives redeploys; if the platform's free tier has no persistent disk option, document that data is rebuilt on each deploy via a `release`/`predeploy` command that runs the scraper+ingestion pipeline before the app boots (acceptable trade-off — record which path was actually used).
5. Deploy; confirm `GET /api/health` returns `200` with a non-zero `listings_total`.
6. Confirm the chat UI loads at the public URL and a sample question from `docs/01-SPEC.md` §4 returns a correct, cited answer.
7. Record the final URL, platform, and any operational caveats (cold start time, data-refresh method) in `SUBMISSION.md`.

## 6. Data refresh procedure (documented, not automated, unless time allows)

Minimum viable: manual re-run — `docker compose run --rm scraper && docker compose run --rm ingestion`, then redeploy/restart the `api` service to pick up the refreshed volume contents (or trigger a hot-reload of the retrieval layer's in-memory handles if the app supports it without a restart — document whichever is actually implemented).
Stretch goal (not required): a scheduled job (platform cron feature, or a GitHub Actions workflow that runs the scraper/ingestion and pushes a refreshed data snapshot / triggers a redeploy) — call out explicitly in `SUBMISSION.md` whether this was implemented or left manual.

## 7. Cost ledger (fill in with actuals during build; template below)

| Component | Provider | Expected cost |
|---|---|---|
| Hosting (API + frontend) | e.g. Render Hobby | $0 |
| LLM generation | OpenRouter free model(s) | $0 |
| Embeddings | Local `sentence-transformers` in-container | $0 |
| Vector store | Embedded Chroma, same host, no external service | $0 |
| Structured DB | SQLite, same host | $0 |
| Domain | Platform-provided subdomain (e.g. `estatebot.onrender.com`) | $0 |
| **Total** | | **$0** |

If any component ends up non-zero-cost (e.g. a paid hosting tier was necessary), state the actual monthly cost and the reason plainly in `SUBMISSION.md` rather than glossing over it — honesty about trade-offs is itself part of what's being evaluated.
