from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from backend.app.models.schema import ContentDocument, Listing
from scraper.common.normalize import canonical_url, clean_lines, clean_text, normalize_city
from scraper.common.parsing import extract_facts, soup_for


def _is_listing_url(url: str) -> bool:
    """Return True only for detail-like Wasalt paths, not search/landing pages."""
    parsed = urlparse(url)
    if not parsed.netloc.endswith(("wasalt.sa", "wasalt.com")):
        return False
    path = parsed.path.lower().rstrip("/")
    if any(token in path for token in ("properties-for-sale-in", "properties-for-rent-in", "/en/properties-for-")):
        return False
    return any(token in path for token in ("/property/", "/listing/", "/real-estate/"))


def discover_listing_urls(base_url: str, html: str) -> list[str]:
    soup = soup_for(html); output = []
    for link in soup.select("a[href]"):
        full = canonical_url(base_url, link.get("href", ""))
        if _is_listing_url(full):
            output.append(full)
    # JSON-LD item lists can contain links not represented as ordinary cards.
    for script in soup.select('script[type="application/ld+json"]'):
        text = script.get_text(" ", strip=True)
        for candidate in re.findall(r'https?://[^"\\ ]*wasalt\.(?:sa|com)[^"\\ ]+', text):
            candidate = candidate.rstrip(".,)")
            if _is_listing_url(candidate):
                output.append(candidate)
    return list(dict.fromkeys(output))


def parse_listing(url: str, html: str, listing_type: str, city_hint: str | None = None, scraped_at=None) -> Listing:
    scraped_at = scraped_at or datetime.now(timezone.utc)
    soup = soup_for(html); facts = extract_facts(soup, url, "SAR")
    text = facts.get("description") or ""
    # The city-specific discovery URL is the least ambiguous signal: listing
    # descriptions and navigation may mention other cities incidentally.
    city = normalize_city(city_hint) or facts.get("location_city")
    if not city:
        for candidate in ("Riyadh", "Jeddah", "Dammam", "Khobar", "Mecca", "Medina"):
            if re.search(rf"\b{candidate}\b", text, re.I): city = candidate; break
    source_id = urlparse(url).path.strip("/").split("/")[-1].lower()
    record_type = "rent_listing" if listing_type == "rent" else "sale_listing"
    facts["location_city_raw"] = city_hint
    facts["status"] = "For Rent" if listing_type == "rent" else "For Sale"
    facts["rent_period"] = "monthly" if listing_type == "rent" and re.search(r"\bmonthly|per month\b", text, re.I) else "yearly" if listing_type == "rent" else None
    amenities = clean_lines([x.get_text(" ", strip=True) for x in soup.select("[class*=amenit] li, [class*=feature] li")])[:50]
    facts["location_city"] = city
    return Listing(source_site="wasalt", source_id=source_id or facts["name"].lower().replace(" ", "-"), source_url=url, record_type=record_type, developer_name=None, listing_type=listing_type, amenities=amenities, scraped_at=scraped_at, updated_at=scraped_at, **facts)


def parse_city_guide(url: str, html: str, city: str, scraped_at=None) -> ContentDocument:
    scraped_at = scraped_at or datetime.now(timezone.utc)
    soup = soup_for(html); title = clean_text(soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else None) or f"Wasalt {city} property guide"
    body = clean_text(soup.get_text(" ", strip=True)) or title
    return ContentDocument(source_site="wasalt", source_id=f"city-guide-{city.lower()}", source_url=url, content_type="city_guide", title=title, body_text=body[:20000], scraped_at=scraped_at, updated_at=scraped_at)
