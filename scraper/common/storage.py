from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from backend.app.db.database import Database
from backend.app.models.schema import ContentDocument, Listing

logger = logging.getLogger(__name__)


def persist_listing(db: Database, item: Listing) -> None:
    db.upsert_listing(item)


def persist_document(db: Database, item: ContentDocument) -> None:
    db.upsert_content(item)


def snapshot_path(raw_dir: str | Path, source_site: str, source_id: str, content: str) -> str:
    root = Path(raw_dir) / source_site
    root.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in source_id)[:160]
    path = root / f"{safe}.html"
    path.write_text(content, encoding="utf-8")
    return str(path)
