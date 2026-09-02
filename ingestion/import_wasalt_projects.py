"""Import the audited standard-browser Wasalt project capture."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.config import get_settings
from backend.app.db.database import Database
from ingestion.build_index import build_index
from scraper.wasalt.browser_capture import project_from_capture


def import_capture(db: Database, path: str | Path = "data/wasalt_project_capture.json") -> int:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    captured_at = payload.get("captured_at")
    count = 0
    for raw in payload.get("records", []):
        db.upsert_listing(project_from_capture(raw, captured_at))
        count += 1
    if count:
        db.set_meta("wasalt_project_capture_at", str(captured_at or "unknown"))
        if captured_at and (not db.meta("last_scrape_completed_at") or str(captured_at) > str(db.meta("last_scrape_completed_at"))):
            db.set_meta("last_scrape_completed_at", str(captured_at))
        build_index(db)
    return count


if __name__ == "__main__":
    print(import_capture(Database(get_settings().database_path)))
