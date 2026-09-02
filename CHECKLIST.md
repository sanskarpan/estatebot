# Master Build Checklist

This is the **execution plan**. Work top to bottom; each phase gates the next (don't build the chatbot before the corpus exists to test against; don't deploy before the app runs correctly in Docker locally). Every checkbox should be individually verifiable — don't check something off "roughly." Cross-reference the linked doc section for the *why* and exact requirements behind each item.

## Phase 0 — Setup

- [x] Initialize repo with the layout in `docs/02-ARCHITECTURE.md` §5.
- [ ] Create `.env` from `.env.example`; obtain an OpenRouter API key (free signup, no card required).
- [x] Query `GET https://openrouter.ai/api/v1/models`, filter for `pricing.prompt=="0"` and `pricing.completion=="0"`, pick primary + 2 fallback models per `docs/05-CHATBOT-RAG-SPEC.md` §1; set `OPENROUTER_MODEL_PRIMARY`/`_FALLBACK_1`/`_FALLBACK_2` in `.env`.
- [x] Set up Python virtual environment(s) for `backend/` and `scraper/` (may share one venv/requirements at this scale — decide and note in `docs/02-ARCHITECTURE.md` if it diverges from the two-`requirements.txt` layout).
- [x] Confirm Docker + docker-compose installed locally.

## Phase 1 — Data schema & storage foundation

- [x] Implement `Listing`, `ContentDocument` Pydantic models exactly per `docs/04-DATA-SCHEMA.md` §2–3.
- [x] Implement SQLite DDL from `docs/04-DATA-SCHEMA.md` §5 (migration script or `CREATE TABLE IF NOT EXISTS` on startup).
- [x] Implement validation rules from `docs/04-DATA-SCHEMA.md` §6 as a reusable validator function used by both scrapers.
- [x] Write unit tests for the validator against known-good and known-bad fixture records.

## Phase 2 — Scraper: DarGlobal

- [x] Implement `scraper/common/http.py`: robots.txt fetch+parse, rate limiting, retry/backoff, WAF-challenge detection — per `docs/03-DATA-SCRAPING-SPEC.md` §1 and §4.
- [x] Implement DarGlobal project-index discovery (`/projects` page parsing).
- [x] Implement DarGlobal project-detail-page parser covering all fields in `docs/03-DATA-SCRAPING-SPEC.md` §2.2–2.3.
- [x] Implement DarGlobal press/newsroom scraper (`/press`, capped at `MAX_DARGLOBAL_PRESS`).
- [ ] Implement DarGlobal about/company-info and brand-partner page scraping.
- [x] Run the DarGlobal scraper end-to-end locally; manually spot-check 5 records against the live site for accuracy.
- [x] Confirm idempotency: re-run, confirm no duplicates, `updated_at` refreshes.
- [x] Confirm graceful handling of at least one deliberately-broken case (temporarily point at a 404 URL, confirm log+skip, no crash).

## Phase 3 — Scraper: Wasalt

- [x] Investigate live Wasalt city/category landing pages: confirm whether listing content is present in raw server-rendered HTML or requires JS rendering (per `docs/03-DATA-SCRAPING-SPEC.md` §3.1 build order) — record findings in `scraper/wasalt/README.md`.
- [x] If a discoverable underlying JSON API is found during Playwright network inspection, implement direct API calls; otherwise implement HTML parsing (static or Playwright-rendered as needed).
- [x] Implement discovery across at least 3 cities × both sale and rent categories.
- [x] Implement pagination handling with `MAX_PAGES_PER_CATEGORY` cap and clean "no more results" detection.
- [x] Implement Wasalt listing-detail parser covering all fields in `docs/03-DATA-SCRAPING-SPEC.md` §3.2–3.3.
- [x] Implement city/area normalization mapping (`location_city` vs `location_city_raw`).
- [ ] Implement Wasalt "Projects"/"Plans" scraping if reachable without login (best-effort per spec).
- [x] Implement city-guide `ContentDocument` extraction from the landing pages' editorial text.
- [x] Run the Wasalt scraper end-to-end locally, capped at `MAX_WASALT_LISTINGS`; manually spot-check 8–10 records for accuracy.
- [x] Confirm idempotency and soft-delete behaviour (temporarily simulate a removed listing, confirm `is_active=false` on re-run, not a hard delete or crash).
- [x] Confirm corpus size meets minimums in `docs/01-SPEC.md` §7 (≥150 listings, ≥3 cities, both sale & rent represented).

## Phase 4 — Ingestion (chunking + embedding)

- [x] Decide embeddings vs BM25 based on a real memory-footprint measurement against the target host's budget (`docs/08-DEPLOYMENT.md` §3); document the decision.
- [x] Implement chunking rules from `docs/04-DATA-SCHEMA.md` §4.
- [x] Implement `ingestion/build_index.py`: reads all active `Listing`/`ContentDocument` rows, produces chunks, computes embeddings (or BM25 index), persists to the vector store (or index file).
- [x] Run ingestion end-to-end; confirm chunk count is sane (roughly proportional to corpus size) and a manual similarity query against a known term returns the expected chunk.
- [x] Confirm re-running ingestion after a re-scrape correctly updates the index (no stale duplicate vectors for updated records; soft-deleted records excluded from retrieval).

## Phase 5 — Retrieval layer

- [x] Implement the intent classifier (§3.1 in `docs/05-CHATBOT-RAG-SPEC.md`).
- [x] Implement the structured-filter query builder (parameterized, injection-safe SQL) reusing the same logic for both `/api/chat` internals and `/api/listings/search`.
- [x] Implement vector/BM25 similarity search wrapper with metadata filtering support.
- [x] Implement the merge/priority logic (structured results pinned, vector results filling remaining budget, deduped).
- [x] Implement the relevance threshold and "no relevant context" short-circuit.
- [x] Unit test all of the above against the fixture corpus (`docs/09-TESTING-QA.md` §2–3).

