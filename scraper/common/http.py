"""Polite, cached, bounded HTTP client used by both crawlers."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from backend.app.config import Settings

logger = logging.getLogger(__name__)


WAF_SIGNATURES = ("incapsula incident", "request unsuccessful", "cf-chl-", "cf-mitigated", "just a moment...", "enable javascript and cookies to continue")


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str
    final_url: str
    from_cache: bool = False


class PoliteHTTPClient:
    def __init__(self, settings: Settings, cache_dir: str | Path | None = None):
        self.settings = settings
        self.cache_dir = Path(cache_dir or settings.raw_snapshot_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(
            headers={"User-Agent": settings.scraper_user_agent, "Accept-Language": "en-US,en;q=0.8"},
            follow_redirects=True,
            timeout=httpx.Timeout(settings.scrape_read_timeout_seconds, connect=settings.scrape_connect_timeout_seconds),
        )
        self.last_request: dict[str, float] = {}
        self.robots: dict[str, tuple[RobotFileParser, float]] = {}
        self.failures: dict[str, int] = {}
        self.circuit_open_until: dict[str, float] = {}

    def close(self) -> None:
        self.client.close()

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.http.json"

    def _robots_for(self, url: str) -> tuple[RobotFileParser | None, float]:
        domain = urlparse(url).netloc.lower()
        if domain in self.robots:
            return self.robots[domain]
        robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
        parser = RobotFileParser()
        delay = self.settings.scrape_delay_seconds
        try:
            response = self.client.get(robots_url)
            if response.status_code == 200 and not self._is_waf(response.text, response.status_code) and "<html" not in response.text[:500].lower():
                lines = response.text.splitlines()
                parser.parse(lines)
                for line in lines:
                    if line.lower().startswith("crawl-delay:"):
                        try:
                            delay = max(delay, float(line.split(":", 1)[1].strip()))
                        except ValueError:
                            pass
                logger.info("robots_loaded", extra={"domain": domain, "delay_seconds": delay, "status": response.status_code})
            else:
                parser.parse(["User-agent: *", "Allow: /", "Disallow: /api", "Disallow: /account", "Disallow: /login", "Disallow: /search"])
                logger.warning("robots_unreachable_conservative", extra={"domain": domain, "status": response.status_code})
        except Exception as exc:
            parser.parse(["User-agent: *", "Allow: /", "Disallow: /api", "Disallow: /account", "Disallow: /login", "Disallow: /search"])
            logger.warning("robots_fetch_failed_conservative", extra={"domain": domain, "error": str(exc)})
        self.robots[domain] = (parser, delay)
        return parser, delay

    def allowed(self, url: str) -> bool:
        parser, _ = self._robots_for(url)
        return bool(parser and parser.can_fetch(self.settings.scraper_user_agent, url))

    def fetch(self, url: str, *, cache_key: str | None = None) -> FetchResult | None:
        if not self.allowed(url):
            logger.warning("robots_disallowed", extra={"url": url})
            return None
        cache_path = self._cache_path(cache_key or url)
        if self.settings.scrape_cache_enabled and cache_path.exists():
            try:
                payload = json.loads(cache_path.read_text())
                return FetchResult(url=url, status_code=payload["status_code"], text=payload["text"], final_url=payload.get("final_url", url), from_cache=True)
            except Exception:
                cache_path.unlink(missing_ok=True)
        domain = urlparse(url).netloc.lower()
        circuit_until = self.circuit_open_until.get(domain, 0)
        if circuit_until > time.monotonic():
            logger.warning("domain_circuit_open", extra={"domain": domain, "retry_after_seconds": int(circuit_until - time.monotonic())})
            return None
        _, delay = self._robots_for(url)
        wait = delay - (time.monotonic() - self.last_request.get(domain, 0))
        if wait > 0:
            time.sleep(wait)
        attempts = max(1, self.settings.scrape_max_retries)
        for attempt in range(attempts):
            try:
                self.last_request[domain] = time.monotonic()
                response = self.client.get(url)
                text = response.text
                if self._is_waf(text, response.status_code):
                    raise RuntimeError("waf_challenge")
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise RuntimeError(f"retryable_http_{response.status_code}")
                self.failures[domain] = 0
                self.circuit_open_until.pop(domain, None)
                result = FetchResult(url=url, status_code=response.status_code, text=text, final_url=str(response.url))
                if self.settings.scrape_cache_enabled and response.status_code == 200:
                    cache_path.write_text(json.dumps({"status_code": response.status_code, "text": text, "final_url": str(response.url)}, ensure_ascii=False))
                return result
            except Exception as exc:
                self.failures[domain] = self.failures.get(domain, 0) + 1
                if self.failures[domain] >= 10:
                    self.circuit_open_until[domain] = time.monotonic() + 300
                    logger.error("domain_circuit_opened", extra={"domain": domain, "pause_seconds": 300})
                logger.warning("fetch_failed", extra={"url": url, "attempt": attempt + 1, "error": str(exc)})
                if attempt + 1 < attempts:
                    time.sleep((5, 15, 60)[min(attempt, 2)])
        logger.error("fetch_skipped", extra={"url": url, "failures": self.failures.get(domain, 0)})
        return None

    @staticmethod
    def _is_waf(text: str, status_code: int) -> bool:
        sample = re.sub(r"\s+", " ", text[:100000].lower())
        return any(signature in sample for signature in WAF_SIGNATURES) or (status_code in {401, 403, 429} and "<html" in sample)
