"""Conservative normalization helpers. Unknown values remain unknown."""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import date
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value).replace("\xa0", " ")
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def clean_lines(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = clean_text(raw)
        if value and value.lower() not in seen:
            out.append(value)
            seen.add(value.lower())
    return out


def canonical_url(base: str, href: str) -> str:
    absolute = urljoin(base, href.strip())
    parsed = urlparse(absolute)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not k.lower() in {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "ref", "source"}]
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path.rstrip("/") or "/", "", urlencode(query), ""))


def parse_price(text: str | None, default_currency: str | None = None) -> tuple[float | None, str | None, str | None]:
    raw = clean_text(text)
    if not raw:
        return None, None, None
    upper = raw.upper()
    currency = None
    if any(x in upper for x in ("SAR", "ر.س", "RIYAL", "ريال")):
        currency = "SAR"
    elif any(x in upper for x in ("AED", "د.إ", "DIRHAM")):
        currency = "AED"
    elif "USD" in upper or "$" in upper:
        currency = "USD"
    elif "GBP" in upper or "£" in upper:
        currency = "GBP"
    elif "EUR" in upper or "€" in upper:
        currency = "EUR"
    elif default_currency:
        currency = default_currency
    numbers = re.findall(r"(?:\d[\d,]*(?:\.\d+)?)", raw)
    if not numbers:
        return None, currency, raw
    try:
        amount = float(numbers[0].replace(",", ""))
    except ValueError:
        return None, currency, raw
    if amount <= 0:
        return None, currency, raw
    return amount, currency, raw


def parse_area_sqm(text: str | None) -> tuple[float | None, float | None]:
    raw = clean_text(text)
    if not raw:
        return None, None
    matches = re.findall(r"(?:\d[\d,]*(?:\.\d+)?)", raw)
    if not matches:
        return None, None
    values = []
    for value in matches[:2]:
        try:
            values.append(float(value.replace(",", "")))
        except ValueError:
            pass
    if not values:
        return None, None
    if any(x in raw.lower() for x in ("sqft", "sq ft", "square feet", "ft²")):
        values = [v * 0.092903 for v in values]
    return min(values), max(values)


def parse_bedrooms(text: str | None) -> tuple[str | None, int | None, int | None, list[str]]:
    raw = clean_text(text)
    if not raw:
        return None, None, None, []
    lower = raw.lower()
    numbers = [int(x) for x in re.findall(r"\d+", lower)]
    if "studio" in lower and not numbers:
        return raw, 0, 0, ["studio"]
    if not numbers:
        return raw, None, None, []
    lo, hi = (0 if "studio" in lower else min(numbers)), max(numbers)
    normalized: list[str] = []
    if "studio" in lower:
        normalized.append("studio")
    for n in range(lo, hi + 1):
        normalized.append({1: "1br", 2: "2br", 3: "3br", 4: "4br"}.get(n, "5br_plus"))
    return raw, lo, hi, list(dict.fromkeys(normalized))


CITY_ALIASES = {
    "riyadh": "Riyadh", "ar riyadh": "Riyadh", "jeddah": "Jeddah", "dammam": "Dammam",
    "khobar": "Khobar", "al khobar": "Khobar", "al-khobar": "Khobar", "mecca": "Mecca", "makkah": "Mecca",
    "medina": "Medina", "madinah": "Medina", "muscat": "Muscat", "dubai": "Dubai", "london": "London",
    "benahavis": "Benahavís", "benahavís": "Benahavís", "doha": "Doha", "jeddah city": "Jeddah",
}


COUNTRY_ALIASES = {
    "ksa": "Saudi Arabia", "saudi arabia": "Saudi Arabia", "saudi": "Saudi Arabia", "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates", "uk": "United Kingdom", "united kingdom": "United Kingdom",
    "oman": "Oman", "spain": "Spain", "maldives": "Maldives", "qatar": "Qatar",
}


def normalize_city(value: str | None) -> str | None:
    raw = clean_text(value)
    return CITY_ALIASES.get(raw.lower()) if raw else None


def normalize_country(value: str | None) -> str | None:
    raw = clean_text(value)
    return COUNTRY_ALIASES.get(raw.lower()) if raw else None


def parse_date(value: str | None) -> date | None:
    raw = clean_text(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y", "%B %Y", "%Y"):
        try:
            parsed = date.fromisoformat(raw) if fmt == "%Y-%m-%d" else __import__("datetime").datetime.strptime(raw, fmt).date()
            return parsed.replace(day=1) if fmt in {"%B %Y", "%Y"} else parsed
        except ValueError:
            continue
    return None
