"""Optional offline corpus bootstrap for a fresh deployment volume."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.app.db.database import Database
from backend.app.models.schema import ContentDocument, Listing
from ingestion.build_index import build_index

logger = logging.getLogger(__name__)


def seed_if_empty(db: Database, path: str, enabled: bool = True) -> int:
    if not enabled or db.stats()["listings_total"] > 0:
        return 0
    seed_path = Path(path)
    if not seed_path.exists():
        return 0
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    count = 0
    for raw in payload.get("listings", []):
        db.upsert_listing(Listing.model_validate(raw)); count += 1
    for raw in payload.get("content_documents", []):
        db.upsert_content(ContentDocument.model_validate(raw))
    if count:
        generated_at = payload.get("last_scrape_completed_at")
        if not generated_at:
            generated_at = payload.get("generated_at")
        if not generated_at:
            timestamps = [str(raw.get("scraped_at")) for raw in payload.get("listings", []) + payload.get("content_documents", []) if raw.get("scraped_at")]
            generated_at = max(timestamps) if timestamps else None
        if generated_at:
            db.set_meta("last_scrape_completed_at", str(generated_at))
        build_index(db)
        logger.info("seed_corpus_loaded", extra={"listings": count, "path": str(seed_path)})
    return count
