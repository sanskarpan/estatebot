# 00 — Repository Review & Build-Pass Brief

> **Post-build addendum (2026-09-02):** The implementation pass has created and verified the runnable local system, fixtures, Docker/CI/deployment configuration, and a two-source seed containing 36 DarGlobal projects, 15 DarGlobal press releases, 180 Wasalt listings, and 3 Wasalt city guides. The original review below is intentionally retained as the pre-build audit; current evidence and remaining release gates are maintained in [`IMPLEMENTATION-STATUS.md`](IMPLEMENTATION-STATUS.md).

## Post-build resolution summary

The original critical findings are resolved locally as follows: all referenced runtime files now exist (C1); unknown/inactive records use `404`/`410` (C2); listing lookup and search are implemented (C3); persistence, lookup, deactivation, retrieval, and citations use composite source identity (C4); incomplete/blocked runs cannot mass-deactivate a source (C5); deterministic structured, lexical, named-entity, cross-source, no-match, and press-routing paths are implemented and tested (C6); model fallback timeouts and bounded context assembly are implemented, although live provider metadata remains an external-key QA gate (C7); SSE buffers and verifies before final delivery (C8); and clean Docker startup bootstraps SQLite/FTS5 from the checked-in seed (C9).

The lifecycle findings are likewise represented in code: Pydantic is the authoritative validation boundary over pragmatic SQLite constraints (I1); IDs and timestamps are generated consistently (I2); refresh metadata is persisted separately and exposed by health/stats (I3); inactive records stay out of ordinary retrieval while direct lookup reports `410` (I4); and source IDs derive from canonical source references/paths inside a source namespace (I5).

The remaining work is external release proof, not an unresolved local design question: supply an OpenRouter key, push to an accessible remote, deploy the prepared Render Blueprint, and execute the documented deployed-URL QA. Those items remain unchecked in [`../SUBMISSION.md`](../SUBMISSION.md).

## Review status

**Review date:** 2026-09-02
**Repository state at review time:** documentation-only planning package
**Review scope:** every non-system file present in the folder: `README.md`, `CHECKLIST.md`, `SUBMISSION.md`, and `docs/01` through `docs/10`.

This review is intentionally separate from the original specifications. It records what the package means, what is already coherent, what is not yet executable, and what should be settled before the implementation pass. No existing specification was silently rewritten.

## 1. Executive assessment

This is a technical-assessment build package for **EstateBot**, a deployed web chatbot that answers questions about publicly available DarGlobal and Wasalt property data. The intended value is not generic conversational ability; it is a demonstrably grounded, auditable workflow:

```text
public source pages
  → polite, bounded, resumable scraping
  → normalized and validated records
  → SQLite structured data + searchable chunks
  → deterministic filters plus retrieval
  → free OpenRouter model with fallbacks
  → citation verification
  → responsive public chat UI
  → Dockerized deployment and recorded QA
```

The product intent is clear and appropriately ambitious for an FDE assessment. The documents show strong awareness of numeric-filter correctness, data freshness, source attribution, prompt injection, provider failure, free-tier constraints, and reviewer experience.

The folder is **not yet a runnable project**. There is no application code, scraper, test suite, fixture corpus, frontend, Docker configuration, `.env.example`, `.gitignore`, deployment manifest, or live submission data. That is consistent with the folder being a build specification, but it means none of the runtime acceptance criteria can be considered satisfied yet.

## 2. What each document contributes

