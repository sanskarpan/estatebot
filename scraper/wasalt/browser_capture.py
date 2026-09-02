"""Normalize public Wasalt project pages captured in a standard browser."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse

from backend.app.models.schema import Listing
from scraper.common.normalize import clean_lines, clean_text, normalize_city, parse_area_sqm, parse_bedrooms, parse_date
from scraper.common.parsing import infer_category


def _lines(record: dict[str, Any]) -> list[str]:
    return [line.strip() for line in str(record.get("text") or "").splitlines() if line.strip()]


def _before(lines: list[str], label: str) -> str | None:
    try:
        index = next(i for i, line in enumerate(lines) if line.lower() == label.lower())
    except StopIteration:
        return None
    return clean_text(lines[index - 1]) if index else None


def _section(lines: list[str], start_label: str, end_labels: set[str]) -> list[str]:
    try:
        start = next(i for i, line in enumerate(lines) if line.lower() == start_label.lower())
    except StopIteration:
        return []
    output: list[str] = []
    normalized_end_labels = tuple(value.lower() for value in end_labels)
    for line in lines[start + 1:]:
        if line.lower().startswith(normalized_end_labels):
            break
        output.append(line)
    return clean_lines(output)


def _compact_price(text: str) -> tuple[float | None, str | None]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*([MK])?", text, re.IGNORECASE)
    if not match:
        return None, None
    factor = {"K": 1_000, "M": 1_000_000}.get((match.group(2) or "").upper(), 1)
    return float(match.group(1)) * factor, clean_text(text)


def project_from_capture(record: dict[str, Any], captured_at: str | None = None) -> Listing:
    if record.get("error"):
        raise ValueError(f"capture failed for {record.get('href')}: {record['error']}")
    url = str(record.get("href") or "")
    parsed = urlparse(url)
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if not ({"wasalt.sa", "www.wasalt.sa"} & {parsed.netloc}) or len(parts) < 4 or parts[1].lower() != "project":
        raise ValueError("capture source URL is not a Wasalt public project page")
    lines = _lines(record)
    try:
        project_index = next(i for i, line in enumerate(lines) if line.lower() == "project")
    except StopIteration as exc:
        raise ValueError("project marker missing from Wasalt capture") from exc
    name = clean_text(lines[project_index - 1]) or "Wasalt project"
    city_raw = parts[2]
    city = normalize_city(city_raw) or {"Aldammam": "Dammam", "Al Ahsa": "Al Ahsa", "Makkah Al Mukarramah": "Mecca", "Madinah": "Medina"}.get(city_raw, city_raw)
    location_line = next((clean_text(lines[i + 1]) for i in range(project_index + 1, len(lines) - 1) if clean_text(lines[i]) == name), None) or city_raw
    location_line = re.sub(r"\s*Map view\s*$", "", location_line or "", flags=re.IGNORECASE)
    area = clean_text((location_line or "").split(",", 1)[0])
    if area and area.lower() == city.lower():
        area = None
    status = next((line for line in lines[project_index + 1:project_index + 5] if line.lower() not in {"for sale", name.lower()}), None)
    completion_raw = next((line for line in lines if re.search(r"\b(?:completion|handover)\b.*\b20\d{2}\b|\bQ[1-4]\s+20\d{2}\b", line, re.I)), None)
    bedrooms, bedrooms_min, bedrooms_max, units = parse_bedrooms(_before(lines, "Bedrooms"))
    bathroom_text = _before(lines, "Bathrooms")
    bathroom_values = [int(value) for value in re.findall(r"\d+", bathroom_text or "")]
    area_match = next((line for line in lines if re.search(r"\d[\d,.]*\s*(?:-|–|to)\s*\d[\d,.]*\s*sqm", line, re.I)), None)
    area_min, area_max = parse_area_sqm(area_match)
    property_types = _section(lines, "Available Property Types", {"Call Now", "Brochure", "Gallery", "Street Information", "Additional Information"})
    category = infer_category(" ".join([name, *property_types])) or infer_category(" ".join(lines[:80])) or "other"
    description_lines = _section(lines, "About Project", {"Units Available", "For Sale", "Register Interest"})
    description = clean_text("\n".join(description_lines))
    # Some public pages publish only punctuation in the About section. Their
    # page metadata is still first-party visible text and is a safer fallback
    # than synthesizing or guessing a project description.
    if not description or not re.search(r"[\w\u0600-\u06ff]{3,}", description):
        description = clean_text(record.get("meta")) or name
    price_text = clean_text(record.get("card_text")) or ""
    price_range = re.match(r"([\d.]+\s*[MK]?\s*-\s*[\d.]+\s*[MK]?)", price_text, re.I)
    if not price_range:
        starts_index = next((i for i, line in enumerate(lines[:-1]) if line.lower() == "starts from"), None)
        price_display = lines[starts_index + 1] if starts_index is not None else ""
    else:
        price_display = price_range.group(1)
    price, compact_display = _compact_price(price_display)
    ref_index = next((i for i, line in enumerate(lines) if line.lower() == "ref no."), None)
    developer_name = clean_text(lines[ref_index - 1]) if ref_index is not None and ref_index > 0 else None
    if developer_name and (developer_name.isdigit() or developer_name.lower() in {"for sale", "register interest"}):
        developer_name = None
    project_refs = re.findall(r"\d+", parts[-1])
    project_ref = project_refs[-1] if project_refs else ""
    images = [
        str(value) for value in record.get("images", [])
        if str(value).startswith(("http://", "https://")) and project_ref and f"/compound/{project_ref}/" in unquote(str(value))
    ]
    timestamp = datetime.fromisoformat(captured_at.replace("Z", "+00:00")) if captured_at else datetime.now(timezone.utc)
    return Listing(
        source_site="wasalt",
        source_id=parts[-1].lower(),
        source_url=url,
        record_type="project",
        name=name,
        description=description[:12000],
        description_lang="mixed" if re.search(r"[\u0600-\u06ff]", description) and re.search(r"[A-Za-z]", description) else "ar" if re.search(r"[\u0600-\u06ff]", description) else "en",
        developer_name=developer_name,
        property_category=category,
        status=status,
        location_country="Saudi Arabia",
        location_city=city,
        location_city_raw=location_line,
        location_area=area,
        price_amount=price,
        price_currency="SAR" if price is not None else None,
        price_display_text=f"{compact_display} SAR" if compact_display else None,
        listing_type="sale",
        area_sqm_min=area_min,
        area_sqm_max=area_max,
        bedrooms=bedrooms,
        bedrooms_min=bedrooms_min,
        bedrooms_max=bedrooms_max,
        bathrooms=max(bathroom_values) if bathroom_values else None,
        unit_types_raw=_before(lines, "Bedrooms"),
        unit_types_normalized=units,
        amenities=_section(lines, "Amenities", {"About Project", "Units Available", "Additional Information"})[:50],
        expected_completion_date=parse_date(completion_raw),
        expected_completion_raw=completion_raw,
        image_urls=list(dict.fromkeys(images))[:20],
        scraped_at=timestamp,
        updated_at=timestamp,
    )
