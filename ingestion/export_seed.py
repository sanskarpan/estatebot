"""Export the current normalized corpus as a reproducible offline bootstrap snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.config import get_settings
from backend.app.db.database import Database, row_to_listing, utc_now


def export_seed(destination: str = "data/seed_corpus.json") -> int:
    db = Database(get_settings().database_path)
    with db.connect() as conn:
        listings = [row_to_listing(row) for row in conn.execute("SELECT * FROM listings WHERE is_active=1 ORDER BY source_site,source_id")]
        docs = []
        for row in conn.execute("SELECT * FROM content_documents WHERE is_active=1 ORDER BY source_site,source_id"):
            item = dict(row)
            item["related_source_ids"] = json.loads(item.get("related_source_ids") or "[]")
            item["is_active"] = bool(item["is_active"])
            docs.append(item)
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    Path(destination).write_text(json.dumps({"generated_by": "scraper.run_all", "generated_at": utc_now(), "last_scrape_completed_at": db.meta("last_scrape_completed_at"), "listings": listings, "content_documents": docs}, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(listings)


if __name__ == "__main__":
    print(export_seed())