| File | Role | Review finding |
|---|---|---|
| `README.md` | Orientation, scope, glossary, assignment traceability | Clearly frames this as a build package and establishes the intended reading order. It references `.env.example`, which is not present yet. |
| `docs/01-SPEC.md` | Product requirements and definition of done | Strong acceptance criteria and representative reviewer prompts. It makes deployment, grounding, citations, and freshness first-class requirements. |
| `docs/02-ARCHITECTURE.md` | Components, data flow, stack, repository layout | Coherent architecture. It leaves a few implementation choices open and contains one key upsert-key ambiguity. |
| `docs/03-DATA-SCRAPING-SPEC.md` | Source scope, legal/ethical boundary, extraction and resilience | Careful and responsible. Site structure, robots rules, selectors, and availability remain live-build questions by design. |
| `docs/04-DATA-SCHEMA.md` | JSON models, chunk model, SQL DDL, validation | Good canonical contract, but the JSON Schema and SQL constraints are not fully aligned and lifecycle fields need clarification. |
| `docs/05-CHATBOT-RAG-SPEC.md` | Models, prompts, retrieval, citations, fallback behavior | The most important grounding design is present. Streaming, fallback context budgets, and structured intent semantics need a concrete implementation contract. |
| `docs/06-API-SPEC.md` | REST/SSE contract and operational headers | Mostly implementable, but contains the explicit `404`/`410` contradiction and an optional/required mismatch. |
| `docs/07-FRONTEND-SPEC.md` | UI, states, accessibility, security | Complete enough to build a strong reviewer-facing UI. The streaming/citation timing contract should be made explicit. |
| `docs/08-DEPLOYMENT.md` | Docker, hosting options, environment variables, operations | Good options analysis and resource awareness. Actual platform, persistence, refresh, and model choices are intentionally not selected yet. |
| `docs/09-TESTING-QA.md` | Unit/integration/manual QA plan | Strong test pyramid and 17-step manual script. The edge-case catalog needs a formal traceability matrix during implementation. |
| `docs/10-EDGE-CASES.md` | Cross-system failure and abuse catalog | Thorough and useful. Several behaviors need to become explicit automated tests rather than remaining prose assertions. |
| `CHECKLIST.md` | Sequential execution plan | Correct overall order and good gating. A few steps conflict with “optional” wording elsewhere and should be normalized before execution. |
| `SUBMISSION.md` | Final reviewer handoff template | Appropriate final gate, but correctly remains blank until the build and deployment exist. |

## 3. Reconstructed product behavior

### Data sources and corpus

The corpus has two logical source namespaces:

- **DarGlobal**: primarily project pages, with press, company, and partner content as supporting documents. DarGlobal records are generally project-level, often with no published price.
- **Wasalt**: capped sale and rent marketplace listings across at least Riyadh, Jeddah, and Dammam/Khobar, with best-effort projects/plans and city-guide documents.

All records carry source identity, stable source identity within that source, canonical URL, scrape timestamp, normalized location and property fields, active/soft-deleted state, and enough raw text for retrieval and citation.

### Retrieval and answer behavior

The intended query planner is hybrid:

1. Detect explicit source, city, category, price, bedroom, rent/sale, and comparative intent.
2. Apply safe structured filters for numeric and categorical facts.
3. Run semantic or keyword retrieval, optionally constrained by the structured candidate set.
4. Pin deterministic results and fill the remaining context budget with relevant chunks.
5. Refuse to generate when there is no trustworthy context, or return a structured “no match” response when a valid filter matches zero records.
6. Generate only from delimited context, using machine-readable citation markers.
7. Verify that every citation belongs to the context shown for this turn, then return clickable source metadata.

The assistant is intentionally narrow: it is not a general knowledge bot, a live property availability service, a transaction system, a financial/legal advisor, or a source of opinions about named people.

### Runtime and delivery

The recommended deployment shape is one long-running FastAPI container serving the static frontend, with scraper and ingestion jobs as one-off Docker Compose tools. SQLite and a local index are persisted under `/app/data` when the host supports it. The public UI exposes corpus counts, source attribution, last scrape time, model transparency, grounded/not-found states, and failure recovery.

## 4. Current implementation readiness

