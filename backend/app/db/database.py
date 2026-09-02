"""Small SQLite repository with WAL mode and JSON serialization helpers."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from backend.app.models.schema import ContentDocument, Listing

logger = logging.getLogger(__name__)


DDL = """
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    source_site TEXT NOT NULL CHECK (source_site IN ('darglobal','wasalt')),
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    record_type TEXT NOT NULL CHECK (record_type IN ('project','sale_listing','rent_listing','plan','auction')),
    name TEXT NOT NULL,
    description TEXT,
    description_lang TEXT NOT NULL DEFAULT 'en' CHECK (description_lang IN ('en','ar','mixed','unknown')),
    developer_name TEXT,
    brand_partner TEXT,
    property_category TEXT CHECK (property_category IN ('apartment','villa','hotel_room','land','commercial','other') OR property_category IS NULL),
    status TEXT,
    location_country TEXT,
    location_city TEXT,
    location_city_raw TEXT,
    location_area TEXT,
    masterplan_name TEXT,
    latitude REAL,
    longitude REAL,
    price_amount REAL,
    price_currency TEXT CHECK (price_currency IN ('AED','SAR','USD','GBP','EUR','QAR','OMR') OR price_currency IS NULL),
    price_display_text TEXT,
    listing_type TEXT CHECK (listing_type IN ('sale','rent') OR listing_type IS NULL),
    rent_period TEXT CHECK (rent_period IN ('monthly','yearly') OR rent_period IS NULL),
    area_sqm_min REAL,
    area_sqm_max REAL,
    bedrooms TEXT,
    bedrooms_min INTEGER,
    bedrooms_max INTEGER,
    bathrooms INTEGER,
    unit_types_raw TEXT,
    unit_types_normalized TEXT NOT NULL DEFAULT '[]',
    amenities TEXT NOT NULL DEFAULT '[]',
    expected_completion_date TEXT,
    expected_completion_raw TEXT,
    image_urls TEXT NOT NULL DEFAULT '[]',
    brochure_url TEXT,
    related_source_ids TEXT NOT NULL DEFAULT '[]',
    posted_or_updated_date TEXT,
    scraped_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    raw_snapshot_path TEXT,
    UNIQUE (source_site, source_id)
);
CREATE INDEX IF NOT EXISTS idx_listings_city ON listings (location_city);
CREATE INDEX IF NOT EXISTS idx_listings_type ON listings (record_type, listing_type);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings (price_amount);
CREATE INDEX IF NOT EXISTS idx_listings_active ON listings (is_active);
CREATE INDEX IF NOT EXISTS idx_listings_source ON listings (source_site);

