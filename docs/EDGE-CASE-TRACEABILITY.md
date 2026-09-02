# Edge-case traceability

**Audit date:** 2026-09-02

This matrix maps every requirement in [`10-EDGE-CASES.md`](10-EDGE-CASES.md) to its strongest current evidence. “Automated” means a repeatable test is part of the local/CI suite. “Inspected” means the implementation path was reviewed but still benefits from live or destructive/manual verification. “Deployed QA” is intentionally not claimed until a public authenticated deployment exists.

## Scraping and source data

| ID | Status | Evidence |
|---|---|---|
| 1.1 | Inspected | Complete-discovery gates and `mark_missing_inactive` in both source spiders; deployed refresh rehearsal remains manual. |
| 1.2 | Automated/inspected | Parser fixtures exercise missing optional values; Pydantic rejects missing required identity rather than persisting corrupt rows. |
| 1.3 | Automated + live | `test_waf_signature_detection`; live challenge observations in [`../scraper/live-findings.md`](../scraper/live-findings.md). |
| 1.4 | Automated | DarGlobal fixture and `test_deterministic_price_answer_is_explicit_when_unpublished`. |
| 1.5 | Automated/inspected | `test_price_is_conservative`; `parse_price` preserves raw display text and only stores an unambiguous first numeric bound. |
| 1.6 | Automated | `test_text_and_url_canonicalization`; composite canonical source identity. |
| 1.7 | Inspected | Same missing-record/deactivation path as 1.1; source run continues after failed fetches. |
| 1.8 | Inspected | Wasalt source IDs derive from canonical paths and URL validation accepts either official hostname without merging cross-source identities. |
| 1.9 | Automated | `test_sitemap_discovery_is_bounded_and_typed`; configured category/listing caps. |
| 1.10 | Inspected | `extract_facts` classifies English/Arabic/mixed text and stores source text verbatim. |
| 1.11 | Automated/inspected | `test_price_is_conservative`; source parser only infers a default currency where source context supplies one. |
| 1.12 | Inspected | `PoliteHTTPClient.allowed` gates every fetch through `RobotFileParser`. |
| 1.13 | Live + inspected | Conservative robots fallback observed for the Wasalt CDN during clean-clone rehearsal. |
| 1.14 | Automated | `test_long_content_is_split_into_bounded_overlapping_chunks`. |
| 1.15 | Automated | `test_text_and_url_canonicalization` covers entities, non-breaking spaces, and whitespace normalization. |
| 1.16 | Seed + smoke | Six distinct Trump-branded DarGlobal records remain separate; factual retrieval smoke tested without editorialization. |
| 1.17 | Inspected | Per-record transactional upserts and idempotent reruns preserve partial progress. |
| 1.18 | Automated | `test_composite_source_identity` and cross-source citation tests. |

## Data modeling and normalization

| ID | Status | Evidence |
|---|---|---|
| 2.1 | Automated | `test_city_alias_normalization`; raw location retained separately. |
| 2.2 | Automated | `test_bedroom_ranges_and_studio`. |
| 2.3 | Automated | `test_bedroom_ranges_and_studio` verifies studio maps to zero, not null. |
| 2.4 | Automated/inspected | Area-range conversion test plus project-level schema fields and grounded prompt wording. |
| 2.5 | Automated | Every checked-in seed record validates `image_urls` as a list, including empty lists. |
| 2.6 | Automated | Quarter parsing and DarGlobal raw-completion preservation assertions. |
| 2.7 | Inspected | Exact duplicate amenities are removed conservatively; semantic near-duplicates remain an acknowledged non-blocking limitation. |

## Retrieval and RAG