| Area | State now | What is still required |
|---|---|---|
| Product definition | Defined | Preserve the narrow grounded scope during implementation. |
| Architecture | Defined with alternatives | Select concrete frontend, retrieval/index, hosting, and persistence choices. |
| Data contract | Mostly defined | Align schema/DDL, define key/lifecycle semantics, add fixtures. |
| Scraping | Specified but unverified | Inspect live robots rules and page/API behavior, then implement and record actual findings. |
| Retrieval | Designed | Choose BM25/FTS5 versus embeddings after an actual memory/latency measurement. |
| Generation | Designed | Query live free-model metadata, configure models, implement fallback and prompt contracts. |
| API | Nearly defined | Resolve response semantics and implement OpenAPI-backed routes. |
| Frontend | Specified | Choose React/Vite or server-rendered UI and implement all required states. |
| Docker/deployment | Planned | Add files, build locally, choose a platform, provision persistence/secrets, deploy. |
| Testing | Planned | Add fixtures, automated tests, QA results, and evidence. |
| Submission | Template only | Fill with actual URL, counts, model, platform, costs, limitations, and QA outcomes. |

## 5. Findings that should be resolved before coding

### Critical contract findings

#### C1 — The folder references required runtime files that do not exist

`README.md`, `CHECKLIST.md`, and `docs/08-DEPLOYMENT.md` all refer to `.env.example`, Docker files, Compose services, and a repository layout that has not been created. This is expected for a planning package, but the first build phase must create the missing scaffolding before any checklist item can be treated as complete.

The directory also contains a `.DS_Store` and is not currently a Git repository (`git status` reports “not a git repository”). The implementation pass should create a clean Git-backed project while preserving this documentation.

#### C2 — Citation-resolution status codes conflict

`docs/06-API-SPEC.md` §1 describes unknown and soft-deleted listing lookups as `404`, while §4 says soft-deleted records return `410 Gone`. `docs/09-TESTING-QA.md` explicitly expects `410` for soft-deleted and `404` for unknown.

Recommended resolution: **unknown = `404`; known but soft-deleted = `410`**, with a small explanatory body. This matches the more specific endpoint rule and the test plan.

#### C3 — “Optional” API features are treated as required elsewhere

`docs/01-SPEC.md` calls listing lookup and listing search optional, but `CHECKLIST.md` requires both and the frontend/citation workflow benefits from listing lookup. The build should choose one position. Recommended: make both required in v1 because they are small, useful reviewer-facing evidence and already have contracts.

#### C4 — Composite source keys must be used consistently

The canonical uniqueness rule is `(source_site, source_id)`, but `docs/02-ARCHITECTURE.md` §4.2 says to upsert “by `source_id`.” That could merge a DarGlobal record and a Wasalt record with the same slug/reference.

Recommended resolution: use `(source_site, source_id)` for every upsert, lookup, citation identity, soft-delete operation, and vector metadata reference. `source_id` alone is not globally unique.

#### C5 — Partial or blocked crawls must not deactivate a whole source

The specs correctly require soft-deletion, but a naïve implementation could mark every previously stored record inactive when robots, WAF, DNS, or a parser break prevents a complete crawl. The “preserve the last good corpus” requirement implies a completeness gate.

Recommended rule: only deactivate previously active records after a source run proves that discovery completed for the intended scope and the record was absent. If the run is `failed`, blocked, structurally incomplete, or only sampled by a cap, preserve existing records and report the run as partial. A run should record its scope, discovery completion, and deactivation eligibility explicitly.

#### C6 — The structured-filter and vector-search interaction needs one concrete truth table

The RAG spec says to filter first, always run vector search, return a deterministic zero-match response for valid empty filters, and use a similarity threshold when no filter matches. Those rules are compatible, but the exact behavior for mixed queries, unrecognized locations, and referential follow-ups is not yet executable without a small decision table.

At minimum, define these cases in code/tests: no structured intent; valid non-empty filter; valid filter with zero rows; invalid/unrecognized filter term; filter plus semantic qualifier; follow-up that inherits the previous turn’s entity/location.

