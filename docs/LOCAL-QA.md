# Local QA Record

**Run date:** 2026-09-02
**Environment:** Python 3.12 virtualenv, Docker Desktop, local seeded data, no OpenRouter key.

## Automated and container checks

- `PYTHONPATH=. .venv/bin/python -m pytest -q`: 33 passed; one upstream Starlette/httpx deprecation warning.
- `docker compose config --quiet`: passed.
- `docker build -f backend/Dockerfile -t estatebot-api:local .`: passed.
- Fresh `docker run` with an empty `/app/data` volume: `/api/health` returned 200 and bootstrapped 36 DarGlobal projects, 180 Wasalt listings, and 18 documents.
- Fresh container chat: “What is the cheapest property in Jeddah?” returned HTTP 200, `grounded=true`, deterministic degraded mode, and five valid citation objects.
- Fresh-project `docker compose up --build -d api`: passed; `/api/health` returned 200 with all 216 records; the temporary test volume was removed afterward.
- Bare final image startup (no Compose environment overrides): passed after Docker defaults were aligned with the embedded seed; `/api/health` returned 216 listings and 18 documents.
- Final resource snapshot: Docker health `healthy`, 51.8 MiB idle RAM, 200,409,071-byte (~191 MiB) image.
- Live public OpenRouter model catalog check: all three configured IDs were present with prompt/completion pricing reported as zero and context windows of 262,144, 256,000, and 1,048,576 tokens respectively. This verifies configuration metadata, not authenticated inference quality.
- No API-key-shaped secret was found by the repository hygiene scan; `.env` is ignored and contains no key.

## Local behavior matrix

| Check | Result | Evidence |
|---|---|---|
| Static UI and noscript fallback | Pass | Root page served and contains EstateBot; `noscript` message is present. |
| About/stats data contract | Pass | `/api/stats` and `/api/health` agree on corpus counts and the UTC snapshot timestamp. |
| DarGlobal project questions | Pass | All 36 visible public project pages normalized; named DG1, Oman-villa, Astera comparison, and Trump-brand retrieval checks pass. |
| DarGlobal press content | Pass | All 15 articles exposed by the current public press index were normalized with source URL, title, publication date, and cleaned body text. |
| Recent-news retrieval | Pass | “What is the latest DarGlobal news?” routes to press releases in descending publication-date order and cites the canonical article URL. |
| Wasalt city/category questions | Pass | Fixture and seeded smoke checks cover Jeddah, Riyadh, and Dammam. |
| Numeric/superlative query | Pass | Structured SQL excludes null prices and preserves ascending order for “cheapest”. |
| Unknown geography | Pass | “Are there villas in Paris?” produces an explicit no-match result without retrieval context. |
| Unknown listing / inactive listing | Pass | Unknown lookup returns 404; known inactive lookup returns 410. |
| OpenRouter primary failure | Pass | Mocked 429 causes fallback model selection; all-provider absence uses deterministic facts. |
| SSE | Pass | Response emits `event: token` followed by verified `event: done`. |
| Input validation | Pass | Blank messages and over-limit payloads return clean 400 responses. |
| Unexpected server error | Pass | Catch-all handler logs server-side details and returns a generic JSON 500 without leaking exception text. |
| Rate limit | Pass | Threshold+1 test returns 429 with `Retry-After`. |
| Citation links | Pass | Every emitted citation is created from the retrieved source URL, not model-supplied URLs. |
| Scraper safety | Pass | Robots handling, WAF detection, bounded retries, cache, and circuit-breaker logic are unit-covered or live-observed. |
| Desktop visual QA | Pass | Chrome rendered the responsive shell, About panel, 216-record stats, question/answer states, and DG1 citation chip correctly. |

## Not yet executable locally

- Live OpenRouter quality, fallback latency, and model context behavior require an API key.
- Deployed URL, HTTPS, host sleep/cold-start, persistent-volume behavior, mobile-device layout, real keyboard/screen-reader pass, and all 17 deployed manual-QA items require a hosting target and a public URL.
- The in-app browser could not load localhost in this environment (`ERR_BLOCKED_BY_CLIENT`), so browser automation was not treated as evidence of a UI failure; HTTP-level and static-file checks were used instead.