| ID | Status | Evidence |
|---|---|---|
| 3.1 | Automated | `test_unknown_city_is_not_dropped` and no-hit retrieval behavior. |
| 3.2 | Automated | Structured empty results return a criterion-specific no-match path. |
| 3.3 | Automated | Unknown geography remains explicit even when other filters are present. |
| 3.4 | Automated | `test_equal_cheapest_prices_are_both_returned`. |
| 3.5 | Automated | `test_directly_named_inactive_record_is_returned_with_stale_caveat`; direct API remains `410`. |
| 3.6 | Automated + container | `test_cross_source_comparison_keeps_both_sides` and fresh-container citation smoke. |
| 3.7 | Inspected; live-model QA pending | Structured facts always include explicit currency and the system prompt forbids implicit conversion/comparison. |
| 3.8 | Automated/by design | BM25-only mode has no vector semantic drift; no lexical hit returns deterministic no-match. |
| 3.9 | Automated | `test_extremely_broad_query_returns_bounded_corpus_overview`. |
| 3.10 | Catalog + automated bounds | Configured contexts verified at ≥256K; context/history are hard-bounded well below that floor. |

## Chat, UX, and abuse

| ID | Status | Evidence |
|---|---|---|
| 4.1 | Automated | `test_empty_chat_is_400`; required textarea and empty-submit guard. |
| 4.2 | Automated | `test_overlong_chat_is_rejected`; textarea `maxlength=2000`. |
| 4.3 | Automated; live-model quality pending | Arabic input returns a non-error response. |
| 4.4 | Automated | Emoji-only input returns a graceful non-error response. |
| 4.5 | Automated | Citation verifier and `test_prompt_extraction_probe_does_not_leak_system_prompt`; context is delimited as data. |
| 4.6 | Automated | Off-topic coding input fails softly without external-knowledge generation in deterministic mode. |
| 4.7 | Inspected; live-model QA pending | System prompt forbids opinions/defamation and permits only sourced factual statements. |
| 4.8 | Automated | Threshold+1 rate-limit test verifies `429` and `Retry-After`; UI surfaces the wait. |
| 4.9 | Automated | Missing-provider deterministic mode and mocked primary-to-fallback behavior. |
| 4.10 | Inspected; deployed QA pending | Client catches stream termination/no-final events, renders an interrupted/error state, and offers Retry. |
| 4.11 | Inspected | No mutable answer cache; structured retrieval and citations remain fact-consistent across repeats. |
| 4.12 | Automated/static | Root-serving test plus visible `<noscript>` fallback. |
| 4.13 | Inspected; deployed QA pending | Server history is bounded; client transcript is persisted, but 50-turn visual performance remains manual. |
| 4.14 | Automated by no-match policy | Unknown developer/property terms receive no corpus context and cannot trigger general-knowledge comparison in deterministic mode. |

## Infrastructure and deployment

| ID | Status | Evidence |
|---|---|---|
| 5.1 | Implemented; deployed QA pending | Client waking-up banner and bounded timeout; actual host sleep requires deployed observation. |
| 5.2 | Automated/container | Bare image and clean Compose volume reconstruct SQLite/FTS5 from the checked-in seed. |
| 5.3 | Automated + container | No-key mode boots, serves UI/health, and returns cited deterministic facts. |
| 5.4 | Measured | BM25 selected; healthy runtime measured near 52 MiB against a 512 MiB target. |
| 5.5 | Inspected | SQLite WAL, busy timeout, short write transactions, and no transaction held during provider calls. |
| 5.6 | Automated | `test_empty_corpus_is_distinctly_degraded` verifies health `503` and ungrounded chat behavior. |
| 5.7 | Inspected | UTC ISO-8601 storage/API; browser formats the timestamp using `toLocaleString`. |
| 5.8 | Automated hygiene | `.env` ignored, example contains placeholders, and secret scan is clean. |

## Language and internationalization

| ID | Status | Evidence |
|---|---|---|
| 6.1 | Inspected | Arabic-only parser classification stores `description_lang=ar` and preserves body text. |
| 6.2 | Automated; authenticated quality pending | Arabic user input returns a valid response; live multilingual model quality is a deployment check. |
| 6.3 | Inspected; authenticated quality pending | Unicode input path is schema-safe; no language-specific transformation can corrupt code-switched text. |

## Remaining manual gates

No row is silently treated as proven by a unit test when it requires a real host or model. The remaining evidence is concentrated in authenticated OpenRouter behavior, Render cold starts, mobile viewport/composer behavior, keyboard/citation operation, dropped network streams, and long-session visual performance. These map directly to the 17-step deployed script in [`09-TESTING-QA.md`](09-TESTING-QA.md).