## Phase 6 — Generation & OpenRouter integration

- [x] Implement the OpenRouter client with the exact request shape in `docs/05-CHATBOT-RAG-SPEC.md` §1.2.
- [x] Implement the system prompt per §2.1, prompt assembly per §2.2, and context-budget trimming per §2.3 using a conservative bound validated against the live configured-model metadata.
- [x] Implement the fallback chain with per-attempt and total timeouts per §1.1 and §6.
- [x] Implement streaming response support (SSE) with the `event: token` / `event: done` / `event: error` shape from `docs/06-API-SPEC.md` §1.
- [x] Implement the citation-marker parsing + verification + one-retry-then-templated-fallback logic per §4.
- [x] Unit test the fallback chain and citation verifier with mocked provider responses (no live API calls in this test tier).

## Phase 7 — Backend API

- [x] Implement `POST /api/chat` (both streaming and non-streaming response modes) per `docs/06-API-SPEC.md` §1.
- [x] Implement `GET /api/health` per §2.
- [x] Implement `GET /api/stats` per §3.
- [x] Implement `GET /api/listings/{source_site}/{source_id}` per §4.
- [x] Implement `GET /api/listings/search` per §5.
- [x] Implement rate limiting per §6.
- [x] Implement CORS + security headers per §7.
- [x] Confirm `/docs` (Swagger UI) renders correctly and matches actual behaviour.
- [x] Global exception handler: confirm unexpected failures return a safe JSON 500 without a client-visible stack trace.

## Phase 8 — Frontend

- [x] Scaffold the chat UI per `docs/07-FRONTEND-SPEC.md` §2 (header, chat log, composer, suggested prompts).
- [x] Implement streaming token rendering + non-streaming fallback.
- [x] Implement citation chips + source-link behaviour.
- [x] Implement all required states from §3 (empty, sending, streaming, grounded, not-found, error, rate-limited, cold-start, long-conversation).
- [x] Implement the "About this data" panel wired to `/api/stats` and `/api/health`.
- [x] Implement responsive layout + accessibility requirements (§5).
- [x] Implement client-side timeout, retry, and `sessionStorage` conversation persistence (§6).
- [x] Implement sanitized markdown rendering and secure external links (§7).
- [ ] Manual pass: resize to mobile width, keyboard-only navigation pass, screen-reader spot check if feasible.

## Phase 9 — Containerisation

- [x] Write `backend/Dockerfile` (multi-stage, includes frontend build) per `docs/08-DEPLOYMENT.md` §1.1.
- [x] Write `scraper/Dockerfile` (or reuse backend image with a different entrypoint/command).
- [x] Write `docker-compose.yml` with `api`, `scraper`, `ingestion` services per §1.2.
- [x] Write `.dockerignore`.
- [ ] From a clean clone (or `git clean -xdf` locally as a rehearsal), run: build scraper → run scraper → run ingestion → build+run api — confirm success end-to-end with zero manual file edits beyond `.env`.
- [x] Confirm the built image's `HEALTHCHECK` reports healthy.
- [x] Confirm final image size and measured runtime memory usage against the §3 resource-sizing budget.

## Phase 10 — Testing

- [x] Write/complete unit tests per `docs/09-TESTING-QA.md` §2 — run locally, all green.
- [x] Write/complete integration tests against the fixture corpus with mocked OpenRouter — all green.
- [x] Set up CI (GitHub Actions or equivalent) to run the above on push, if time allows — not a hard requirement, but strengthens the submission; if skipped, note it as a deliberate scope decision in `SUBMISSION.md`.
- [x] Run a lightweight load/burst test to confirm rate limiting behaves per spec.

## Phase 11 — Deployment

- [x] Choose and record the hosting platform per `docs/08-DEPLOYMENT.md` §2 decision.
- [ ] Provision the service, set all env vars from `.env.example`/§4, attach persistent storage (or document the rebuild-on-deploy fallback).
- [ ] Deploy; confirm `/api/health` is `200` with real corpus stats.
- [ ] Confirm the public URL loads the chat UI and a live end-to-end chat exchange works with a real OpenRouter call.
- [ ] Confirm HTTPS is active (most platforms provide this automatically) — never ship an HTTP-only public URL.
- [ ] Note actual cold-start behaviour, if any, and confirm the frontend's cold-start UI state actually triggers/looks right in that scenario.

## Phase 12 — Final QA & submission

- [ ] Execute the full 17-item manual QA script in `docs/09-TESTING-QA.md` §4 against the **deployed** URL; record results.
- [ ] Re-check every row of the traceability table in `docs/01-SPEC.md` §2 — all sub-items A/B/C satisfied.
- [ ] Re-read `docs/10-EDGE-CASES.md` top to bottom; confirm each row's required behaviour actually holds (spot-test the ones not already covered by automated tests).
- [ ] Fill in `SUBMISSION.md` completely: live URL, repo link, actual corpus stats, actual model(s) used, actual hosting platform, cost ledger, known limitations.
- [x] Grep the repo for the literal OpenRouter API key value / any other secret to confirm nothing is committed.
- [ ] Final fresh-eyes pass: open the URL in a private/incognito window as if you were the reviewer seeing it for the first time, and run through the 9 use cases in `docs/01-SPEC.md` §4 one more time.
- [ ] Submit: send the URL + repo link per `SUBMISSION.md`.
