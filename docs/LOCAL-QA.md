# Local QA Record

**Run date:** 2026-09-02
**Environment:** Python 3.12 virtualenv, Docker Desktop, local seeded data, no OpenRouter key.

## Automated and container checks

- `PYTHONPATH=. .venv/bin/python -m pytest -q`: 50 passed; one upstream Starlette/httpx deprecation warning.
- `docker compose config --quiet`: passed.
- `docker build -f backend/Dockerfile -t estatebot-api:local .`: passed.
- Fresh `docker run` with an empty `/app/data` volume: `/api/health` returned 200 and bootstrapped 36 DarGlobal projects, 180 Wasalt sale/rent listings, 32 Wasalt projects, and 20 documents.
- Fresh container chat: “What is the cheapest property in Jeddah?” returned HTTP 200, `grounded=true`, deterministic degraded mode, and five valid citation objects.
- Fresh-project `docker compose up --build -d api`: passed in an isolated Compose project; `/api/health` returned 200 with all 248 records and Docker health reached `healthy`; its temporary container, network, and volume were removed afterward.
- Bare final image startup (no Compose environment overrides): passed after Docker defaults were aligned with the embedded seed; `/api/health` returned 248 listings/projects and 20 documents.
- Clean-clone rehearsal: built all three Compose services, bootstrapped the API baseline, applied a bounded live refresh, rebuilt ingestion, restarted the API, and retained both source corpora without manual data edits. The subsequently expanded 248-record seed was revalidated independently in a fresh image volume and fresh Compose project.
- Final resource snapshot: Docker health `healthy`, 52.16 MiB idle RAM, 200,576,043-byte (~191 MiB) image.
- Live public OpenRouter model catalog check: all three configured IDs were present with prompt/completion pricing reported as zero and context windows of 262,144, 256,000, and 1,048,576 tokens respectively. This verifies configuration metadata, not authenticated inference quality.
- No API-key-shaped secret was found by the repository hygiene scan; `.env` is ignored and contains no key.

## Local behavior matrix

| Check | Result | Evidence |
|---|---|---|
| Static UI and noscript fallback | Pass | Root page served and contains EstateBot; `noscript` message is present. |
| About/stats data contract | Pass | `/api/stats` and `/api/health` agree on corpus counts and the UTC snapshot timestamp. |
| DarGlobal project questions | Pass | All 36 visible public project pages normalized; named DG1, Oman-villa, Astera comparison, and Trump-brand retrieval checks pass. |
| DarGlobal press content | Pass | All 15 articles exposed by the current public press index were normalized with source URL, title, publication date, and cleaned body text. |
| DarGlobal company content | Pass | Public About and Investor Relations pages were normalized as company-information documents; named brand partnerships remain attached to their project records. |
| Recent-news retrieval | Pass | “What is the latest DarGlobal news?” routes to press releases in descending publication-date order and cites the canonical article URL. |
| Wasalt city/category questions | Pass | Fixture and seeded smoke checks cover Jeddah, Riyadh, and Dammam. |
| Wasalt project questions | Pass | 32 visible public project pages normalized; an explicit Wasalt-projects query returns project records only, with canonical project URLs and project-owned images. |
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
| Desktop visual QA | Pass | Chrome rendered the responsive shell, About panel, live corpus stats, question/answer states, and DG1 citation chip correctly. |

## Not yet executable locally

- Live OpenRouter quality, fallback latency, and model context behavior require an API key.
- Deployed URL, HTTPS, host sleep/cold-start, persistent-volume behavior, mobile-device layout, real keyboard/screen-reader pass, and all 17 deployed manual-QA items require a hosting target and a public URL.
- The in-app browser could not load localhost in this environment (`ERR_BLOCKED_BY_CLIENT`), so browser automation was not treated as evidence of a UI failure; HTTP-level and static-file checks were used instead.
- A LAN-address desktop render succeeded in the in-app browser and matched the earlier Chrome visual pass. Programmatic mobile emulation was unavailable under the browser security policy, so the 375px and keyboard/citation checks remain deployed-manual items rather than being overstated as complete.
