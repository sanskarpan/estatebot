# 06 — Backend API Specification

Local base URL: `http://localhost:8000`. The interactive OpenAPI description is available at `/docs`. All application endpoints are under `/api` and use JSON except the optional SSE chat response.

## 1. `POST /api/chat`

Send a message and receive a completed, citation-verified answer.

### Request

```json
{
  "message": "What villas does DarGlobal have in Oman?",
  "conversation_id": "optional conversation identifier",
  "model": "optional ID returned by GET /api/models"
}
```

| Field | Rules |
|---|---|
| `message` | Required; trimmed; 1–2,000 characters |
| `conversation_id` | Optional; a new conversation is created when omitted |
| `model` | Optional; must be in the server’s curated allow-list |

### JSON response

```json
{
  "conversation_id": "...",
  "message_id": "...",
  "answer": "DarGlobal has several villa projects within AIDA...",
  "citations": [
    {
      "source_id": "aida-trump-cliff-villas",
      "source_site": "darglobal",
      "source_url": "https://darglobal.co.uk/...",
      "name": "Trump Cliff Villas",
      "record_type": "project",
      "location": "AIDA, Muscat, Oman",
      "property_category": "villa",
      "price": null,
      "bedrooms": "5 bedrooms",
      "image_url": "https://cdn.darglobal.co.uk/...jpg"
    }
  ],
  "model_used": "z-ai/glm-5.2:free",
  "retrieval_mode": "bm25_only",
  "grounded": true,
  "response_time_ms": 4210,
  "degraded": false
}
```

`model_used` is `null` for deterministic conversational, structured, no-match, and data-only responses. `retrieval_mode` may be `conversation`, `structured`, `none`, or the configured retrieval mode. `grounded=false` identifies a no-match result, not a provider failure; a deterministic answer built from retrieved records remains grounded and includes citations. Property citations include optional presentation fields sourced from the canonical database; supporting-document citations leave those fields null.

### SSE response

Send `Accept: text/event-stream` to receive buffered SSE:

```text
event: token
data: {"text":"DarGlobal "}

event: done
data: {"conversation_id":"...","answer":"...","citations":[...],"grounded":true,...}
```

The server finishes generation and verification before sending token events. `done` is the authoritative completion signal; an interrupted stream without it must not be presented as a verified answer.

### Errors

| Status | Shape / meaning |
|---:|---|
| 400 | `invalid_request` for blank or over-limit input |
| 400 | `invalid_model` when the requested ID is not allowed |
| 429 | `rate_limited` with `retry_after_seconds` and `Retry-After` |
| 503 | `service_unavailable` when the turn cannot complete safely |

Unexpected exceptions are logged server-side and returned as generic structured errors without stack traces or secrets.

## 2. `GET /api/models`

Returns the curated zero-cost model menu and automatic default.

```json
{
  "default": "google/gemma-4-31b-it:free",
  "models": [
    {
      "id": "google/gemma-4-31b-it:free",
      "label": "Gemma 4 31B",
      "provider": "Google",
      "description": "Reliable instruction following and concise summaries.",
      "free": true
    }
  ],
  "fallback_enabled": true,
  "catalog_checked_at": "2026-09-03"
}
```

Only reviewed text-answering models are exposed. See [`OPENROUTER-MODELS.md`](OPENROUTER-MODELS.md) for the current six-model list and selection rationale.

## 3. `GET /api/health`

Readiness and operational transparency endpoint.

```json
{
  "status": "ok",
  "corpus": {
    "listings_total": 248,
    "listings_darglobal": 36,
    "listings_wasalt": 212,
    "content_documents_total": 20,
    "cities_covered": ["Dubai", "Jeddah", "London", "Muscat", "Riyadh"],
    "countries_covered": ["Oman", "Saudi Arabia", "United Arab Emirates"],
    "last_scrape_completed_at": "2026-09-02T14:00:00Z"
  },
  "model": {
    "primary": "google/gemma-4-31b-it:free",
    "fallbacks": ["z-ai/glm-5.2:free", "minimax/minimax-m3:free"]
  },
  "retrieval_mode": "bm25_only",
  "version": "estatebot@local",
  "uptime_seconds": 120
}
```

An empty corpus or unreachable database returns HTTP 503 with degraded status.

## 4. `GET /api/stats`

Returns the public corpus summary used by the About dialog: active source counts, supporting-document count, covered cities/countries, and last successful scrape timestamp.

## 5. `GET /api/listings/{source_site}/{source_id}`

Returns one canonical active record.

- `200`: active record.
- `404`: identity has never been recorded.
- `410`: record is known but inactive; response explains that it was previously collected.

Identity is composite: both `source_site` and `source_id` are required.

## 6. `GET /api/listings/search`

| Parameter | Meaning |
|---|---|
| `city`, `country`, `source_site` | Exact canonical scope |
| `listing_type` | `sale` or `rent` |
| `record_type` | Listing/project type |
| `min_price`, `max_price` | Numeric bounds in the record’s published currency |
| `bedrooms_min` | Minimum compatible bedroom count |
| `q` | Name/description substring |
| `limit`, `offset` | Pagination; limit is clamped to 1–100 |

Response:

```json
{"results": [], "total": 0}
```

## 7. Cross-cutting behavior

- Chat rate limiting defaults to 20 requests per 300 seconds and uses proxy-aware client identity.
- CORS origins are configured through `CORS_ALLOWED_ORIGINS`.
- Responses include CSP, `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` headers.
- API keys remain in server-side environment configuration and are never serialized.
- Source URLs in citations come from stored canonical records, never model output.
- `/docs` and `/openapi.json` remain enabled so reviewers can inspect the living schema.
