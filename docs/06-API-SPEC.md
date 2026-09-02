# 06 — Backend API Specification

Base URL (local): `http://localhost:8000`. Base URL (deployed): the public URL recorded in `SUBMISSION.md`. All endpoints under `/api`. Content type `application/json` unless noted (chat streaming uses `text/event-stream`).

## 1. `POST /api/chat`

Send a message, get a grounded answer.

**Request body**
```json
{
  "message": "What villas does DarGlobal have in Oman?",
  "conversation_id": "optional-uuid, omit to start a new conversation",
  "model": "optional ID from GET /api/models; omit for automatic selection"
}
```

**Validation rules**
- `message`: required, non-empty after trim, max 2000 characters (return `400` with a clear error otherwise — do not silently truncate).
- `conversation_id`: optional; if provided but unknown, treat as inputting a fresh conversation with that ID (do not 404 — be forgiving of client-side state loss) rather than erroring.
- `model`: optional; must be one of the server's curated zero-cost models returned by `GET /api/models`. The selected model is attempted first, then the configured fallback chain. Unknown IDs return `400` and are never forwarded to the provider.

**Response (non-streaming mode, `Accept: application/json`)**
```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "answer": "DarGlobal has several villa projects within its AIDA masterplan...",
  "citations": [
    { "source_id": "aida-trump-cliff-villas", "name": "Trump Cliff Villas", "source_site": "darglobal", "source_url": "https://darglobal.co.uk/aida-trump-international-cliff-villas" }
  ],
  "model_used": "meta-llama/llama-3.3-70b-instruct:free",
  "retrieval_mode": "hybrid",
  "grounded": true,
  "response_time_ms": 4210
}
```

**Response (streaming mode, `Accept: text/event-stream`)** — SSE events:
```
event: token
data: {"text": "DarGlobal"}

event: token
data: {"text": " has"}

...

event: done
data: {"conversation_id": "uuid", "message_id": "uuid", "citations": [...], "model_used": "...", "grounded": true, "response_time_ms": 4210}
```
On mid-stream failure, emit `event: error` with a JSON payload `{"message": "..."}` before closing the connection — the frontend must handle this as a distinct, user-visible error state (see `docs/07-FRONTEND-SPEC.md`).

**Deterministic "not found" response shape** (FR-12) — still `200`, `grounded: false`:
```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "answer": "I couldn't find anything about that in DarGlobal's or Wasalt's data. I can help with properties/projects from those two sources — try asking about a city, project name, or property type.",
  "citations": [],
  "model_used": null,
  "retrieval_mode": "none",
  "grounded": false,
  "response_time_ms": 180
}
```

**Error responses**
- `400` — invalid input (empty/too-long message).
- `400` — requested model is not in the curated free-model allow-list.
- `429` — rate limit exceeded (see §5).
- `503` — all model providers in the fallback chain failed AND the deterministic degraded response itself could not be constructed (should be extremely rare — near-impossible unless the DB itself is unreachable); body: `{"error": "service_unavailable", "message": "..."}`.
- Never a raw unhandled `500` with a stack trace — all exceptions caught at the route boundary and converted to a structured error payload.

## 1.1 `GET /api/models`

Returns the curated free chat models offered by the UI, the automatic-mode primary, whether fallback is enabled, and the catalogue review date. This endpoint intentionally does not expose the full upstream catalogue: music-generation, moderation-only, coding-only, harness-restricted, and models that produced empty answer content in live checks are excluded.

```json
{
  "default": "google/gemma-4-31b-it:free",
  "models": [
    {"id": "google/gemma-4-31b-it:free", "label": "Gemma 4 31B", "free": true}
  ],
  "fallback_enabled": true,
  "catalog_checked_at": "2026-09-02"
}
```

## 2. `GET /api/health`

