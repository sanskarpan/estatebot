from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from backend.app.config import Settings
from backend.app.db.database import Database
from scraper.common.http import PoliteHTTPClient
from scraper.common.storage import persist_document, persist_listing, snapshot_path
from scraper.darglobal.parsers import discover_press_urls, discover_project_urls, parse_press, parse_project

logger = logging.getLogger(__name__)


class DarGlobalSpider:
    source = "darglobal"
    base = "https://darglobal.co.uk"

    def __init__(self, settings: Settings, db: Database):
        self.settings = settings; self.db = db; self.http = PoliteHTTPClient(settings)
        self.attempted = self.succeeded = self.failed = self.skipped = self.upserted = 0
        self.seen: set[str] = set(); self.documents_seen: set[str] = set(); self.discovery_complete = False

    def run(self) -> None:
        run_id = self.db.create_scrape_run(self.source); now = datetime.now(timezone.utc)
        try:
            index_url = f"{self.base}/projects"; self.attempted += 1; index = self.http.fetch(index_url)
            if not index or index.status_code != 200:
                self.failed += 1; self._finish(run_id, "failed", False, "Project index unavailable"); return
            project_urls = discover_project_urls(self.base, index.text)
            self.discovery_complete = bool(project_urls)
            for url in project_urls:
                self._scrape_project(url, now)
            press_index = self.http.fetch(f"{self.base}/press"); self.attempted += 1
            if press_index and press_index.status_code == 200:
                for url in discover_press_urls(f"{self.base}/press", press_index.text)[: self.settings.max_darglobal_press]:
                    self._scrape_press(url, now)
            status = "success" if self.failed == 0 else "partial_failure"
            deactivation = self.discovery_complete and status == "success"
            deactivated = self.db.mark_missing_inactive(self.source, self.seen) if deactivation else 0
            self.db.mark_content_missing_inactive(self.source, self.documents_seen) if deactivation else 0
            self._finish(run_id, status, deactivation, f"projects_discovered={len(project_urls)}; deactivated={deactivated}", deactivated)
        finally:
            self.http.close()

    def _scrape_project(self, url: str, now: datetime) -> None:
        self.attempted += 1; result = self.http.fetch(url)
        if not result or result.status_code != 200: self.failed += 1; return
        try:
            item = parse_project(result.final_url, result.text, now)
            item.raw_snapshot_path = snapshot_path(self.settings.raw_snapshot_dir, self.source, item.source_id, result.text) if self.settings.scrape_cache_enabled else None
            persist_listing(self.db, item); self.seen.add(item.source_id); self.succeeded += 1; self.upserted += 1
        except Exception as exc:
            self.failed += 1; logger.exception("darglobal_parse_failed", extra={"url": url, "error": str(exc)})

    def _scrape_press(self, url: str, now: datetime) -> None:
        self.attempted += 1; result = self.http.fetch(url)
        if not result or result.status_code != 200: self.failed += 1; return
        try:
            item = parse_press(result.final_url, result.text, now); persist_document(self.db, item); self.documents_seen.add(item.source_id); self.succeeded += 1; self.upserted += 1
        except Exception as exc:
            self.failed += 1; logger.exception("darglobal_press_parse_failed", extra={"url": url, "error": str(exc)})

    def _finish(self, run_id: str, status: str, eligible: bool, notes: str, deactivated: int = 0) -> None:
        self.db.finish_scrape_run(run_id, status=status, discovery_complete=self.discovery_complete, deactivation_eligible=eligible, pages_attempted=self.attempted, pages_succeeded=self.succeeded, pages_failed=self.failed, pages_skipped=self.skipped, records_upserted=self.upserted, records_deactivated=deactivated, notes=notes)
