# 04 — Canonical Data Schema

All scraper output MUST conform to this schema before being persisted. This is the contract between the ingestion pipeline and everything downstream (retrieval, generation, API, frontend).

## 1. Entity overview

- **`Listing`** — the atomic unit: an individual property, project, or plan record from either source (DarGlobal "project" pages and Wasalt "sale"/"rent"/"project"/"plan" pages are all modeled as `Listing` rows with a `record_type` discriminator — this keeps retrieval and the API uniform across sources instead of maintaining two parallel tables).
- **`ContentDocument`** — non-listing corpus content: press articles, city guides, brand-partner pages, about/company info. Also retrievable, but not filterable via property-specific fields (price/bedrooms/etc).
- **`Chunk`** — a piece of text derived from a `Listing` or `ContentDocument`, embedded and stored in the vector index; many `Chunk`s reference one parent record.
- **`ScrapeRun`** — metadata about each scrape execution (for the `last_scraped_at` / stats surface).

## 2. `Listing` — JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Listing",
  "type": "object",
  "required": ["source_site", "source_id", "source_url", "record_type", "name", "scraped_at", "is_active"],
  "properties": {
    "id": { "type": "string", "description": "Internal UUID, generated on first insert." },
    "source_site": { "type": "string", "enum": ["darglobal", "wasalt"] },
    "source_id": { "type": "string", "description": "Stable identifier from the source (slug or listing reference). Unique per source_site." },
    "source_url": { "type": "string", "format": "uri" },
    "record_type": {
      "type": "string",
      "enum": ["project", "sale_listing", "rent_listing", "plan", "auction"],
      "description": "'project' = DarGlobal developer project OR Wasalt developer project; 'sale_listing'/'rent_listing' = individual Wasalt marketplace listings; 'plan' = Wasalt land plot; 'auction' = out of scope for v1 but reserved."
    },
    "name": { "type": "string", "description": "Project/listing title." },
    "description": { "type": ["string", "null"], "description": "Primary marketing/body text, verbatim (not summarized) as scraped." },
    "description_lang": { "type": "string", "enum": ["en", "ar", "mixed", "unknown"], "default": "en" },

    "developer_name": { "type": ["string", "null"], "description": "e.g. 'DarGlobal'; for Wasalt listings, the listed developer/agent/brokerage if shown." },
    "brand_partner": { "type": ["string", "null"], "description": "Co-branding partner if any, e.g. 'Trump Organization', 'Pagani', 'FENDI Casa'." },

    "property_category": {
      "type": ["string", "null"],
      "enum": ["apartment", "villa", "hotel_room", "land", "commercial", "other", null]
    },
    "status": { "type": ["string", "null"], "description": "e.g. 'Under Development', 'Ready', 'Off-plan', 'For Sale', 'For Rent'." },

    "location_country": { "type": ["string", "null"] },
    "location_city": { "type": ["string", "null"], "description": "Normalized city (e.g. 'Riyadh', 'Dubai'); see docs/03-DATA-SCRAPING-SPEC.md for normalization rules." },
    "location_city_raw": { "type": ["string", "null"], "description": "As-scraped, unnormalized city/area text." },
    "location_area": { "type": ["string", "null"], "description": "Neighbourhood/community, e.g. 'Business Bay', 'Al Marjan Island'." },
    "masterplan_name": { "type": ["string", "null"], "description": "e.g. 'AIDA', 'Amaya', 'Rayana', 'Wadi Safar' — larger masterplan a project sits within, when detectable." },
    "latitude": { "type": ["number", "null"] },
    "longitude": { "type": ["number", "null"] },

    "price_amount": { "type": ["number", "null"], "description": "Never fabricated — null if not published on source." },
    "price_currency": { "type": ["string", "null"], "enum": ["AED", "SAR", "USD", "GBP", "EUR", "QAR", "OMR", null] },
    "price_display_text": { "type": ["string", "null"], "description": "Raw price text as shown on page, if structured amount could not be confidently parsed." },
    "listing_type": { "type": ["string", "null"], "enum": ["sale", "rent", null] },
    "rent_period": { "type": ["string", "null"], "enum": ["monthly", "yearly", null] },

    "area_sqm_min": { "type": ["number", "null"] },
    "area_sqm_max": { "type": ["number", "null"] },
    "bedrooms": { "type": ["string", "null"], "description": "Raw text, e.g. '2' or 'Studio' or '1-3'." },
    "bedrooms_min": { "type": ["integer", "null"], "description": "0 = studio. Parsed for structured filtering." },
    "bedrooms_max": { "type": ["integer", "null"] },
    "bathrooms": { "type": ["integer", "null"] },
    "unit_types_raw": { "type": ["string", "null"] },
    "unit_types_normalized": {
      "type": "array",
      "items": { "type": "string", "enum": ["studio", "1br", "2br", "3br", "4br", "5br_plus", "penthouse", "villa", "plot", "other"] },
      "default": []
    },

    "amenities": { "type": "array", "items": { "type": "string" }, "default": [] },
    "expected_completion_date": { "type": ["string", "null"], "format": "date", "description": "Best-effort parsed; keep raw text in expected_completion_raw if not cleanly parseable." },
    "expected_completion_raw": { "type": ["string", "null"] },

    "image_urls": { "type": "array", "items": { "type": "string", "format": "uri" }, "default": [] },
    "brochure_url": { "type": ["string", "null"], "format": "uri" },
    "related_source_ids": { "type": "array", "items": { "type": "string" }, "default": [], "description": "Other Listing.source_id values referenced (e.g. 'Other projects' section)." },

    "posted_or_updated_date": { "type": ["string", "null"], "format": "date" },
    "scraped_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" },
    "is_active": { "type": "boolean", "default": true, "description": "False = soft-deleted (no longer found on re-scrape)." },
    "raw_snapshot_path": { "type": ["string", "null"], "description": "Path to cached raw HTML, dev-only, may be absent in production image." }
  }
}
```

## 3. `ContentDocument` — JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ContentDocument",
  "type": "object",
  "required": ["source_site", "source_id", "source_url", "content_type", "title", "body_text", "scraped_at"],
  "properties": {
    "id": { "type": "string" },
    "source_site": { "type": "string", "enum": ["darglobal", "wasalt"] },
    "source_id": { "type": "string" },
    "source_url": { "type": "string", "format": "uri" },
    "content_type": { "type": "string", "enum": ["press_release", "city_guide", "brand_partner", "company_info"] },
    "title": { "type": "string" },
    "publish_date": { "type": ["string", "null"], "format": "date" },
    "body_text": { "type": "string" },
    "related_source_ids": { "type": "array", "items": { "type": "string" }, "default": [] },
    "scraped_at": { "type": "string", "format": "date-time" },
    "is_active": { "type": "boolean", "default": true }
  }
}
```

