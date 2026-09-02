# 10 — Edge Case Catalog

Exhaustive, categorized list of edge cases the implementation must handle. Each row states the case and the required behaviour. Treat every row as a testable assertion — most map directly to a unit test (`docs/09-TESTING-QA.md`) or a manual QA step.

## 1. Scraping & source-data edge cases

| # | Case | Required behaviour |
|---|---|---|
| 1.1 | Target page returns 404/410 after being discovered from a listing/index page | Log, skip, don't crash the run; if a previously-stored record, soft-delete it (`is_active=false`). |
| 1.2 | Target page structure changes (selector not found) | Log structured warning with URL + missing field, degrade to `null` for that field or skip the record if a required field is missing; continue the run. |
| 1.3 | WAF/CAPTCHA challenge page returned instead of content | Detect via signature check, back off, retry bounded number of times, then skip — never attempt to solve/bypass. |
| 1.4 | Price not published (common on DarGlobal) | Store `null`, never estimate/infer; downstream must handle `null` price gracefully in both filtering and generation (never say a number that wasn't scraped). |
| 1.5 | Price shown as a range or "starting from" text | Parse the lower bound into `price_amount` if unambiguous, and always preserve the full raw text in `price_display_text`; if ambiguous, leave `price_amount` null and rely on `price_display_text`. |
| 1.6 | Same project reachable via multiple URLs (referrer-tagged query strings, nested vs. flat paths) | Canonicalize and dedupe by normalized path; one record per real-world entity. |
| 1.7 | Listing removed between crawl-discovery and detail-page fetch (race condition within a single run) | Treat as case 1.1 — log and skip/soft-delete, don't error the whole run. |
| 1.8 | Duplicate content across `wasalt.sa` and `wasalt.com` | Dedupe by normalized content/reference key before persisting; keep whichever canonical URL actually resolves. |
| 1.9 | Pagination that never signals "end" cleanly (infinite scroll, or a "next" link that loops) | Enforce a hard page cap (`MAX_PAGES_PER_CATEGORY`) regardless of signal reliability. |
| 1.10 | Mixed-language content (Arabic text present on an `/en/` page) | Store verbatim, tag `description_lang`, never drop or mistranslate silently. |
| 1.11 | Currency ambiguity (symbol without clear currency, e.g. just a number) | Infer currency from page locale/context (AED for DarGlobal UAE pages, SAR for Wasalt) only when unambiguous from surrounding text; otherwise leave `price_currency` null alongside `price_amount` null and keep raw text. |
| 1.12 | robots.txt disallows a path the assignment would otherwise want | Respect the disallow — document the resulting gap in `docs/03-DATA-SCRAPING-SPEC.md` §7-style "not scraped" list rather than overriding it. |
| 1.13 | robots.txt itself unreachable | Fall back to the conservative default (marketing/listing pages only) per `docs/03-DATA-SCRAPING-SPEC.md` §6, log clearly. |
| 1.14 | Extremely long description text (multi-thousand words on a press article) | Chunk per `docs/04-DATA-SCHEMA.md` §4 chunking rule rather than truncating or embedding as one oversized vector. |
| 1.15 | HTML entities / encoding artifacts in scraped text (`&amp;`, curly quotes, non-breaking spaces) | Decode/normalize during parsing, not left raw in stored text or later shown garbled in chat answers. |
| 1.16 | A "Trump"-branded or other-politically-salient project name | Treat exactly like any other project name — store and answer factually from source content; do not editorialize, and do not refuse to discuss it (it's public real-estate marketing content, not a request for political commentary). |
| 1.17 | Scrape run interrupted mid-way (process killed, host restart) | Incremental per-record upserts mean partial progress is preserved; safe to re-run. |
| 1.18 | Two projects with very similar/identical names across sources (unlikely but possible) | `(source_site, source_id)` uniqueness plus retrieval always carrying `source_site` in citations prevents conflation; never merge cross-source records into one. |

## 2. Data modeling & normalization edge cases

| # | Case | Required behaviour |
|---|---|---|
| 2.1 | City name variants ("Al-Khobar" vs "Khobar", "Makkah" vs "Mecca") | Normalize into `location_city` via controlled mapping; retain `location_city_raw` for audit. |
| 2.2 | Bedroom count given as a range ("1-3 bedrooms") on a project (not a single unit) | Store as `bedrooms_min`/`bedrooms_max` range, not a single misleading value. |
| 2.3 | Studio units | `bedrooms_min = bedrooms_max = 0`, `unit_types_normalized` includes `"studio"` — must not be confused with "unknown"/null. |
| 2.4 | Area given only as a range across an entire project, not per-unit | Store as `area_sqm_min`/`area_sqm_max` at the project level; the chatbot must phrase answers about area as project-level ranges, not per-unit facts, when that's what was actually scraped. |
| 2.5 | A listing legitimately has no image | `image_urls: []`, not null-vs-empty inconsistency; frontend/UI must handle an empty gallery gracefully if images are ever surfaced. |
| 2.6 | A listing's `expected_completion_date` given as a quarter/year only ("Q4 2027" or just "2027") | Store the best-effort parsed date (e.g. first day of period) in `expected_completion_date` AND always keep `expected_completion_raw` — answers should quote the raw text, not a falsely-precise parsed date. |
| 2.7 | Amenities list has near-duplicate entries across scrapes due to markup changes ("Gym" vs "State-of-the-art Gym") | Not required to fully dedupe semantically at scrape time — acceptable to store as-scraped; retrieval/generation should not be materially harmed by minor duplication. Flag as a known limitation if observed, don't over-engineer a fix for this narrow issue. |

## 3. Retrieval & RAG edge cases

| # | Case | Required behaviour |
|---|---|---|
| 3.1 | Query with no relevant corpus match at all | Deterministic "not found" response (§3.2 in `docs/05-CHATBOT-RAG-SPEC.md`), never a forced/hallucinated answer. |
| 3.2 | Query with a structured filter matching zero rows (valid criteria, no results) | Explicitly say nothing matched *that specific* criterion; optionally suggest a close alternative; never silently substitute unrelated results. |
| 3.3 | Query mixing a valid filter with an invalid one ("villas in Mars under 1M AED") | Recognize the unresolvable location term, state plainly it isn't recognized/covered, don't silently drop it and answer as if only the price filter existed. |
| 3.4 | Superlative query when multiple records tie ("cheapest villa" with 2+ equal lowest prices) | Return all tied results, don't arbitrarily pick one and imply uniqueness. |
| 3.5 | Query referencing a property that existed at scrape time but is now soft-deleted | Still answer from stored data if directly asked by name, but note it may no longer be listed/active as of the last scrape — don't pretend total ignorance of something once known, and don't present stale data as current without the caveat. |
| 3.6 | Cross-source comparison query ("DarGlobal vs Wasalt villas in the same city") | Correctly retrieve and represent both sources; citations must show the mixed `source_site` values distinctly, not merge into one undifferentiated answer. |
| 3.7 | Currency-crossing comparison ("is the DarGlobal Dubai unit cheaper than a Wasalt Riyadh villa") when one is AED/null and the other SAR | Never silently equate different currencies as if numerically comparable; either state both figures with currencies explicit and note conversion wasn't performed, or perform an explicit, clearly-labeled approximate conversion only if the system is built to do so deliberately (not implicitly). |
| 3.8 | Vector store returns technically-similar but factually-irrelevant chunks (semantic drift) | Relevance threshold (§3.2 in `docs/05-CHATBOT-RAG-SPEC.md`) filters these before they reach the prompt; if borderline, the groundedness system-prompt rule and citation verification are the second and third lines of defense. |
| 3.9 | Extremely broad query ("tell me about everything you have") | Should not attempt to cram the entire corpus into one response; respond with a structured overview (counts by source/city/category) and invite narrowing, rather than truncating arbitrarily or erroring on context overflow. |
| 3.10 | Model context window smaller than the default chunk/history budget (a small free model) | Verify every configured model's live `context_length` before deployment and keep the fixed top-k/per-chunk/history caps below the smallest supported window (§2.3 in `docs/05-CHATBOT-RAG-SPEC.md`); lower the caps before accepting any smaller replacement model. Runtime startup must not depend on the catalog endpoint. |

## 4. Chat/UX & abuse edge cases

| # | Case | Required behaviour |
|---|---|---|
| 4.1 | Empty message | `400`, friendly inline handling client-side too (disable send on empty input). |
| 4.2 | Extremely long message (over cap) | `400` with a clear "message too long" error, not silent truncation (silent truncation could change the user's intended meaning). |
| 4.3 | Non-English input (Arabic, etc.) | Respond sensibly — either answer if feasible or explain the limitation — never a raw error. |
| 4.4 | Emoji-only / gibberish input | No crash; a graceful "I'm not sure what you're asking — could you rephrase?" style response. |
| 4.5 | Prompt injection attempts (embedded in user message OR present inside scraped source content itself) | Neither surface can override system instructions; system prompt leakage never occurs (§7 in `docs/05-CHATBOT-RAG-SPEC.md`). |
| 4.6 | Off-topic requests (general knowledge, coding help, unrelated chit-chat) | Politely decline/redirect to real-estate Q&A about the two sources; don't silently answer off-topic questions from the model's general knowledge (breaks the groundedness value proposition and scope in `docs/01-SPEC.md` §3). |
| 4.7 | Requests for opinions/defamatory claims about named individuals (executives, brokers) | Decline to speculate; only relay factual, sourced statements that actually appear in scraped content. |
| 4.8 | Rapid-fire burst of requests (rate-limit trigger) | `429` + `Retry-After`, UI countdown, graceful re-enable after window — never a crash or unbounded queue growth. |
| 4.9 | Model provider outage (primary AND all fallbacks down simultaneously) | Deterministic degraded response built from retrieved structured facts without generation — the user still gets something useful, never a raw 500. |
| 4.10 | Streaming connection dropped mid-response (client network blip) | Backend request still completes server-side (message persisted); client shows a clear "connection interrupted" state with a retry option that can re-fetch or continue the conversation, not silent data loss. |
| 4.11 | User asks the same question twice in a row | No special-casing needed — deterministic-enough pipeline (structured filters + verified citations) should give consistent, correct answers both times even though the LLM's exact phrasing may vary; consistency of *facts*, not verbatim text, is the requirement. |
| 4.12 | Browser with JS disabled or a very old browser | Not a hard requirement to fully support, but the app must not present a totally blank white page — a `<noscript>` message is sufficient minimum handling. |
| 4.13 | Conversation grows very long (50+ turns) | Prompt-budget trimming (oldest-first) keeps requests within model context limits; UI remains scroll-performant. |
| 4.14 | User asks the bot to compare it against a competitor developer not in the corpus (e.g. "is DarGlobal better than Emaar?") | Honestly state the corpus doesn't include Emaar data, so a fair comparison isn't possible from available data — don't fabricate Emaar facts from general model knowledge. |

## 5. Infrastructure & deployment edge cases

| # | Case | Required behaviour |
|---|---|---|
| 5.1 | Host free tier sleeps after inactivity | UI cold-start state (§3 in `docs/07-FRONTEND-SPEC.md`); health check timeout tuned accordingly. |
| 5.2 | Redeploy wipes ephemeral disk (no persistent volume on the free tier) | Documented `predeploy`/release-phase re-ingestion step, or accept and document that data is rebuilt fresh per deploy (§5 in `docs/08-DEPLOYMENT.md`). |
| 5.3 | `OPENROUTER_API_KEY` missing/invalid at runtime | App still boots and serves the frontend + health/stats endpoints; `/api/chat` returns a clear, structured error (not a crash) explaining the model provider isn't configured — fail loud in logs, fail soft to the user with the deterministic-fact-based degraded response where possible. |
| 5.4 | Embedding model too large for the host's memory | Automatic/documented fallback to BM25 retrieval (§9 in `docs/05-CHATBOT-RAG-SPEC.md`) rather than an OOM crash. |
| 5.5 | Concurrent requests from multiple reviewers/testers at once | SQLite's single-writer characteristic must not deadlock reads; use WAL mode or equivalent, and keep write transactions short (chat message logging, not long-held locks during generation). |
| 5.6 | Corpus is empty (scrape/ingestion never run, or failed entirely) before first deploy | `/api/health` reports `503`/degraded rather than a false `200`; `/api/chat` explains data isn't loaded yet rather than silently answering nothing-grounded as if it were normal "not found" behaviour (these are different failure classes and should be distinguishable in logs even if the user-facing message is similarly graceful). |
| 5.7 | Clock skew / timezone confusion in `last_scraped_at` display | Store and transmit in UTC ISO-8601; format for display client-side in the user's local time or clearly-labeled UTC — never an ambiguous unlabeled timestamp. |
| 5.8 | Secrets accidentally committed to the repo | `.gitignore` covers `.env`; `.env.example` contains only placeholder values; a pre-submission grep for the literal API key value is a sane final sanity check. |

## 6. Language & internationalization edge cases

| # | Case | Required behaviour |
|---|---|---|
| 6.1 | Source content is Arabic-only for a given field | Stored verbatim with `description_lang: "ar"`; not dropped. |
| 6.2 | User writes in Arabic | Model attempts a reasonable response (many free OpenRouter models handle Arabic); if quality is clearly inadequate, respond in English with a note rather than producing broken/garbled Arabic. |
| 6.3 | Mixed-language single message (code-switching) | No special handling required beyond normal LLM behaviour — not a system-breaking case, just worth being aware isn't explicitly optimized for in v1 (`docs/01-SPEC.md` §3 non-goals). |

Every row above should be traceable to either an automated test or a manual QA step in `docs/09-TESTING-QA.md`; if a new edge case is discovered during implementation that isn't listed here, add it to this file rather than fixing it silently and leaving no record.
