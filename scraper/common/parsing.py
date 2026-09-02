from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scraper.common.normalize import clean_lines, clean_text, parse_area_sqm, parse_bedrooms, parse_date, parse_price


def soup_for(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    records = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.get_text())
            if isinstance(value, list): records.extend(x for x in value if isinstance(x, dict))
            elif isinstance(value, dict): records.append(value)
        except (ValueError, TypeError):
            continue
    return records


def meta(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return None


def title(soup: BeautifulSoup, fallback: str = "") -> str:
    h1 = soup.find("h1")
    value = clean_text(h1.get_text(" ", strip=True)) if h1 else None
    return value or meta(soup, "og:title", "twitter:title") or clean_text(soup.title.get_text(" ", strip=True) if soup.title else None) or fallback or "Untitled property"


def body_text(soup: BeautifulSoup) -> str:
    copy = BeautifulSoup(str(soup), "lxml")
    for tag in copy(["script", "style", "noscript", "svg", "nav", "header", "footer", "form"]):
        tag.decompose()
    return clean_text(copy.get_text(" ", strip=True)) or ""


def images(soup: BeautifulSoup, base_url: str) -> list[str]:
    from urllib.parse import urljoin
    urls = []
    for tag in soup.select("img[src], source[srcset]"):
        raw = tag.get("src") or tag.get("srcset", "").split(",")[0].split(" ")[0]
        if raw and not raw.startswith("data:"):
            urls.append(urljoin(base_url, raw))
    return list(dict.fromkeys(urls))[:30]


def infer_category(text: str) -> str | None:
    lower = text.lower()
    if re.search(r"\bvillas?\b", lower): return "villa"
    if re.search(r"\bapartments?\b|\bflats?\b|\bfloors?\b", lower): return "apartment"
    if re.search(r"\bhotel rooms?\b|\bhotel\b", lower): return "hotel_room"
    if re.search(r"\bplots?\b|\bland\b", lower): return "land"
    if "commercial" in lower: return "commercial"
    return None


def infer_location(text: str) -> tuple[str | None, str | None, str | None, str | None]:
    countries = ["United Arab Emirates", "UAE", "Saudi Arabia", "KSA", "Oman", "Spain", "United Kingdom", "UK", "Maldives", "Qatar"]
    country = next((x for x in countries if re.search(rf"\b{re.escape(x)}\b", text, re.I)), None)
    country_norm = {"UAE": "United Arab Emirates", "KSA": "Saudi Arabia", "UK": "United Kingdom"}.get(country or "", country)
    cities = ["Dubai", "Riyadh", "Jeddah", "Dammam", "Khobar", "Muscat", "London", "Doha", "Benahavís"]
    city = next((x for x in cities if re.search(rf"\b{re.escape(x)}\b", text, re.I)), None)
    area = None
    for marker in ("Business Bay", "Al Marjan Island", "Wadi Safar", "AIDA", "Amaya", "Rayana", "Noonu Atoll"):
        if re.search(rf"\b{re.escape(marker)}\b", text, re.I): area = marker; break
    masterplan = next((x for x in ("AIDA", "Amaya", "Rayana", "Wadi Safar") if re.search(rf"\b{re.escape(x)}\b", text, re.I)), None)
    return city, country_norm, area, masterplan


def extract_facts(soup: BeautifulSoup, url: str, default_currency: str | None = None) -> dict[str, Any]:
    text = body_text(soup)
    item_title = title(soup, urlparse(url).path.rsplit("/", 1)[-1])
    city, country, area, masterplan = infer_location(text)
    price_text = None
    for selector in ("[class*=price]", "[id*=price]", "meta[property='product:price:amount']"):
        tag = soup.select_one(selector)
        if tag:
            price_text = tag.get("content") or tag.get_text(" ", strip=True); break
    if not price_text:
        price_match = re.search(r"[\d,]+(?:\.\d+)?\s*(?:SAR|AED|USD|GBP|EUR|OMR|QAR|\$|£|€)|(?:SAR|AED|USD|GBP|EUR|OMR|QAR|\$|£|€)\s*[\d,]+(?:\.\d+)?", text, re.I)
        price_text = price_match.group(0) if price_match else None
    amount, currency, display = parse_price(price_text, default_currency)
    bedroom_text = None
    bedroom_match = re.search(r"\b\d+\s*(?:[-–]\s*\d+)?\s*(?:bed(?:room)?s?|br)\b", text, re.I)
    if bedroom_match:
        bedroom_text = bedroom_match.group(0)
        if re.search(r"studio", text[max(0, bedroom_match.start() - 60):bedroom_match.start()], re.I):
            bedroom_text = "studio " + bedroom_text
    elif re.search(r"\bstudios?\b", text, re.I):
        bedroom_text = "studio"
    bedrooms, bedrooms_min, bedrooms_max, units = parse_bedrooms(bedroom_text)
    area_match = re.search(r"[\d,]+(?:\.\d+)?\s*(?:-|–|to)\s*[\d,]+(?:\.\d+)?\s*(?:sqm|m2|m²|sqft|sq ft|square metres?|square feet)?|[\d,]+(?:\.\d+)?\s*(?:sqm|m2|m²|sqft|sq ft|square metres?|square feet)", text, re.I)
    area_min, area_max = parse_area_sqm(area_match.group(0) if area_match else None)
    completion_raw = None
    completion_match = re.search(r"(?:completion|handover|ready)\D{0,20}(Q[1-4]\s+)?20\d{2}|(?:Q[1-4]\s+20\d{2})", text, re.I)
    if completion_match: completion_raw = clean_text(completion_match.group(0))
    bathroom_match = re.search(r"\b(\d+)\s*(?:bath(?:room)?s?)\b", text, re.I)
    bathrooms = int(bathroom_match.group(1)) if bathroom_match else None
    lang = "ar" if re.search(r"[\u0600-\u06ff]", text) and not re.search(r"[A-Za-z]", text) else "mixed" if re.search(r"[\u0600-\u06ff]", text) else "en"
    category = infer_category(item_title) or infer_category(text[:2000])
    return {"name": item_title, "description": text[:12000] or None, "description_lang": lang, "property_category": category, "location_city": city, "location_country": country, "location_area": area, "masterplan_name": masterplan, "price_amount": amount, "price_currency": currency, "price_display_text": display, "bedrooms": bedrooms, "bedrooms_min": bedrooms_min, "bedrooms_max": bedrooms_max, "bathrooms": bathrooms, "unit_types_normalized": units, "unit_types_raw": bedroom_text, "area_sqm_min": area_min, "area_sqm_max": area_max, "expected_completion_raw": completion_raw, "expected_completion_date": parse_date(completion_raw), "image_urls": images(soup, url), "status": next((x for x in ("Under Development", "Off-plan", "Ready", "For Sale", "For Rent") if x.lower() in text.lower()), None)}
