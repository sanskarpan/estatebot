# 08 — Docker, Delivery, and Operations

This document records the implemented delivery design. Reviewer-facing URLs and provider-specific release facts are in [`../SUBMISSION.md`](../SUBMISSION.md); implementation and public checks are in [`IMPLEMENTATION-STATUS.md`](IMPLEMENTATION-STATUS.md) and [`DEPLOYED-QA.md`](DEPLOYED-QA.md).

## 1. Runtime image

`backend/Dockerfile` builds a single Python 3.12 image containing:

- the FastAPI application;
- the vanilla static frontend;
- the collection and ingestion packages used by one-off tool commands;
- the normalized seed corpus used to initialize an empty data directory.

The container exposes port 8000 and includes an HTTP health check against `/api/health`. Development dependencies, the local virtual environment, `.env`, Git metadata, and raw capture files are excluded from the production image.

Recorded release measurements:

| Check | Result |
|---|---|
| Final image size | approximately 191 MiB |
| Idle memory | approximately 52 MiB |
| Fresh-volume startup | 248 records and 20 documents restored |
| Health state | Docker `healthy`, API HTTP 200 |

## 2. Local orchestration

`docker-compose.yml` defines three roles over the same application code and named data volume:

| Service | Lifecycle | Purpose |
|---|---|---|
| `api` | Long-running | UI, API, SQLite, FTS5 retrieval |
| `scraper` | One-off tool | Bounded source refresh |
| `ingestion` | One-off tool | Rebuild chunks/index and seed export |

Start the application:

```bash
cp .env.example .env
docker compose up --build api
```

Refresh after the API has initialized the last-known-good seed:

```bash
docker compose run --rm scraper
docker compose run --rm ingestion
docker compose restart api
```

That ordering is intentional. An incomplete or challenged source run cannot mass-deactivate the existing good snapshot.

## 3. Persistence and startup

Runtime state lives under `/app/data`:

- `estatebot.db` contains canonical records, FTS5 chunks, conversations, messages, and scrape metadata;
- raw captures are development/audit inputs and are not required for request-time retrieval;
- a fresh empty directory is reconstructed from `/app/seed_corpus.json`, then indexed locally.

The public assessment service uses ephemeral runtime storage by design. Property data is reproducible because the normalized seed is part of the image; conversation history is session data and may disappear after a service restart. Local Compose uses a named volume so iterative development survives container restarts.

## 4. Required configuration

`.env.example` is the authoritative configuration template.

| Variable | Required | Purpose |
|---|---:|---|
| `OPENROUTER_API_KEY` | For generated answers | Server-side provider credential; never expose to the browser or repository |
| `OPENROUTER_MODEL_PRIMARY` | Yes | Automatic model choice |
| `OPENROUTER_MODEL_FALLBACK_1`, `_2` | Recommended | Bounded resilience chain |
| `OPENROUTER_SELECTABLE_MODELS` | Yes | Curated allow-list returned to the UI |
| `DATABASE_PATH` | Yes | SQLite database path |
| `SEED_CORPUS_PATH`, `SEED_ON_EMPTY` | Yes | Clean-start bootstrap |
| `RETRIEVAL_MODE` | No | Current release uses `bm25_only` |
| `MAX_RETRIEVAL_CHUNKS` | No | Context result cap, default 8 |
| `CHAT_HISTORY_TURNS` | No | Server history bound, default 8 |
| `CHAT_RATE_LIMIT_*` | No | Request budget and time window |
| `LLM_*_TIMEOUT_SECONDS` | No | Per-attempt and total model bounds |
| `CORS_ALLOWED_ORIGINS` | Yes | Explicit allowed browser origins |
| scraper limits/delays | No | Ethical crawl bounds and retry behavior |

The application remains useful without an OpenRouter key: relevant records are formatted deterministically with canonical citations. Secrets belong in the runtime secret manager, never image layers, manifests, screenshots, or documentation.

## 5. Release configuration

The checked-in `render.yaml` is the concrete public-service manifest. It selects the Docker runtime, `/api/health`, FTS5/BM25 retrieval, automatic seed initialization, and environment-backed secrets. CI must pass before a release is accepted.

Release verification requires:

1. root UI, `/api/health`, `/api/stats`, and `/docs` return successfully over HTTPS;
2. health reports the exact non-zero corpus counts;
3. a conversational prompt, no-match prompt, source-specific prompt, generic balanced prompt, and selected-model prompt behave correctly;
4. citations resolve to canonical DarGlobal/Wasalt pages;
5. validation, rate limiting, security headers, mobile layout, and transcript reset are checked;
6. the actual URL, costs, and observational limits are recorded in [`../SUBMISSION.md`](../SUBMISSION.md).

## 6. Availability and cold starts

`.github/workflows/availability-ping.yml` requests the public `/api/health` endpoint every fifteen minutes at off-hour minute marks and supports manual execution. It follows redirects, uses a bounded timeout, retries transient failures, and fails visibly unless the response confirms readiness and a non-empty corpus.

This is best-effort assessment availability, not an uptime guarantee. Scheduled jobs can be delayed or dropped, the hosting service can restart independently, and the application still needs a visible bounded waking/retry state. Manual dispatch passed against the public endpoint and confirmed the 248-record corpus. Later scheduled runs also passed and confirmed the same contract, but the observed run history is not evidence of an every-slot guarantee. A complete provider idle-window wake is also an explicitly recorded observational gap.

## 7. CI gates

`.github/workflows/ci.yml` verifies:

- the Python test suite;
- exact seed counts and both source namespaces;
- Compose configuration;
- a clean Docker image build;
- fresh-container health;
- cited chat behavior and cross-source generic retrieval.

Live OpenRouter calls are not placed in ordinary CI because free capacity is variable and a secret-backed network dependency would make correctness tests flaky. Provider routing is mocked in CI and separately checked during release QA.

## 8. Cost ledger

| Component | Implementation | Cost |
|---|---|---:|
| Web service | Free assessment service | $0 |
| LLM generation | Curated OpenRouter free models | $0 |
| Retrieval | SQLite FTS5/BM25 | $0 |
| Embeddings/vector service | Not used | $0 |
| Database | SQLite in the application runtime | $0 |
| **Total monthly** | | **$0** |

Free service and model availability can change. Recheck platform terms and OpenRouter model pricing before a future release rather than treating this dated assessment ledger as permanent.

## 9. Operational limitations

- Runtime conversation storage is not durable across public-service restarts.
- Data refresh is manual; the public service starts from the dated checked-in snapshot until a new seed is released.
- The scheduled health check reduces cold-start likelihood but does not provide production uptime.
- In-memory rate limiting is appropriate for one process; multi-instance delivery would require a shared limiter.
- SQLite is appropriate for this read-heavy corpus. A multi-instance, write-heavy product should move persistence to a managed relational database.
