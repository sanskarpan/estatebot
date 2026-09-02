"""Build the low-memory SQLite FTS5 index from active canonical records."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from backend.app.config import get_settings
from backend.app.db.database import Database, row_to_listing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _words(text: str) -> list[str]:
    return re.findall(r"\S+", text or "")


def _chunks(text: str, size: int = 420, overlap: int = 60) -> list[str]:
    words = _words(text)
    if not words:
        return []
    result = []
    step = max(1, size - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + size])
        if chunk:
            result.append(chunk)
        if start + size >= len(words):
            break
    return result


def _chunk_id(site: str, source_id: str, chunk_type: str, index: int = 0) -> str:
    return hashlib.sha1(f"{site}:{source_id}:{chunk_type}:{index}".encode()).hexdigest()


def listing_chunks(row: Any) -> list[dict[str, Any]]:
    item = row_to_listing(row)
    price = item.get('price_display_text') or (f"{item.get('price_amount')} {item.get('price_currency')}" if item.get('price_amount') else 'not published')
    facts = [
        f"{item['name']} is a {item.get('record_type', 'property')} from {item['source_site']}.",
        f"Location: {', '.join(x for x in [item.get('location_area'), item.get('location_city'), item.get('location_country')] if x) or 'not published'}.",
        f"Property category: {item.get('property_category') or 'not published'}. Status: {item.get('status') or 'not published'}.",
        f"Listing type: {item.get('listing_type') or 'not published'}. Price: {price}.",
        f"Bedrooms: {item.get('bedrooms') or 'not published'}. Area: {item.get('area_sqm_min') or 'not published'} to {item.get('area_sqm_max') or item.get('area_sqm_min') or 'not published'} square metres.",
    ]
    if item.get("expected_completion_raw") or item.get("expected_completion_date"):
        facts.append(f"Expected completion: {item.get('expected_completion_raw') or item.get('expected_completion_date')}.")
    if item.get("brand_partner"):
        facts.append(f"Brand partner: {item['brand_partner']}.")
    if item.get("unit_types_raw"):
        facts.append(f"Unit types: {item['unit_types_raw']}.")
    output = [{
        "chunk_id": _chunk_id(item["source_site"], item["source_id"], "overview"), "parent_type": "listing", "parent_id": item["id"],
        "parent_source_site": item["source_site"], "parent_source_id": item["source_id"], "parent_source_url": item["source_url"], "name": item["name"],
        "chunk_type": "overview", "text": " ".join(facts),
    }]
    if item.get("amenities"):
        output.append({**output[0], "chunk_id": _chunk_id(item["source_site"], item["source_id"], "amenities"), "chunk_type": "amenities", "text": f"Amenities at {item['name']}: " + ", ".join(item["amenities"]) + "."})
    description = item.get("description") or ""
    if len(_words(description)) <= 40:
        if description:
            output[0]["text"] += f" Description: {description}"
    else:
        for index, text in enumerate(_chunks(description)):
            output.append({**output[0], "chunk_id": _chunk_id(item["source_site"], item["source_id"], "body", index), "chunk_type": "body", "text": text})
    return output


def document_chunks(row: Any) -> list[dict[str, Any]]:
    item = dict(row)
    body = item["body_text"]
    output = []
    for index, text in enumerate(_chunks(body)):
        output.append({
            "chunk_id": _chunk_id(item["source_site"], item["source_id"], "body", index), "parent_type": "content_document", "parent_id": item["id"],
            "parent_source_site": item["source_site"], "parent_source_id": item["source_id"], "parent_source_url": item["source_url"], "name": item["title"],
            "chunk_type": "body", "text": f"{item['title']}. {text}",
        })
    return output


def build_index(db: Database) -> int:
    chunks: list[dict[str, Any]] = []
    with db.connect() as conn:
        listings = conn.execute("SELECT * FROM listings WHERE is_active=1").fetchall()
        documents = conn.execute("SELECT * FROM content_documents WHERE is_active=1").fetchall()
    for row in listings:
        chunks.extend(listing_chunks(row))
    for row in documents:
        chunks.extend(document_chunks(row))
    db.replace_chunks(chunks)
    logger.info("index_built", extra={"records": len(listings) + len(documents), "chunks": len(chunks)})
    return len(chunks)


if __name__ == "__main__":
    settings = get_settings()
    build_index(Database(settings.database_path))
