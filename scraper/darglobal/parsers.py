from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from backend.app.models.schema import ContentDocument, Listing
from scraper.common.normalize import canonical_url, clean_text, clean_lines
from scraper.common.parsing import extract_facts, soup_for


BRANDS = ("Trump Organization", "Trump", "Aston Martin", "Pagani", "FENDI Casa", "Missoni", "Elie Saab", "Mouawad", "Lamborghini", "W Hotels", "Marriott")


def discover_project_urls(base_url: str, html: str) -> list[str]:
    soup = soup_for(html); output = []
    for link in soup.select("a[href]"):
        href = link.get("href", "")
        full = canonical_url(base_url, href)
        path = urlparse(full).path.lower()
        if urlparse(full).netloc.endswith("darglobal.co.uk") and path not in {"/", "/projects"} and not any(x in path for x in ("/press", "/contact", "/about", "/login", "/privacy", "/terms")) and not re.search(r"\.(?:jpg|jpeg|png|svg|pdf|mp4)$", path):
            output.append(full)
    return list(dict.fromkeys(output))


def discover_press_urls(base_url: str, html: str) -> list[str]:
    soup = soup_for(html); output = []
    for link in soup.select("a[href]"):
        full = canonical_url(base_url, link.get("href", ""))
        path = urlparse(full).path.lower()
        if urlparse(full).netloc.endswith("darglobal.co.uk") and "/press" in path and path.rstrip("/") != "/press":
            output.append(full)
    return list(dict.fromkeys(output))


def parse_project(url: str, html: str, scraped_at=None) -> Listing:
    scraped_at = scraped_at or datetime.now(timezone.utc)
    soup = soup_for(html); facts = extract_facts(soup, url)
    text = facts.get("description") or ""
    brand = next((b for b in BRANDS if b.lower() in text.lower() or b.lower() in facts["name"].lower()), None)
    source_id = urlparse(url).path.strip("/").lower().replace("/", "--") or facts["name"].lower().replace(" ", "-")
    related = []
    for link in soup.select("a[href]"):
        href = canonical_url(url, link.get("href", ""))
        if href != url and urlparse(href).netloc.endswith("darglobal.co.uk") and urlparse(href).path not in {"/projects"}:
            related.append(urlparse(href).path.strip("/"))
    amenities = clean_lines([x.get_text(" ", strip=True) for x in soup.select("[class*=amenit] li, [class*=feature] li")])[:50]
    return Listing(source_site="darglobal", source_id=source_id, source_url=url, record_type="project", developer_name="DarGlobal", brand_partner=brand, amenities=amenities, related_source_ids=list(dict.fromkeys(related))[:30], scraped_at=scraped_at, updated_at=scraped_at, **facts)


def parse_press(url: str, html: str, scraped_at=None) -> ContentDocument:
    scraped_at = scraped_at or datetime.now(timezone.utc)
    soup = soup_for(html)
    title = clean_text(soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else None) or "DarGlobal press article"
    body = extract_facts(soup, url).get("description") or title
    source_id = urlparse(url).path.strip("/")
    return ContentDocument(source_site="darglobal", source_id=source_id, source_url=url, content_type="press_release", title=title, body_text=body, scraped_at=scraped_at, updated_at=scraped_at)