## 4. `Chunk` (implemented SQLite FTS5 search record)

| Field | Type | Notes |
|---|---|---|
| `chunk_id` | string (stable hash) | primary key in `chunks` and `chunks_fts` |
| `parent_type` | enum `listing` \| `content_document` | |
| `parent_id` | string | FK to `Listing.id` or `ContentDocument.id` |
| `parent_source_id` | string | denormalized for fast citation display without a join |
| `parent_source_url` | string | denormalized, used directly for citation links |
| `chunk_type` | enum `overview` \| `amenities` \| `location` \| `pricing` \| `body` | lets retrieval favor certain chunk types for certain intents |
| `text` | string | normalized searchable text indexed by FTS5 |
| `is_active` | boolean | inactive chunks are excluded from retrieval |

**Chunking rule:** for a `Listing`, generate: (1) an `overview` chunk containing identity, type, location, status, price, bedrooms, area, and other structured facts; (2) an `amenities` chunk when amenities exist; and (3) bounded `body` chunks when the description exceeds 40 words. Short descriptions are folded into the overview. `ContentDocument.body_text` is split into overlapping chunks of roughly 420 whitespace-delimited words with a 60-word overlap. `ingestion/build_index.py` rebuilds both the canonical chunk table and its FTS5 index.

## 5. SQL DDL (SQLite-compatible; Postgres-compatible with trivial type substitutions noted)

