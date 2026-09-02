from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.app.config import Settings
from backend.app.db.database import Database
from scraper.common.http import PoliteHTTPClient
from scraper.common.normalize import canonical_url
from scraper.common.storage import persist_document, persist_listing, snapshot_path
from scraper.wasalt.parsers import discover_listing_urls, parse_city_guide, parse_listing
from scraper.wasalt.sitemap import filter_listing_urls, urls_from_sitemap

logger = logging.getLogger(__name__)


class WasaltSpider:
    source = "wasalt"
    base = "https://wasalt.sa"
    cities = ("riyadh", "jeddah", "dammam")

    def __init__(self, settings: Settings, db: Database):
        self.settings = settings; self.db = db; self.http = PoliteHTTPClient(settings)
        self.attempted = self.succeeded = self.failed = self.skipped = self.upserted = 0
        self.seen: set[str] = set(); self.documents_seen: set[str] = set(); self.discovery_complete = False

    def run(self) -> None:
        run_id = self.db.create_scrape_run(self.source); now = datetime.now(timezone.utc); discovered_categories = 0
        try:
            sitemap_urls = self._sitemap_urls()
            for city in self.cities:
                for listing_type in ("sale", "rent"):
                    discovered_categories += 1
                    previous_links: set[str] = set()
                    for page in range(1, self.settings.max_pages_per_category + 1):
                        path = f"/en/properties-for-{listing_type}-in-{city}"
                        base_url = canonical_url(self.base, path + (f"?page={page}" if page > 1 else ""))
                        self.attempted += 1; landing = self.http.fetch(base_url)
                        if not landing or landing.status_code != 200:
                            self.failed += 1
                            if page == 1:
                                # The public Wasalt sitemap is a compliant discovery fallback;
                                # detail fetches still go through the same WAF-safe client.
                                links = filter_listing_urls(sitemap_urls, listing_type)[: max(0, self.settings.max_wasalt_listings - len(self.seen))]
                                for url in links:
                                    self._scrape_listing(url, listing_type, None, now)
                            break
                        try:
                            if page == 1:
                                guide = parse_city_guide(landing.final_url, landing.text, city, now); persist_document(self.db, guide); self.documents_seen.add(guide.source_id); self.upserted += 1
                        except Exception as exc: logger.warning("wasalt_guide_failed", extra={"url": base_url, "error": str(exc)})
                        links = discover_listing_urls(landing.final_url, landing.text)[: max(0, self.settings.max_wasalt_listings - len(self.seen))]
                        if not links or set(links) == previous_links: break
                        previous_links = set(links)
                        for url in links: self._scrape_listing(url, listing_type, city, now)
                        if len(self.seen) >= self.settings.max_wasalt_listings: break
                    if len(self.seen) >= self.settings.max_wasalt_listings: break
                if len(self.seen) >= self.settings.max_wasalt_listings: break
            self.discovery_complete = discovered_categories == len(self.cities) * 2 and self.failed == 0
            status = "success" if self.failed == 0 else "partial_failure"
            deactivation = self.discovery_complete
            deactivated = self.db.mark_missing_inactive(self.source, self.seen) if deactivation else 0
            self.db.mark_content_missing_inactive(self.source, self.documents_seen) if deactivation else 0
            self.db.finish_scrape_run(run_id, status=status, discovery_complete=self.discovery_complete, deactivation_eligible=deactivation, pages_attempted=self.attempted, pages_succeeded=self.succeeded, pages_failed=self.failed, pages_skipped=self.skipped, records_upserted=self.upserted, records_deactivated=deactivated, notes=f"cities={','.join(self.cities)}; listings_discovered={len(self.seen)}")
        finally:
            self.http.close()

    def _sitemap_urls(self) -> list[str]:
        urls: list[str] = []
        for sitemap in ("https://cdn.wasalt.sa/sitemap/product_sitemap_en_sa.xml.gz", "https://cdn.wasalt.sa/sitemap/rental_pdp_sitemap_en_sa.xml.gz"):
            self.attempted += 1
            result = self.http.fetch(sitemap)
            if result and result.status_code == 200:
                urls.extend(urls_from_sitemap(result.text))
        # Keep global fallback bounded and deterministic; city-specific landing pages
        # are preferred whenever they are available.
        return filter_listing_urls(list(dict.fromkeys(urls)))[: self.settings.max_wasalt_listings]

    def _scrape_listing(self, url: str, listing_type: str, city: str | None, now: datetime) -> None:
        if len(self.seen) >= self.settings.max_wasalt_listings: return
        self.attempted += 1; result = self.http.fetch(url)
        if not result or result.status_code != 200: self.failed += 1; return
        try:
            item = parse_listing(result.final_url, result.text, listing_type, city, now); item.raw_snapshot_path = snapshot_path(self.settings.raw_snapshot_dir, self.source, item.source_id, result.text) if self.settings.scrape_cache_enabled else None
            persist_listing(self.db, item); self.seen.add(item.source_id); self.succeeded += 1; self.upserted += 1
        except Exception as exc:
            self.failed += 1; logger.exception("wasalt_listing_parse_failed", extra={"url": url, "error": str(exc)})
