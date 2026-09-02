# Public Release QA Record

**Run date:** 2026-09-02  
**Public endpoint:** `https://estatebot-assessment.onrender.com`  
**Corpus snapshot:** `2026-09-02T14:00:00Z`  
**Configured retrieval:** `bm25_only` with deterministic structured filters  
**Configured model chain:** `google/gemma-4-31b-it:free` → `z-ai/glm-5.2:free` → `minimax/minimax-m3:free`

This record covers the public release from a fresh browser tab and direct HTTPS API requests. Secrets are not recorded here. Automated provider tests remain mocked in CI; the checks below are supplementary real-network evidence.

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
| 1 | Pass | Fresh page loaded with suggested prompts; the About dialog showed 248 records, 20 documents, 13 cities, 7 countries, 2 sources, 6 models, and last-scrape time. |
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

- The fifteen-minute health check is configured and its public health request passed by manual dispatch. No schedule-triggered run appeared during the observed release slots, and the free host's complete idle/sleep window was not waited out, so this remains best-effort mitigation rather than an uptime claim.
- No native screen-reader session was run; semantic browser structure and native control focusability were inspected.
- A live TCP connection was not deliberately severed mid-stream; automated tests verify that an unverified/incomplete stream is never presented as a grounded answer.
- A 51-turn visual stress session was completed in the later adversarial hardening pass; the DOM and restored transcript remained capped at 100 messages.

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

## Conversational and scope regression addendum — 2026-09-03

- The reported `hello` failure was reproduced and corrected. On the public UI, the user bubble measured 61×43 px and rendered “hello” on one line; EstateBot returned a useful conversational response without invoking a model or showing a source-verification label.
- Unmatched geography now displays the literal “No matching source data” state. The misleading generic “Verified data response” label and irrelevant Copy action are absent.
- “Which locations do you cover?” returned all 13 corpus cities and all 7 countries, including Dubai, London, Muscat, and the United Arab Emirates, while clearly stating that EstateBot is corpus-bound rather than a worldwide search engine.
- The first-run screen now exposes the 13-city/7-country breadth and leads with a Dubai example instead of visually implying Riyadh-only coverage. The About dialog shows both city and country counts.
- Automated coverage increased to 62 passing tests, including deterministic greeting routing, provider-call avoidance for greetings, location coverage, and the existing unsupported-developer guard.

## Source-balance and availability addendum — 2026-09-03

- The corpus was reconfirmed at 36 DarGlobal projects and 212 Wasalt records. Explicit DarGlobal prompts already returned DarGlobal data; the observed defect affected generic queries because the larger Wasalt set could exhaust the result limit first.
- Unspecified-source structured retrieval now alternates available candidates from DarGlobal and Wasalt. Explicit source filters, named entities, and global cheapest/most-expensive ordering are unchanged.
- On the public UI, “What villas are available?” returned eight verified citations split evenly: four DarGlobal Oman projects and four Wasalt Saudi projects. The answer visibly grouped both providers.
- The clean-container CI smoke check now requires a generic villa answer to contain both source identifiers. Automated coverage increased to 64 passing tests.
- `.github/workflows/availability-ping.yml` supports scheduled and manual dispatch. Its first manual run passed against `/api/health`. A later operational audit corrected the cadence and strengthened response validation; this remains best-effort cold-start mitigation, not an uptime guarantee.

## Adversarial hardening and rich-card addendum — 2026-09-03

- The public release passed the 74-test suite and clean-container CI smoke flow. The release was then exercised directly through HTTPS and a fresh browser session; full cases are recorded in [`ADVERSARIAL-QA.md`](ADVERSARIAL-QA.md).
- Greeting, neutral coverage, unsupported geography/developer, prompt extraction, malformed source wording, numeric gibberish, suffix currencies, fresh-topic context isolation, and referential follow-ups were all rechecked.
- Public QA found and corrected one additional wording gap: `Show me villas from madeuphomes` now asks the user to clarify the source instead of returning unrelated generic villas.
- Generic villa results rendered eight structured cards: four DarGlobal and four Wasalt. Six remote property images loaded successfully; canonical links, metadata, currency labels, and image fallbacks were inspected.
- The textarea no longer uses native required validation and its accessible composer-level focus state replaces the former orange inner rectangle and browser tooltip.
- The seven-option model menu stayed inside the mobile viewport. A Gemma 4 31B selection was sent to the public API; when that free route did not complete, the successful MiniMax M3 fallback was visibly and correctly disclosed.
- New chat cleared messages, draft, transient state, and conversation context while intentionally retaining the selected model preference. Mobile cards and composer remained within the viewport without horizontal overflow.

## Professional visual-system addendum — 2026-09-03

- The released empty state now presents a property-research workspace rather than a generic chatbot splash: a modern system-sans hierarchy, subtle data grid, restrained green emphasis, and live indexed-record/source/model signals were verified in the public browser.
- Raw character icons were removed from the interface. Corpus state, model routing, keyboard hint, close controls, assistant identity, source labels, external links, and missing-property imagery now share one inline-SVG language.
- Property cards received stronger hierarchy, consistent image treatment, vector fallbacks, clearer metadata, and restrained elevation. A public `Show villas from both sources` request rendered eight cards split four DarGlobal/four Wasalt, including two clean image fallbacks.
- The model selector exposed all seven options and remained entirely inside the mobile viewport. The About dialog, header controls, composer, focus states, and capability metrics were also rechecked at desktop and the smallest supported mobile width.
- Browser QA found and corrected two additional issues during this visual pass: generic `both/all sources` language was initially mistaken for an unknown provider, and the New chat toast overlapped the mobile composer. Both now have regression coverage or measured browser verification.
- The final suite contains 75 passing tests. CI also passed Compose validation, a clean image build, seeded startup, and container smoke checks for commit `4b2eb0b`.

## Availability and release-parity audit — 2026-09-03

- The prior cron expression intended a ten-minute cadence, but GitHub showed only a manual run and no scheduled history. It was replaced with explicit fifteen-minute off-hour marks (`5,20,35,50`) and the workflow was re-enabled to refresh scheduler registration.
- The health step now follows redirects, retries transient failures, parses the response, and fails unless `status` is `ok` and `corpus.listings_total` is positive.
- Manual run `33682389121` completed successfully at commit `6043598`, reporting `EstateBot ready: 248 records; uptime=118s`. The associated CI run `33682379353` also passed.
- No `schedule` event appeared during the observed 21:05, 21:20, or post-registration 21:35 UTC slots, including a five-minute allowance after the last slot. This audit therefore verifies the probe and configuration, not reliable scheduler execution or continuous uptime.
- A direct public health request at 21:41 UTC returned `status=ok`, 248 records, and process uptime of four seconds. The service recovered correctly, but the short uptime corroborates that it had recently restarted or woken; it does not support a keep-awake claim.
- Public `/api/health`, `/api/models`, and `/api/corpus/stats` responses matched the release expectations: 248 records, 36 DarGlobal records, 212 Wasalt records, 20 documents, 13 cities, 7 countries, six selectable free models, fallback enabled, and BM25-only retrieval.
- The public HTML, JavaScript, and CSS were byte-for-byte identical to the checked-in assets by SHA-256. Fresh-browser checks also passed greeting behavior, single-line message rendering, source-label suppression for uncited responses, New chat isolation, the seven-option selector, and mobile overflow.
- Direct public API regression passed greeting, coverage, unknown-source, both-source, unsupported-developer, prompt-extraction, out-of-corpus, invalid-model, and multi-turn location-isolation cases.
