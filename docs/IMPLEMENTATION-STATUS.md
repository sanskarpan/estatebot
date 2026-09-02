# Implementation Status & Evidence

**Recorded:** 2026-09-02 (Asia/Kolkata)
**Scope:** local build and verification pass for the EstateBot assessment.

## What is implemented

- FastAPI service with `/api/chat`, `/api/health`, `/api/stats`, listing lookup, listing search, JSON responses, and buffered/verified SSE responses.
- Responsive static chat UI with source chips, About panel, local transcript persistence, loading/error/retry states, keyboard-friendly controls, and prompt-injection-safe rendering.
- Pydantic validation and SQLite persistence with WAL mode, foreign keys, JSON fields, FTS5/BM25 chunks, conversation history, scrape-run metadata, composite `(source_site, source_id)` identity, and inactive-record handling (`404` unknown / `410` known inactive).
- Deterministic query planning for named entities, cross-source comparisons, source, city, country, category, sale/rent, bedrooms, price bounds, currency, and cheapest/most-expensive ordering. Explicit constraints use structured SQL first and preserve SQL ordering.
- OpenRouter generation with a configurable free-model fallback chain, bounded per-attempt/total timeouts, context truncation, citation-marker verification, strict regeneration, and deterministic degraded answers when no key/provider is available.
- Polite, cached, bounded scraper infrastructure with robots handling, descriptive user-agent, delay, retries, WAF/challenge detection, domain circuit breaking, raw snapshots, and safe deactivation only after complete discovery.
- DarGlobal and Wasalt parser packages, source-specific normalization, sitemap fallback, auditable standard-browser DarGlobal project/press capture import, city-guide documents, index builder, seed export, fixtures, and automated tests.
- Docker multi-stage API image, separate scraper image, Compose tool profiles, persistent data volume, health check, and offline seed bootstrap for a clean API volume.
- GitHub Actions test/container-smoke workflow and a Render Blueprint configured to deploy only after CI checks pass.

## Verified local evidence

| Check | Result |
|---|---|
| `PYTHONPATH=. .venv/bin/python -m pytest -q` | 34 passed; one upstream Starlette/httpx deprecation warning |
| `docker compose config --quiet` | Passed |
| API image build | Passed (`estatebot-api:local`) |
| Fresh-container `/api/health` | HTTP 200; 36 DarGlobal + 180 Wasalt records loaded from seed |
| Fresh-container `/api/chat` | HTTP 200; named-project and cross-source responses grounded with valid citations |
| Current active listings | 216 total: 36 DarGlobal projects and 180 Wasalt listings |
| Current content documents | 20 total: 15 dated DarGlobal press releases, 2 DarGlobal company documents, and 3 Wasalt city guides |
| Cities | Benahavís, Dammam, Doha, Dubai, Jeddah, London, Muscat, Ras Al Khaimah, Riyadh |
| Countries | Maldives, Oman, Qatar, Saudi Arabia, Spain, United Arab Emirates, United Kingdom |
| Search index | 785 active chunks |
| Runtime resource check | Healthy container at 51.8 MiB idle RAM; 200,409,071-byte (~191 MiB) image |
| OpenRouter catalog check | All three configured IDs present with zero prompt/completion pricing; context windows 262,144 / 256,000 / 1,048,576 tokens |

The first 150-row crawl contained three landing-page false positives; those rows were removed, the discovery filter was corrected for ordinary links and JSON-LD, and a small bounded follow-up crawl produced 180 genuine detail records. The index and seed were then regenerated.

## Live-source findings

The scraper was exercised against the live public sites. DarGlobal plain-HTTP probes returned an Incapsula shell, so the HTTP crawler correctly skipped them. The same public project index, all 36 linked project pages, all 15 articles exposed by the current press index, and the About/Investor Relations pages loaded normally in a standard unauthenticated browser; their visible DOM was captured and imported through a dedicated, tested normalization path without exporting cookies or solving/bypassing a challenge. The press index's visible “Load More” control did not expose additional links in this session. Wasalt robots and CDN sitemaps were readable, and a bounded detail crawl produced 180 records. Full evidence is in [`scraper/live-findings.md`](../scraper/live-findings.md).

## Remaining release gates

1. Configure a real OpenRouter API key in the deployment secret store and run live model fallback/manual QA. Local deterministic mode and mocked provider fallback are verified.
2. Push the repository to an accessible remote and connect the included `render.yaml` Blueprint. No hosting account, remote repository URL, or deployment credentials are available in this workspace.
3. Execute and record the 17-item deployed-URL manual QA script from [`docs/09-TESTING-QA.md`](09-TESTING-QA.md), including mobile, keyboard, cold-start, citation-link, and rate-limit checks.

Until these gates are closed, `SUBMISSION.md` is intentionally not marked as a final submission; the two-source corpus and application are complete locally, but public delivery is not yet proven.