#### C7 — Model fallback metadata and context budgets are underspecified

The prompt budget is based on the selected model’s context length, but fallback models may have different context windows. The implementation must calculate a safe budget for the model actually being attempted, or use the minimum budget across configured models. If `openrouter/free` is used, the app should distinguish the configured router ID from the effective model/provider when that information is available.

The fallback chain also needs an explicit retry policy for failures after a partial streamed response, because switching providers mid-stream is not transparent to the client.

#### C8 — Streaming and citation verification have a timing dependency

The backend cannot safely expose a final answer as already-committed UI text and only later discover that its citations are invalid. The documents should choose one of these designs:

1. buffer the generated answer, verify it, then stream the verified text; or
2. stream provisional text while suppressing citation markers and treat the final `done` event as authoritative, replacing the provisional message if verification/regeneration changes it.

The first option is simpler and safest for a small assessment. In either case, assistant message persistence, client disconnect behavior, and retry semantics should be defined together.

#### C9 — Docker “single command” behavior conflicts with the profile workflow

`docs/01-SPEC.md` describes `docker compose up` as bringing up the full stack, while `docs/08-DEPLOYMENT.md`, `CHECKLIST.md`, and `SUBMISSION.md` define the scraper and ingestion services as manual one-off profile commands that must run before the API. A clean checkout with an empty volume therefore cannot have a ready corpus from `docker compose up` alone, and the example backend image copies `backend/` but not the top-level `ingestion/` package even though the `ingestion` Compose service runs it.

Recommended resolution: define two explicit supported workflows. For local development, `docker compose run --rm scraper`, `docker compose run --rm ingestion`, then `docker compose up api`; for deployment, publish a prebuilt data snapshot or run a documented release/prestart ingestion job before the API is marked ready. Ensure every image that executes `ingestion.build_index` actually contains that package and its dependencies. Change the assignment wording to require a reproducible documented pipeline, not an impossible empty-volume `up` that is simultaneously expected to have non-zero data.

### Important schema and lifecycle findings

#### I1 — JSON Schema and SQL DDL are not fully equivalent

The JSON Schema enumerates `description_lang`, `property_category`, `price_currency`, and normalized fields, while the SQLite DDL leaves several of those as unconstrained `TEXT`. The app validator can enforce them, but the statement that the DDL is the canonical persistence contract is then only partially true.

Either add matching `CHECK` constraints where practical or state explicitly that Pydantic validation is authoritative and SQL constraints only protect identity/lifecycle invariants.

#### I2 — Internal IDs and update timestamps need explicit semantics

`id` is described as an internal UUID generated on first insert, but it is not required by the JSON Schema and has no SQL default. `ContentDocument` also lacks `updated_at`, despite being soft-deletable. Define whether `id` is always generated by the persistence layer, and add/update lifecycle timestamps consistently if re-ingestion and auditability depend on them.

#### I3 — `last_scrape_completed_at` must come from run metadata

The schema uses per-record `scraped_at`, while the API exposes `last_scrape_completed_at`. The latter should be derived from the most recent successful or explicitly partial `scrape_runs.finished_at`, not from an arbitrary record timestamp. The UI should distinguish “data last refreshed” from “this record was scraped.”

#### I4 — Soft-deleted citations need an explicit answer policy

The edge-case catalog says a directly requested soft-deleted record may still be answered with a stale-data caveat, while the listing endpoint returns `410`. Retrieval must therefore include or exclude inactive records deliberately: inactive records can be searched for historical/name resolution, but should not be mixed into ordinary “currently available” result sets without a visible caveat.

#### I5 — Source identity and provenance need a stable algorithm

The docs permit slugs, listing references, or normalized hashes. These have different update and deduplication behavior. Before writing scrapers, document the precedence order, canonical URL normalization rules, hash fallback, and how a changed slug/reference is linked to an existing record.

## 6. Build-time assumptions that must be verified, not trusted

