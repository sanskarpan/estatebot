# Public Release QA Record

**Run date:** 2026-09-02  
**Public endpoint:** `https://estatebot-assessment.onrender.com`  
**Corpus snapshot:** `2026-09-02T14:00:00Z`  
**Configured retrieval:** `bm25_only` with deterministic structured filters  
**Configured model chain:** `google/gemma-4-31b-it:free` → `z-ai/glm-5.2:free` → `minimax/minimax-m3:free`

This record covers the public release candidate from a fresh browser tab and direct HTTPS API requests. Secrets are not recorded here. Automated provider tests remain mocked in CI; the checks below are supplementary real-network evidence.

## Release summary

| Area | Result | Evidence |
|---|---|---|
| HTTPS and service readiness | Pass | Root UI, `/api/health`, `/api/stats`, and `/docs` returned successfully over HTTPS. Warm health latency was approximately 143 ms. |
| Corpus integrity | Pass | Health/stats reported 248 active listings/projects, 20 content documents, 13 cities, and the expected snapshot timestamp. |
| Authenticated model inference | Pass | Direct provider call and deployed chatbot calls returned non-empty responses. Deployed requests exercised configured fallback models successfully. |
| Grounded citations | Pass | Citation objects resolve to retrieved canonical DarGlobal/Wasalt URLs; live DG1 citation resolved to `https://darglobal.co.uk/dg1`. |
| SSE contract | Pass | Live request emitted 10 `token` events, exactly one `done` event, and no `error` event. |
| Validation and safe errors | Pass | Blank and 2,001-character messages returned structured HTTP 400 responses; no stack traces were exposed. |
| Security headers | Pass | CSP, `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` were present. |
| Browser responsiveness | Pass | Desktop and 375×812 viewports had no horizontal overflow; textarea and Send control remained fully visible and at least 44 px high. |
| Conversation UX | Pass | Enter submitted, Shift+Enter inserted a newline, streamed content rendered, and the visible transcript survived refresh. |

## Representative prompt results

| Prompt/behavior | Grounding result | Citations | Observed behavior |
|---|---:|---:|---|
| DarGlobal villas in Oman | `true` | 8 | Returned relevant AIDA/Oman properties. |
| Price of a 2-bedroom DG1 unit | `true` | 1 | Correctly disclosed that a price was not published rather than inventing one. |
| Astera compared with Wasalt Riyadh villas | `true` | 8 | Cross-source answer used records from both sides. |
| Cheapest property in Jeddah | `true` | 3 | Used structured ordering and preserved the source's price-period ambiguity. |
| Trump-branded properties | `true` | 5 | Returned distinct relevant projects without editorializing. |
| Anything in Paris | `false` | 0 | Deterministic corpus-boundary response; no model call. |
| Follow-up: “What about 3-bedroom units there?” | `true` | 1 | Resolved “there” against the earlier DG1 turn. |
| Arabic Riyadh question | `true` | 8 | Returned a grounded Arabic response. |
| Emoji/gibberish | `false` | 0 | Graceful no-match response; no crash. |
| Prompt-injection probe | `true` | 3 | Refused/redirection behavior; no system prompt text leaked. |
| Unsupported competitor (Emaar/Damac) | `false` | 0 | Deterministic pre-generation rejection added after live QA found unrelated lexical citations; regression-covered. |

Observed successful live model responses included `z-ai/glm-5.2:free` and `minimax/minimax-m3:free`, demonstrating that the configured fallback chain remains usable when the primary route is unavailable or declined. Exact provider routing can vary between requests on free infrastructure.

## Manual 17-item script

| # | Result | Record |
|---:|---|---|
| 1 | Pass | Fresh page loaded with suggested prompts; About panel showed 248 records, 20 documents, 13 cities, model, and last-scrape time. |
| 2 | Pass | Representative grounded, unsupported, and adversarial prompts behaved as specified; details above. |
| 3 | Pass | Contextual 3-bedroom follow-up resolved to DG1. |
| 4 | Pass | Transcript remained visible after browser reload. |
| 5 | Pass | Empty input is blocked client-side; direct API returned 400. |
| 6 | Pass | Over-limit direct API request returned structured 400. |
| 7 | Pass | Arabic request returned a grounded Arabic response. |
| 8 | Pass | Emoji/gibberish returned a safe no-match result. |
| 9 | Pass | Proxy-aware threshold+1 test returned 429 with `Retry-After`; the bucket accepted requests again after the configured test window. Production settings were restored afterward. |
| 10 | Pass | Citation href, label, `_blank` target, and `noopener noreferrer` were verified against the canonical DG1 source. |
| 11 | Pass | Unsupported competitor handling returns `grounded=false`, no citations, and no model use. |
| 12 | Pass | Prompt-extraction probe did not disclose the system prompt. |
| 13 | Limited | Warm behavior and waking-state implementation were verified, but the complete free-host idle period was not observed during this release window. |
| 14 | Pass | At a measured 375×812 viewport, document/body width stayed within the viewport and the composer remained usable. |
| 15 | Pass with harness note | Native buttons, link, and textarea appear in logical DOM focus order; Enter/Shift+Enter were exercised. The browser harness could not reliably synthesize full sequential Tab traversal. |
| 16 | Pass (local) | Scraper/ingestion rerun remained idempotent and preserved soft-delete semantics. |
| 17 | Pass (local) | Clean-clone Compose build bootstrapped the checked-in seed and reached healthy state without manual data edits. |

## Performance observations

The 11-message live sample completed without timeouts or crashes. Grounded model-backed responses ranged from roughly 2.3 to 9.0 seconds in this sample; deterministic no-match responses completed in roughly 0.2 seconds. These are observations, not a statistically meaningful benchmark. Free-model and cold-start latency can vary.

## Explicit limitations

- The free host's complete idle/sleep window was not waited out during this run.
- No native screen-reader session was run; semantic browser structure and native control focusability were inspected.
- A live TCP connection was not deliberately severed mid-stream; automated tests verify that an unverified/incomplete stream is never presented as a grounded answer.
- A 50-turn visual stress session was not run; client and server history are explicitly bounded.

## Free-model selector addendum — 2026-09-03

- The live OpenRouter catalogue was reviewed and filtered to six suitable zero-cost text-answering models; selection rationale and exclusions are recorded in [`OPENROUTER-MODELS.md`](OPENROUTER-MODELS.md).
- `GET /api/models` returned the six curated choices, model labels, fallback status, and catalogue date from the public service.
- A direct public `POST /api/chat` requesting Dots3 Note Preview returned `grounded=true`, one canonical DG1 citation, a non-empty answer, and the requested model in `model_used`.
- An arbitrary non-allow-listed model ID returned HTTP 400 with `invalid_model` and was not forwarded upstream.
- In the deployed browser UI, Dots3 could be selected from the labelled custom model menu, served the answer, and appeared as “Dots3 Note Preview” in the answer attribution.
- The selected choice, transcript, and friendly actual-model disclosure survived reload.
- The product UI redesign was rechecked at desktop and 375×812 after release: the structured empty state, compact fixed composer, seven-option model menu, native About dialog, cited answer cards, copy action, transcript persistence, and responsive layout all passed. The mobile document and body widths measured exactly 375 px with no horizontal overflow.
- A refresh-only attribution defect found during this pass was fixed: restored answers now rerender after the model catalogue loads, so friendly labels replace raw provider IDs.
- Automated coverage increased to 60 passing tests, including catalogue allow-listing, selected-model-first ordering, fallback/deduplication, request propagation, actual-model reporting, degraded-answer formatting, and invalid-model rejection.