CREATE TABLE IF NOT EXISTS content_documents (
    id TEXT PRIMARY KEY,
    source_site TEXT NOT NULL CHECK (source_site IN ('darglobal','wasalt')),
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK (content_type IN ('press_release','city_guide','brand_partner','company_info')),
    title TEXT NOT NULL,
    publish_date TEXT,
    body_text TEXT NOT NULL,
    related_source_ids TEXT NOT NULL DEFAULT '[]',
    scraped_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    UNIQUE (source_site, source_id)
);
CREATE INDEX IF NOT EXISTS idx_content_active ON content_documents (is_active);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id TEXT PRIMARY KEY,
    source_site TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    pages_attempted INTEGER DEFAULT 0,
    pages_succeeded INTEGER DEFAULT 0,
    pages_failed INTEGER DEFAULT 0,
    pages_skipped INTEGER DEFAULT 0,
    records_upserted INTEGER DEFAULT 0,
    records_deactivated INTEGER DEFAULT 0,
    status TEXT CHECK (status IN ('running','success','partial_failure','failed')),
    discovery_complete INTEGER NOT NULL DEFAULT 0,
    deactivation_eligible INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    citations TEXT,
    model_used TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    parent_type TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    parent_source_site TEXT NOT NULL,
    parent_source_id TEXT NOT NULL,
    parent_source_url TEXT NOT NULL,
    name TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    text TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    UNIQUE (parent_source_site, parent_source_id, chunk_type, chunk_id)
);
CREATE INDEX IF NOT EXISTS idx_chunks_parent ON chunks (parent_source_site, parent_source_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    parent_source_site UNINDEXED,
    parent_source_id UNINDEXED,
    name,
    text,
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def json_text(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False)


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(DDL)

    def upsert_listing(self, item: Listing) -> None:
        data = item.model_dump(mode="json")
        columns = [
            "id", "source_site", "source_id", "source_url", "record_type", "name", "description", "description_lang",
            "developer_name", "brand_partner", "property_category", "status", "location_country", "location_city",
            "location_city_raw", "location_area", "masterplan_name", "latitude", "longitude", "price_amount",
            "price_currency", "price_display_text", "listing_type", "rent_period", "area_sqm_min", "area_sqm_max",
            "bedrooms", "bedrooms_min", "bedrooms_max", "bathrooms", "unit_types_raw", "unit_types_normalized",
            "amenities", "expected_completion_date", "expected_completion_raw", "image_urls", "brochure_url",
            "related_source_ids", "posted_or_updated_date", "scraped_at", "updated_at", "is_active", "raw_snapshot_path",
        ]
        values = [data.get(c) for c in columns]
        for col in ("unit_types_normalized", "amenities", "image_urls", "related_source_ids"):
            values[columns.index(col)] = json_text(data.get(col))
        for col in ("scraped_at", "updated_at", "expected_completion_date", "posted_or_updated_date"):
            values[columns.index(col)] = iso(data.get(col))
        placeholders = ",".join("?" for _ in columns)
        updates = ",".join(f"{c}=excluded.{c}" for c in columns if c not in {"id", "source_site", "source_id"})
        with self.connect() as conn:
            conn.execute(
                f"INSERT INTO listings ({','.join(columns)}) VALUES ({placeholders}) "
                f"ON CONFLICT(source_site, source_id) DO UPDATE SET {updates}", values
            )

    def upsert_content(self, item: ContentDocument) -> None:
        data = item.model_dump(mode="json")
        cols = ["id", "source_site", "source_id", "source_url", "content_type", "title", "publish_date", "body_text", "related_source_ids", "scraped_at", "updated_at", "is_active"]
        values = [data.get(c) for c in cols]
        values[8] = json_text(data.get("related_source_ids"))
        values[6] = iso(data.get("publish_date"))
        values[9] = iso(data.get("scraped_at"))
        values[10] = iso(data.get("updated_at"))
        with self.connect() as conn:
            conn.execute(
                f"INSERT INTO content_documents ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) "
                f"ON CONFLICT(source_site, source_id) DO UPDATE SET "
                + ",".join(f"{c}=excluded.{c}" for c in cols if c not in {"id", "source_site", "source_id"}), values
            )

    def latest_content(self, source_site: str | None = None, content_type: str | None = None, limit: int = 8) -> list[sqlite3.Row]:
        clauses = ["is_active=1"]
        params: list[Any] = []
        if source_site:
            clauses.append("source_site=?")
            params.append(source_site)
        if content_type:
            clauses.append("content_type=?")
            params.append(content_type)
        with self.connect() as conn:
            return list(conn.execute(
                f"SELECT * FROM content_documents WHERE {' AND '.join(clauses)} "
                "ORDER BY publish_date IS NULL, publish_date DESC, updated_at DESC LIMIT ?",
                [*params, limit],
            ).fetchall())

    def get_listing(self, source_site: str, source_id: str, include_inactive: bool = True) -> sqlite3.Row | None:
        with self.connect() as conn:
            query = "SELECT * FROM listings WHERE source_site=? AND source_id=?"
            params: list[Any] = [source_site, source_id]
            if not include_inactive:
                query += " AND is_active=1"
            return conn.execute(query, params).fetchone()

    def list_active_records(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM listings WHERE is_active=1 ORDER BY source_site,name").fetchall()
            docs = conn.execute("SELECT * FROM content_documents WHERE is_active=1 ORDER BY source_site,title").fetchall()
            return list(rows) + list(docs)

    def mark_missing_inactive(self, source_site: str, seen_ids: set[str]) -> int:
        with self.connect() as conn:
            if not seen_ids:
                return 0
            placeholders = ",".join("?" for _ in seen_ids)
            cur = conn.execute(
                f"UPDATE listings SET is_active=0, updated_at=? WHERE source_site=? AND is_active=1 AND source_id NOT IN ({placeholders})",
                [utc_now(), source_site, *sorted(seen_ids)],
            )
            return cur.rowcount

    def mark_content_missing_inactive(self, source_site: str, seen_ids: set[str]) -> int:
        with self.connect() as conn:
            if not seen_ids:
                return 0
            placeholders = ",".join("?" for _ in seen_ids)
            cur = conn.execute(
                f"UPDATE content_documents SET is_active=0, updated_at=? WHERE source_site=? AND is_active=1 AND source_id NOT IN ({placeholders})",
                [utc_now(), source_site, *sorted(seen_ids)],
            )
            return cur.rowcount

    def create_scrape_run(self, source_site: str) -> str:
        run_id = str(uuid4())
        with self.connect() as conn:
            conn.execute("INSERT INTO scrape_runs(id,source_site,started_at,status) VALUES(?,?,?,?)", [run_id, source_site, utc_now(), "running"])
        return run_id

    def finish_scrape_run(self, run_id: str, *, status: str, discovery_complete: bool, deactivation_eligible: bool, pages_attempted: int, pages_succeeded: int, pages_failed: int, pages_skipped: int, records_upserted: int, records_deactivated: int, notes: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE scrape_runs SET finished_at=?, status=?, discovery_complete=?, deactivation_eligible=?,
                pages_attempted=?, pages_succeeded=?, pages_failed=?, pages_skipped=?, records_upserted=?,
                records_deactivated=?, notes=? WHERE id=?""",
                [utc_now(), status, int(discovery_complete), int(deactivation_eligible), pages_attempted, pages_succeeded, pages_failed, pages_skipped, records_upserted, records_deactivated, notes, run_id],
            )
            if status in {"success", "partial_failure"}:
                conn.execute("INSERT INTO app_meta(key,value) VALUES('last_scrape_completed_at',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", [utc_now()])

    def latest_scrape(self) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM scrape_runs ORDER BY finished_at DESC LIMIT 1").fetchone()

    def meta(self, key: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM app_meta WHERE key=?", [key]).fetchone()
            return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", [key, value])

    def stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            listings_total = conn.execute("SELECT COUNT(*) FROM listings WHERE is_active=1").fetchone()[0]
            darglobal = conn.execute("SELECT COUNT(*) FROM listings WHERE is_active=1 AND source_site='darglobal'").fetchone()[0]
            wasalt = conn.execute("SELECT COUNT(*) FROM listings WHERE is_active=1 AND source_site='wasalt'").fetchone()[0]
            docs = conn.execute("SELECT COUNT(*) FROM content_documents WHERE is_active=1").fetchone()[0]
            cities = [r[0] for r in conn.execute("SELECT DISTINCT location_city FROM listings WHERE is_active=1 AND location_city IS NOT NULL ORDER BY location_city").fetchall()]
            countries = [r[0] for r in conn.execute("SELECT DISTINCT location_country FROM listings WHERE is_active=1 AND location_country IS NOT NULL ORDER BY location_country").fetchall()]
            return {"listings_total": listings_total, "listings_darglobal": darglobal, "listings_wasalt": wasalt, "content_documents_total": docs, "cities_covered": cities, "countries_covered": countries, "last_scrape_completed_at": self.meta("last_scrape_completed_at")}

    def ensure_conversation(self, conversation_id: str | None = None) -> str:
        conversation_id = conversation_id or str(uuid4())
        now = utc_now()
        with self.connect() as conn:
            conn.execute("INSERT INTO conversations(id,created_at,last_active_at) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET last_active_at=excluded.last_active_at", [conversation_id, now, now])
        return conversation_id

    def add_message(self, conversation_id: str, role: str, content: str, citations: list[dict[str, Any]] | None = None, model_used: str | None = None) -> str:
        message_id = str(uuid4())
        with self.connect() as conn:
            conn.execute("INSERT INTO messages(id,conversation_id,role,content,citations,model_used,created_at) VALUES(?,?,?,?,?,?,?)", [message_id, conversation_id, role, content, json.dumps(citations or []), model_used, utc_now()])
        return message_id

    def history(self, conversation_id: str, limit: int = 8) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(reversed(conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at DESC LIMIT ?", [conversation_id, limit * 2]).fetchall()))

    def replace_chunks(self, chunks: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM chunks_fts")
            conn.execute("DELETE FROM chunks")
            for c in chunks:
                conn.execute("INSERT INTO chunks(chunk_id,parent_type,parent_id,parent_source_site,parent_source_id,parent_source_url,name,chunk_type,text,is_active) VALUES(?,?,?,?,?,?,?,?,?,1)", [c["chunk_id"], c["parent_type"], c["parent_id"], c["parent_source_site"], c["parent_source_id"], c["parent_source_url"], c["name"], c["chunk_type"], c["text"]])
                conn.execute("INSERT INTO chunks_fts(chunk_id,parent_source_site,parent_source_id,name,text) VALUES(?,?,?,?,?)", [c["chunk_id"], c["parent_source_site"], c["parent_source_id"], c["name"], c["text"]])

    def search_chunks(self, query: str, limit: int = 8, source_site: str | None = None, source_ids: set[str] | None = None, source_keys: set[tuple[str, str]] | None = None) -> list[sqlite3.Row]:
        terms = [t for t in _fts_terms(query) if len(t) > 1]
        if not terms:
            return []
        match = " OR ".join(f'"{t.replace(chr(34), "")}"' for t in terms[:24])
        with self.connect() as conn:
            sql = "SELECT c.*, bm25(chunks_fts) AS rank FROM chunks_fts JOIN chunks c USING(chunk_id) WHERE chunks_fts MATCH ? AND c.is_active=1"
            params: list[Any] = [match]
            if source_site:
                sql += " AND c.parent_source_site=?"
                params.append(source_site)
            if source_keys:
                predicates = []
                for key_site, key_id in sorted(source_keys):
                    predicates.append("(c.parent_source_site=? AND c.parent_source_id=?)")
                    params.extend([key_site, key_id])
                sql += " AND (" + " OR ".join(predicates) + ")"
            elif source_ids:
                sql += f" AND c.parent_source_id IN ({','.join('?' for _ in source_ids)})"
                params.extend(sorted(source_ids))
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)
            return list(conn.execute(sql, params).fetchall())


def _fts_terms(text: str) -> list[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    stop = {"the", "and", "for", "what", "with", "does", "have", "this", "that", "there", "about", "from", "into", "are", "you", "how", "much", "tell", "me", "is", "in", "of", "to", "a", "an"}
    return [word for word in cleaned.split() if word not in stop and len(word) > 1]


def row_to_listing(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for col in ("unit_types_normalized", "amenities", "image_urls", "related_source_ids"):
        try:
            result[col] = json.loads(result.get(col) or "[]")
        except json.JSONDecodeError:
            result[col] = []
    result["is_active"] = bool(result.get("is_active"))
    return result