These claims are appropriately marked as things to check during implementation, but they are not evidence of current runtime behavior:

- exact DarGlobal project, press, partner, and corporate URL inventory;
- exact Wasalt listing URL patterns, SSR behavior, pagination, and any public JSON API;
- current `robots.txt` rules and crawl-delay directives for both domains;
- whether WAF responses permit the chosen plain HTTP client at the required rate;
- current OpenRouter free-model IDs, pricing, context lengths, streaming support, and quotas;
- actual free-host RAM, disk persistence, sleep, egress, and build-time limits;
- the accuracy of current marketing metrics and third-party technology-profile claims.

The implementation should record these findings in source-specific notes and the final submission rather than leaving the planning-time observations unchanged.

## 7. Recommended decisions for the implementation pass

These are recommendations, not silent changes to the original spec:

1. Keep the single-container public architecture: FastAPI serves the built static frontend; scraper and ingestion are one-off jobs.
2. Use SQLite in WAL mode with composite `(source_site, source_id)` identity.
3. Start with a deterministic, low-memory retrieval path (SQLite FTS5/BM25 plus structured filters) unless an actual embedding benchmark shows the selected local model fits the deployment budget with headroom. Preserve a pluggable retrieval interface so local embeddings can be added without changing the API.
4. Make `/api/listings/{source_site}/{source_id}` and `/api/listings/search` required v1 endpoints.
5. Use `404` for unknown records and `410` for known inactive records.
6. Buffer and verify generated answers before emitting the final SSE content, or explicitly implement a provisional-stream replacement protocol.
7. Treat a source run as eligible for deactivation only after complete discovery for its configured scope; never mass-soft-delete after an infrastructure or parser failure.
8. Build the fixture corpus and validator tests before connecting live scrapers or OpenRouter.
9. Keep a source/run provenance record for actual URLs, crawl outcomes, counts, and limitations.
10. Add a requirement-to-test traceability table covering every edge-case row before final QA.

## 8. Build-pass execution order

The existing checklist is directionally correct. The safest execution order is:

1. create the repository/runtime scaffolding and environment template;
2. implement schema, persistence, migrations, and fixtures;
3. implement and test normalizers and source-independent HTTP policy;
4. inspect live source behavior and build DarGlobal/Wasalt parsers against saved fixtures;
5. run bounded scrapes and verify corpus quality/idempotency;
6. implement chunking and the chosen retrieval index;
7. implement deterministic query planning and degraded responses;
8. implement OpenRouter fallback, prompting, citation verification, and API routes;
9. implement the frontend and all runtime states;
10. build and test Docker locally from a clean data volume;
11. deploy with secrets and persistent/rebuild strategy documented;
12. execute the full automated and 17-item manual QA suite, then fill `SUBMISSION.md`.

## 9. Inputs needed for the build/deployment pass

No clarification is required to understand the product or begin local implementation. Before public deployment, the following external inputs will be needed:

- an OpenRouter API key supplied through a local ignored `.env` file or host secret manager (never committed or pasted into a tracked document);
- a GitHub/repository destination if the project must be submitted as a hosted repository;
- permission to create/use the selected free hosting account, or a user-provided deployment target;
- the desired public project/repository name if `estatebot` is not the final name.

The implementation can proceed with safe defaults for the stack, model selection, and hosting evaluation, but deployment cannot be truthfully marked complete without those external credentials/access paths.

## 10. Final review verdict

**Understanding:** clear.
**Specification quality:** strong, with the contract issues above.
**Implementation readiness:** good after the critical findings are resolved in code/spec notes.
**Current completion:** planning/documentation phase only; no acceptance criterion is yet evidenced by a running system.

The project’s central assessment story is sound: demonstrate disciplined data acquisition, reliable structured retrieval, grounded generation, graceful failure, and a reviewer-friendly deployment. The next pass should focus on building that vertical slice and collecting evidence for each claim rather than expanding the feature surface.