```sql
CREATE TABLE listings (
    id                      TEXT PRIMARY KEY,                 -- UUID
    source_site             TEXT NOT NULL CHECK (source_site IN ('darglobal','wasalt')),
    source_id               TEXT NOT NULL,
    source_url              TEXT NOT NULL,
    record_type             TEXT NOT NULL CHECK (record_type IN ('project','sale_listing','rent_listing','plan','auction')),
    name                    TEXT NOT NULL,
    description             TEXT,
    description_lang        TEXT DEFAULT 'en',
    developer_name          TEXT,
    brand_partner           TEXT,
    property_category       TEXT,
    status                  TEXT,
    location_country        TEXT,
    location_city           TEXT,
    location_city_raw       TEXT,
    location_area           TEXT,
    masterplan_name         TEXT,
    latitude                REAL,
    longitude               REAL,
    price_amount             REAL,
    price_currency           TEXT,
    price_display_text       TEXT,
    listing_type             TEXT CHECK (listing_type IN ('sale','rent') OR listing_type IS NULL),
    rent_period               TEXT CHECK (rent_period IN ('monthly','yearly') OR rent_period IS NULL),
    area_sqm_min             REAL,
    area_sqm_max             REAL,
    bedrooms                 TEXT,
    bedrooms_min              INTEGER,
    bedrooms_max              INTEGER,
    bathrooms                 INTEGER,
    unit_types_raw            TEXT,
    unit_types_normalized     TEXT,     -- JSON array stored as TEXT in SQLite; native TEXT[] in Postgres
    amenities                 TEXT,     -- JSON array as TEXT
    expected_completion_date  TEXT,
    expected_completion_raw   TEXT,
    image_urls                TEXT,     -- JSON array as TEXT
    brochure_url               TEXT,
    related_source_ids         TEXT,     -- JSON array as TEXT
    posted_or_updated_date     TEXT,
    scraped_at                  TEXT NOT NULL,
    updated_at                   TEXT NOT NULL,
    is_active                     INTEGER NOT NULL DEFAULT 1,   -- BOOLEAN in Postgres
    raw_snapshot_path             TEXT,
    UNIQUE (source_site, source_id)
);

CREATE INDEX idx_listings_city ON listings (location_city);
CREATE INDEX idx_listings_type ON listings (record_type, listing_type);
CREATE INDEX idx_listings_price ON listings (price_amount);
CREATE INDEX idx_listings_active ON listings (is_active);

CREATE TABLE content_documents (
    id              TEXT PRIMARY KEY,
    source_site     TEXT NOT NULL CHECK (source_site IN ('darglobal','wasalt')),
    source_id       TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    content_type    TEXT NOT NULL CHECK (content_type IN ('press_release','city_guide','brand_partner','company_info')),
    title           TEXT NOT NULL,
    publish_date    TEXT,
    body_text       TEXT NOT NULL,
    related_source_ids TEXT,
    scraped_at      TEXT NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE (source_site, source_id)
);

CREATE TABLE scrape_runs (
    id                TEXT PRIMARY KEY,
    source_site       TEXT NOT NULL,
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    pages_attempted   INTEGER DEFAULT 0,
    pages_succeeded   INTEGER DEFAULT 0,
    pages_failed      INTEGER DEFAULT 0,
    pages_skipped     INTEGER DEFAULT 0,
    records_upserted  INTEGER DEFAULT 0,
    records_deactivated INTEGER DEFAULT 0,
    status            TEXT CHECK (status IN ('running','success','partial_failure','failed')),
    notes             TEXT
);

CREATE TABLE conversations (
    id           TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,
    last_active_at TEXT NOT NULL
);

CREATE TABLE messages (
    id               TEXT PRIMARY KEY,
    conversation_id  TEXT NOT NULL REFERENCES conversations(id),
    role             TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content          TEXT NOT NULL,
    citations        TEXT,          -- JSON array of {source_id, source_url, name}
    model_used        TEXT,
    created_at        TEXT NOT NULL
);
```

## 6. Field-level validation rules (enforced by the Validator step, §4.4 in `03-DATA-SCRAPING-SPEC.md`)

- `price_amount`, if present, must be `> 0`.
- `area_sqm_min` ≤ `area_sqm_max` when both present.
- `bedrooms_min` ≤ `bedrooms_max` when both present; `0` is a valid value (studio).
- `source_url` must be a well-formed absolute URL on the expected domain for its `source_site`.
- `(source_site, source_id)` must be unique — enforced at the DB level (`UNIQUE` constraint above), not just in application code.
- `name` must be non-empty after trimming whitespace; a record with no usable name is dropped, not stored with a placeholder.
- `unit_types_normalized` values must be drawn only from the enum in §2 — free-text unit descriptions that don't map cleanly are kept in `unit_types_raw` and simply omitted from the normalized array rather than force-mapped incorrectly.

## 7. Why structured columns AND free-text chunks (not one or the other)

Structured columns (`price_amount`, `bedrooms_min`, `location_city`, etc.) support deterministic filters such as "under 2,000,000 SAR", "3+ bedrooms", and "in Riyadh". Free-text chunks support BM25 matching for names, descriptions, amenities, and supporting documents. The planner combines them as described in `docs/05-CHATBOT-RAG-SPEC.md` §3.