Liveness/readiness + transparency endpoint (also usable by the hosting platform's health check).

**Response `200`**
```json
{
  "status": "ok",
  "corpus": {
    "listings_total": 412,
    "listings_darglobal": 47,
    "listings_wasalt": 365,
    "content_documents_total": 38,
    "last_scrape_completed_at": "2026-08-30T10:15:00Z"
  },
  "model": {
    "primary": "meta-llama/llama-3.3-70b-instruct:free",
    "fallbacks": ["google/gemma-3-27b-it:free", "openrouter/free"]
  },
  "version": "estatebot@<git-sha-or-semver>",
  "uptime_seconds": 86412
}
```
Returns `503` with `{"status": "degraded", "reason": "..."}` if the DB is unreachable or the corpus is empty (a genuinely broken deploy should fail its health check, not report fake success).

## 3. `GET /api/stats`

Public-facing, lighter version of `/api/health`'s corpus block, intended for the frontend's "About this data" panel (kept separate from `/api/health` so the health check endpoint can be locked down/rate-limited differently from a page that loads on every visitor's first paint, if desired).
```json
{
  "listings_total": 412,
  "sources": ["darglobal", "wasalt"],
  "cities_covered": ["Dubai", "Riyadh", "Jeddah", "Dammam", "Muscat", "..."],
  "last_scrape_completed_at": "2026-08-30T10:15:00Z"
}
```

## 4. `GET /api/listings/{source_site}/{source_id}`

Debug/citation-resolution endpoint — lets the frontend (or a curious reviewer) fetch the full structured record behind a citation chip without leaving the chat.
- `200` with the full `Listing` object (per `docs/04-DATA-SCHEMA.md`) if found and `is_active: true`.
- `404` with `{"error": "not_found"}` if unknown or soft-deleted (soft-deleted returns `410 Gone` instead, with a note that it was previously scraped but no longer active on the source, to keep old citations explainable rather than mysteriously vanished).

## 5. `GET /api/listings/search` (optional, supports UI-side "browse the data" affordance if built)

Query params: `city`, `country`, `source_site`, `listing_type` (`sale`/`rent`), `min_price`, `max_price`, `bedrooms_min`, `record_type`, `q` (free-text), `limit` (default 20, max 100), `offset`.
Returns `{"results": [Listing, ...], "total": N}`. This is a thin wrapper over the same structured-filter logic used internally by the retrieval layer (§3.2 in `docs/05-CHATBOT-RAG-SPEC.md`) — reusing that logic, not duplicating it, is a design requirement (single source of truth for filter semantics).

## 6. Rate limiting

- Per-IP (or per-`conversation_id` if behind a shared proxy where IP isn't reliable) token-bucket limit on `POST /api/chat`: default **20 requests / 5 minutes**, configurable via `CHAT_RATE_LIMIT_REQUESTS` / `CHAT_RATE_LIMIT_WINDOW_SECONDS`.
- On limit exceeded: `429` with `Retry-After` header and a body `{"error": "rate_limited", "retry_after_seconds": N}` — frontend must show a friendly countdown, not a raw error.
- Rate limiting exists primarily to protect the shared free OpenRouter quota from being exhausted by a single abusive session before the reviewer gets to test it, secondarily as basic abuse protection.

## 7. CORS & security headers

- CORS: allow the deployed frontend origin explicitly (not `*`) if frontend and backend are served from different origins/containers; if the frontend is served as static files from the same FastAPI process, CORS is largely moot but should still be configured correctly for local dev (`http://localhost:5173` or whichever dev server port) to avoid this becoming a last-minute deployment surprise.
- Standard security headers on all responses: `X-Content-Type-Options: nosniff`, `Content-Security-Policy` appropriate to the frontend's actual asset origins, `Referrer-Policy: strict-origin-when-cross-origin`.
- No API keys or secrets ever appear in any response body or client-visible config — `OPENROUTER_API_KEY` lives only server-side.

## 8. OpenAPI

FastAPI auto-generates `/docs` (Swagger UI) and `/openapi.json` from the route definitions and Pydantic models — this doubles as the living, always-accurate version of this spec once implemented, and should be left enabled (not disabled in production) so the reviewer can inspect it directly as evidence of a well-typed API.
