"""Normalize an auditable capture of visible public DarGlobal project pages.

The ordinary HTTP spider remains the preferred refresh path. This importer is a
WAF-safe fallback for captures made through a standard browser session; it does
not contain authentication, CAPTCHA solving, cookie export, or bypass logic.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from backend.app.models.schema import ContentDocument, Listing
from scraper.common.normalize import clean_lines, clean_text, parse_area_sqm, parse_bedrooms, parse_date, parse_price
from scraper.common.parsing import infer_category, infer_location
from scraper.darglobal.parsers import BRANDS


SECTION_ENDS = {
    "PHOTO GALLERY", "VIEW ALL IMAGES", "KEY FEATURES", "WHY INVEST",
    "FREQUENTLY ASKED QUESTIONS", "OTHER PROJECTS", "REGISTER YOUR INTEREST",
}


def _lines(record: dict[str, Any]) -> list[str]:
    return [line.strip() for line in str(record.get("text") or "").splitlines() if line.strip()]


def _after(lines: list[str], *labels: str) -> tuple[str | None, str | None]:
    wanted = {label.upper() for label in labels}
    for index, line in enumerate(lines[:-1]):
        if line.upper() in wanted:
            return line, clean_text(lines[index + 1])
    return None, None


def _section(lines: list[str], label: str) -> list[str]:
    try:
        start = next(index for index, line in enumerate(lines) if line.upper() == label)
    except StopIteration:
        return []
    output: list[str] = []
    for line in lines[start + 1:]:
        if line.upper() in SECTION_ENDS:
            break
        output.append(line)
    return clean_lines(output)


def _description(lines: list[str], name: str) -> str | None:
    start = next((index for index, line in enumerate(lines) if line.upper() == name.upper()), 0)
    end = next((index for index, line in enumerate(lines[start + 1:], start + 1) if line.upper() in {"OTHER PROJECTS", "REGISTER YOUR INTEREST"}), len(lines))
    return clean_text("\n".join(lines[start:end]))


def _location(raw: str, description: str) -> tuple[str | None, str | None, str | None, str | None]:
    city, country, area, masterplan = infer_location(raw)
    description_city, description_country, description_area, description_masterplan = infer_location(description[:2500])
    city = city or description_city
    country = country or description_country
    area = area or description_area
    masterplan = masterplan or description_masterplan
    upper = raw.upper()
    if "RAK" in upper:
        city = "Ras Al Khaimah"
    if not country and "ENGLAND" in upper:
        country = "United Kingdom"
    if not country:
        country = {
            "Dubai": "United Arab Emirates", "Ras Al Khaimah": "United Arab Emirates",
            "Riyadh": "Saudi Arabia", "Jeddah": "Saudi Arabia", "Muscat": "Oman",
            "Doha": "Qatar", "London": "United Kingdom", "Benahavís": "Spain",
        }.get(city or "")
    if not area:
        for candidate in ("Al Marjan Island", "Jumeirah Golf Estates", "AIDA", "Amaya", "Rayana", "Wadi Safar", "Noonu Atoll", "Cortesin"):
            if candidate.lower() in f"{raw} {description}".lower():
                area = candidate
                break
    return city, country, area, masterplan


def _category(record: dict[str, Any], name: str, property_type: str | None, unit_types: str | None, description: str) -> str:
    primary = f"{name} {record.get('name') or ''} {record.get('href') or ''} {property_type or ''} {unit_types or ''}"
    category = infer_category(primary)
    if category:
        return category
    lower = primary.lower()
    if "mansion" in lower:
        return "villa"
    if any(token in lower for token in ("penthouse", "residence", "residential tower")):
        return "apartment"
    return infer_category(description[:1500]) or "other"


def listing_from_capture(record: dict[str, Any], captured_at: str | None = None) -> Listing:
    if record.get("error"):
        raise ValueError(f"capture failed for {record.get('href')}: {record['error']}")
    url = str(record.get("href") or "")
    if "darglobal.co.uk" not in urlparse(url).netloc:
        raise ValueError("capture source URL is not a DarGlobal public page")
    name = clean_text(record.get("h1") or record.get("name")) or "DarGlobal project"
    lines = _lines(record)
    description = _description(lines, name) or clean_text(record.get("meta")) or name
    raw_location = clean_text(record.get("location")) or ""
    city, country, area, masterplan = _location(raw_location, description)
    property_label, property_type = _after(lines, "PROPERTY TYPE")
    _, status = _after(lines, "STATUS")
    _, unit_types = _after(lines, "UNIT TYPE", "UNITS")
    bedrooms, bedrooms_min, bedrooms_max, normalized_units = parse_bedrooms(unit_types)
    area_label, area_value = _after(lines, "AREA (SQM)", "AREA FROM (SQM)", "AREA BUA (SQM)", "AREA (SQFT)", "AREA FROM (SQFT)", "AREA BUA (SQFT)")
    area_text = f"{area_value or ''} {'sqft' if area_label and 'SQFT' in area_label.upper() else 'sqm'}" if area_value else None
    area_min, area_max = parse_area_sqm(area_text)
    _, completion = _after(lines, "EXPECTED COMPLETION DATE", "COMPLETION DATE", "HANDOVER DATE")
    _, price_text = _after(lines, "PRICE", "STARTING PRICE", "PRICE FROM")
    price, currency, price_display = parse_price(price_text)
    brand = next((brand for brand in BRANDS if brand.lower() in f"{name} {description}".lower()), None)
    images = [str(value) for value in record.get("images", []) if str(value).startswith(("http://", "https://"))]
    brochure = record.get("brochure")
    if brochure and ("modern_slavery" in brochure.lower() or "brochure" not in brochure.lower()):
        brochure = None
    timestamp = datetime.fromisoformat(captured_at.replace("Z", "+00:00")) if captured_at else datetime.now(timezone.utc)
    source_id = urlparse(url).path.strip("/").lower().replace("/", "--")
    return Listing(
        source_site="darglobal",
        source_id=source_id,
        source_url=url,
        record_type="project",
        name=name,
        description=description[:12000],
        description_lang="en",
        developer_name="DarGlobal",
        brand_partner=brand,
        property_category=_category(record, name, property_type, unit_types, description),
        status=status,
        location_country=country,
        location_city=city,
        location_city_raw=raw_location,
        location_area=area,
        masterplan_name=masterplan,
        price_amount=price,
        price_currency=currency,
        price_display_text=price_display,
        area_sqm_min=area_min,
        area_sqm_max=area_max,
        bedrooms=bedrooms,
        bedrooms_min=bedrooms_min,
        bedrooms_max=bedrooms_max,
        unit_types_raw=unit_types,
        unit_types_normalized=normalized_units,
        amenities=_section(lines, "AMENITIES")[:50],
        expected_completion_date=parse_date(completion),
        expected_completion_raw=completion,
        image_urls=list(dict.fromkeys(images))[:20],
        brochure_url=brochure,
        scraped_at=timestamp,
        updated_at=timestamp,
    )


def document_from_capture(record: dict[str, Any], captured_at: str | None = None) -> ContentDocument:
    """Normalize one public press page captured by a standard browser session."""
    if record.get("error"):
        raise ValueError(f"capture failed for {record.get('source_url')}: {record['error']}")
    url = str(record.get("source_url") or "")
    parsed = urlparse(url)
    if "darglobal.co.uk" not in parsed.netloc or not parsed.path.startswith("/press/"):
        raise ValueError("capture source URL is not a DarGlobal public press page")
    title = clean_text(record.get("title") or record.get("card_title")) or "DarGlobal press article"
    raw_body = str(record.get("body_text") or "")
    body_lines = [line.strip() for line in raw_body.splitlines() if line.strip()]
    title_index = next((index for index, line in enumerate(body_lines) if clean_text(line) == title), None)
    if title_index is not None:
        body_lines = body_lines[title_index + 1:]
    body = clean_text("\n".join(body_lines)) or clean_text(record.get("meta_description")) or title
    published = parse_date(str(record.get("published_at") or ""))
    timestamp = datetime.fromisoformat(captured_at.replace("Z", "+00:00")) if captured_at else datetime.now(timezone.utc)
    return ContentDocument(
        source_site="darglobal",
        source_id=parsed.path.strip("/").lower(),
        source_url=url,
        content_type="press_release",
        title=title,
        publish_date=published,
        body_text=body[:24000],
        scraped_at=timestamp,
        updated_at=timestamp,
    )
