# DarGlobal × Wasalt Real Estate AI Chatbot

[![EstateBot CI](https://github.com/sanskarpan/estatebot/actions/workflows/ci.yml/badge.svg)](https://github.com/sanskarpan/estatebot/actions/workflows/ci.yml)

**Assignment:** AI Full Stack Engineer / Forward Deployed Engineer (FDE) — Technical Assessment
**Deliverable type:** Deployed, publicly reachable AI chatbot grounded in scraped data from [DarGlobal](https://darglobal.co.uk) and [Wasalt](https://wasalt.sa) (also reachable via `wasalt.com`), containerised with Docker, powered by a free model on [OpenRouter](https://openrouter.ai).

This repository is a **complete implementation and delivery package**: runnable application code, auditable source captures, a normalized seed corpus, automated tests, container/deployment configuration, and the specifications and decision records behind them. The documentation remains deliberately explicit so another engineer can reproduce, audit, refresh, and deploy the system without reverse-engineering its intent.

> **Current repository status:** the runnable local implementation and two-source seed corpus are present: 36 DarGlobal projects, 15 DarGlobal press releases, 2 DarGlobal company documents, 180 Wasalt sale/rent listings, 32 Wasalt projects, and 3 Wasalt city guides. Both sites' visible public pages that required a normal browser path were captured and imported through dedicated auditable normalizers; see [`scraper/live-findings.md`](scraper/live-findings.md). Public deployment and live OpenRouter QA still require account credentials. See [`docs/IMPLEMENTATION-STATUS.md`](docs/IMPLEMENTATION-STATUS.md) for evidence and remaining gates.

## Run locally

```bash
cp .env.example .env
docker compose up --build api
```

Open `http://localhost:8000`. A fresh data volume bootstraps from the checked-in `data/seed_corpus.json`, so the UI is usable without an API key; it falls back to deterministic, cited answers when OpenRouter is not configured. Let the API initialize that baseline before the first refresh. Then run `docker compose run --rm scraper`, `docker compose run --rm ingestion`, and `docker compose restart api`; partial or challenged refreshes preserve the last good source records.

For a Python-only development setup, install `backend/requirements-dev.txt`, then run `PYTHONPATH=. .venv/bin/python -m pytest` and `make run-api`.

For deployment, push the repository and create a Render Blueprint from [`render.yaml`](render.yaml); provide the OpenRouter key and assigned HTTPS URL as dashboard secrets. The free-tier deployment reconstructs its ephemeral SQLite/FTS5 database from the checked-in seed at startup.

---

## How to use this package

If you are an AI assistant (or engineer) picking this up cold, read the documents **in this order**:

| # | Document | Purpose |
|---|----------|---------|
| 0 | `README.md` (this file) | Orientation, scope, definitions, how the docs fit together |
| 1 | `docs/01-SPEC.md` | The product/functional specification — what "done" means |
| 2 | `docs/02-ARCHITECTURE.md` | System design, component diagram, data flow, tech stack decisions + rationale |
| 3 | `docs/03-DATA-SCRAPING-SPEC.md` | Exactly what to scrape from DarGlobal & Wasalt, how, legally, and how to handle failures |
| 4 | `docs/04-DATA-SCHEMA.md` | Canonical data model (JSON Schema + SQL DDL) that scraper output must conform to |
| 5 | `docs/05-CHATBOT-RAG-SPEC.md` | Retrieval-augmented generation design, OpenRouter model selection/fallback, prompt contracts |
| 6 | `docs/06-API-SPEC.md` | Backend REST/streaming API contract (OpenAPI-style) |
| 7 | `docs/07-FRONTEND-SPEC.md` | Chat UI requirements, states, accessibility, responsive behaviour |
| 8 | `docs/08-DEPLOYMENT.md` | Docker, docker-compose, hosting target options, environment variables, CI/CD, secrets |
| 9 | `docs/09-TESTING-QA.md` | Test plan: unit/integration/e2e, manual QA script, performance & security testing |
| 10 | `docs/10-EDGE-CASES.md` | Exhaustive edge-case catalog across scraping, data, RAG, chat, infra |
| 11 | `docs/EDGE-CASE-TRACEABILITY.md` | Evidence map from every edge case to automated, inspected, live, or pending deployed QA |
| 12 | `CHECKLIST.md` | The master, sequential, checkbox-driven build checklist — the actual execution plan |
| 13 | `SUBMISSION.md` | What must be true before you say "done"; maps every assignment requirement to concrete deliverables |
| — | `.env.example` | Every environment variable the system needs, documented |

**Rule of thumb:** `docs/*.md` define *what* and *why*. `CHECKLIST.md` defines *in what order* and *how to verify each step*. `SUBMISSION.md` is the final gate. If any instruction in `CHECKLIST.md` seems to conflict with a `docs/*.md` file, the `docs/*.md` file is authoritative — the checklist is a task-tracker, not a spec.

---

## Assignment requirements (verbatim, for traceability)

1. Scrape publicly available data from DarGlobal and Wasalt.
2. Build an AI chatbot using the collected data.
3. Use any suitable free model available through OpenRouter.
4. Containerise the application using Docker.
5. Deploy the solution rather than submitting source code only.
6. Provide a working URL so the reviewer can access and test the chatbot directly.

Every one of these six lines is expanded into concrete, testable acceptance criteria in `docs/01-SPEC.md` §2 and re-verified in `SUBMISSION.md`.

## What this package deliberately adds beyond the literal brief

The brief is short by design — it's testing judgement, not just compliance. This package intentionally goes further, because an FDE is evaluated on production-readiness, not on ticking four boxes:

- **Data governance & legality** — robots.txt compliance, rate-limiting, ToS awareness, attribution, and a documented "what we did NOT scrape and why" section (§ Legal & Ethical Scope in `docs/03-DATA-SCRAPING-SPEC.md`).
- **Grounded, hallucination-resistant answers** — retrieval-augmented generation over the scraped corpus, with explicit "I don't know from the available data" behaviour, source citation, and price/number verification before the answer leaves the pipeline.
- **Resilience** — free OpenRouter models are volatile (rate limits, deprecation, downtime). The spec defines a multi-model fallback chain and graceful degradation rather than a single hardcoded model string.
- **Operability** — health checks, structured logs, basic metrics, and a re-runnable, idempotent scraper — not a one-off script.
- **Reviewer experience** — the deployed URL must load fast, explain itself (a short "About this data" note and last-scraped timestamp visible in the UI), and survive a reviewer asking odd or adversarial questions.

## Project identity

- **Working name:** `estatebot` (used as the Docker image name / repo slug / env var prefix throughout the docs — rename freely, but keep it consistent across all files if you do).
- **Primary language:** Python 3.12 (backend + scraper) — see `docs/02-ARCHITECTURE.md` §3 for the stack decision record, including alternatives considered.
- **Primary data sources:**
  - DarGlobal: `https://darglobal.co.uk` — luxury developer, ~40–70 static, server-rendered project pages plus a newsroom/press section. Low page count, low volatility, no visible login wall.
  - Wasalt: `https://wasalt.sa` (redirects also served from `wasalt.com`) — large-scale KSA property marketplace (buy/rent/projects/plans/auctions) across multiple cities. High page count, paginated/filterable listings, more dynamic.

## Glossary

- **Listing** — an individual property/unit record scraped from either source (an apartment, villa, plot, or off-plan unit).
- **Project** — a development/building/community that groups one or more listings (e.g. "DG1" on DarGlobal groups many units).
- **Corpus** — the normalized, deduplicated collection of listings + projects + supporting content (FAQs, area guides, press releases) used for retrieval.
- **RAG** — retrieval-augmented generation: retrieve relevant corpus chunks, inject into the LLM prompt, generate a grounded answer.
- **Free model** — an OpenRouter model with `pricing.prompt == 0` and `pricing.completion == 0` at the `:free` variant suffix.

Proceed to `docs/01-SPEC.md`.
