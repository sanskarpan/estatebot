"""Deterministic query planning for the fields where semantic search is unsafe."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.app.db.database import Database, row_to_listing
from scraper.common.normalize import parse_price


@dataclass
class QueryPlan:
    source_site: str | None = None
    city: str | None = None
    country: str | None = None
    category: str | None = None
    listing_type: str | None = None
    bedrooms_min: int | None = None
    bedrooms_max: int | None = None
    min_price: float | None = None
    max_price: float | None = None
    currency: str | None = None
    order: str | None = None
    limit: int = 5
    structured_intent: bool = False
    entity_source_site: str | None = None
    entity_source_id: str | None = None
    entity_name: str | None = None
    cross_source: bool = False
    content_intent: bool = False
    location_mentioned: str | None = None
    location_recognized: bool = True
    notes: list[str] = field(default_factory=list)


def _known_locations(db: Database) -> tuple[dict[str, str], dict[str, str]]:
    with db.connect() as conn:
        cities = [r[0] for r in conn.execute("SELECT DISTINCT location_city FROM listings WHERE location_city IS NOT NULL").fetchall()]
        countries = [r[0] for r in conn.execute("SELECT DISTINCT location_country FROM listings WHERE location_country IS NOT NULL").fetchall()]
    return ({str(x).lower(): str(x) for x in cities}, {str(x).lower(): str(x) for x in countries})


def _normalized_phrase(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _resolve_entity(db: Database, text: str) -> tuple[str, str, str] | None:
    haystack = f" {_normalized_phrase(text)} "
    matches: list[tuple[int, str, str, str]] = []
    with db.connect() as conn:
        rows = conn.execute("SELECT source_site,source_id,name FROM listings WHERE is_active=1").fetchall()
    for row in rows:
        source_phrase = _normalized_phrase(str(row["source_id"]).replace("--", " ").replace("-", " "))
        name_phrase = _normalized_phrase(str(row["name"]))
        aliases = {source_phrase, name_phrase, name_phrase.split(" interiors by ", 1)[0], name_phrase.split(" design inspired ", 1)[0]}
        aliases |= {alias.removeprefix("the ") for alias in aliases}
        aliases = {alias for alias in aliases if len(alias) >= 3 and alias not in {"property", "project", "apartment", "villa", "residences"}}
        matched = max((len(alias) for alias in aliases if f" {alias} " in haystack), default=0)
        if matched:
            matches.append((matched, str(row["source_site"]), str(row["source_id"]), str(row["name"])))
    if not matches:
        return None
    matches.sort(reverse=True)
    top_score = matches[0][0]
    top = {(site, source_id, name) for score, site, source_id, name in matches if score == top_score}
    return next(iter(top)) if len(top) == 1 else None


def _number_amount(value: str, query: str) -> tuple[float | None, str | None]:
    amount, currency, _ = parse_price(value, "SAR" if "sar" in query.lower() or "riyal" in query.lower() else None)
    if amount is None:
        return None, currency
    lower = query.lower()
    if "million" in lower or re.search(r"\b[0-9]+(?:\.[0-9]+)?m\b", lower):
        amount *= 1_000_000
    elif "thousand" in lower or re.search(r"\b[0-9]+(?:\.[0-9]+)?k\b", lower):
        amount *= 1_000
    return amount, currency


def plan_query(db: Database, query: str, history: list[str] | None = None) -> QueryPlan:
    raw = query.strip()
    lower = raw.lower()
    plan = QueryPlan()
    known_cities, known_countries = _known_locations(db)
    effective = " ".join((history or [])[-2:] + [raw])
    effective_lower = effective.lower()

    if re.search(r"\b(?:news|press release|press releases|announcement|announcements|announced)\b|what(?:'s| is) new", effective_lower):
        plan.content_intent = True

    mentions_darglobal = "darglobal" in effective_lower or "dar global" in effective_lower
    mentions_wasalt = "wasalt" in effective_lower
    if mentions_darglobal and mentions_wasalt:
        plan.cross_source = True
        plan.structured_intent = True
    elif mentions_darglobal:
        plan.source_site = "darglobal"
        plan.structured_intent = True
    elif mentions_wasalt:
        plan.source_site = "wasalt"
        plan.structured_intent = True

    entity = _resolve_entity(db, effective)
    if entity:
        plan.entity_source_site, plan.entity_source_id, plan.entity_name = entity
        if not plan.cross_source:
            plan.source_site = plan.entity_source_site
        plan.structured_intent = True

    for alias, city in {**known_cities, "al-khobar": "Khobar", "makkah": "Mecca", "madinah": "Medina"}.items():
        if re.search(rf"\b{re.escape(alias)}\b", effective_lower):
            plan.city = city
            plan.location_mentioned = alias
            plan.location_recognized = True
            plan.structured_intent = True
            break
    if not plan.city:
        for alias, country in known_countries.items():
            if re.search(rf"\b{re.escape(alias)}\b", effective_lower):
                plan.country = country
                plan.location_mentioned = alias
                plan.location_recognized = True
                plan.structured_intent = True
                break
    # Explicit geography not in the corpus must not be silently discarded.
    if not plan.city and not plan.country:
        match = re.search(r"\b(?:in|at|near|around)\s+([A-Za-z][A-Za-z -]{2,35})", lower)
        if match:
            candidate = re.split(r"\b(?:under|below|with|for|that|and|or)\b", match.group(1))[0].strip(" .,?")
            if candidate and len(candidate.split()) <= 4:
                plan.location_mentioned = candidate
                plan.location_recognized = False
                plan.structured_intent = True
                plan.notes.append(f"Location '{candidate}' is not covered by the active corpus.")

    category_words = {"villa": "villa", "villas": "villa", "apartment": "apartment", "apartments": "apartment", "flat": "apartment", "flats": "apartment", "land": "land", "plot": "land", "plots": "land", "commercial": "commercial", "hotel": "hotel_room"}
    for word, category in category_words.items():
        if re.search(rf"\b{word}\b", effective_lower):
            plan.category = category
            plan.structured_intent = True
            break
    if re.search(r"\b(?:rent|rental|for lease|lease)\b", effective_lower):
        plan.listing_type = "rent"; plan.structured_intent = True
    elif re.search(r"\b(?:sale|sell|buy|buying|for sale)\b", effective_lower):
        plan.listing_type = "sale"; plan.structured_intent = True

    bedroom = re.search(r"\b(\d+)\s*[- ]?\s*(?:bed(?:room)?s?|br)\b", effective_lower)
    if bedroom:
        count = int(bedroom.group(1)); plan.bedrooms_min = count; plan.bedrooms_max = count; plan.structured_intent = True
    if "studio" in effective_lower:
        plan.bedrooms_min = 0; plan.bedrooms_max = 0; plan.structured_intent = True
    if re.search(r"\b(?:more than|at least|minimum of)\s*(\d+)\s*(?:bed|bedroom|br)", effective_lower):
        count = int(re.search(r"\b(?:more than|at least|minimum of)\s*(\d+)", effective_lower).group(1)); plan.bedrooms_min = count + (1 if "more than" in effective_lower else 0); plan.bedrooms_max = None

    nums = re.findall(r"(?:\$|aed|sar|usd|gbp|eur|qar|omr|riyal|dirham)?\s*\d[\d,]*(?:\.\d+)?\s*(?:million|m|thousand|k)?", effective_lower)
    if nums:
        parsed = [_number_amount(x, effective_lower)[0] for x in nums]
        parsed = [x for x in parsed if x]
        currency = next((_number_amount(x, effective_lower)[1] for x in nums if _number_amount(x, effective_lower)[0]), None)
        plan.currency = currency
        if len(parsed) >= 2 and re.search(r"\bbetween\b|\bfrom\b.*\bto\b", effective_lower):
            plan.min_price, plan.max_price = min(parsed[0], parsed[1]), max(parsed[0], parsed[1])
        elif re.search(r"\b(?:under|below|less than|up to|max(?:imum)?|budget)\b", effective_lower):
            plan.max_price = parsed[0]
        elif re.search(r"\b(?:over|above|more than|at least|minimum)\b", effective_lower):
            plan.min_price = parsed[0]
        else:
            plan.max_price = parsed[0] if any(x in effective_lower for x in ("budget", "cheapest")) else None
        plan.structured_intent = True
    if re.search(r"\b(?:cheapest|lowest|least expensive|most affordable)\b", effective_lower):
        plan.order = "asc"; plan.structured_intent = True
    elif re.search(r"\b(?:most expensive|highest priced|priciest)\b", effective_lower):
        plan.order = "desc"; plan.structured_intent = True
    return plan


def structured_search(db: Database, plan: QueryPlan, limit: int = 5) -> list[dict[str, Any]]:
    if plan.content_intent or not plan.structured_intent or not plan.location_recognized:
        return []
    if plan.entity_source_site and plan.entity_source_id:
        with db.connect() as conn:
            entity = conn.execute("SELECT * FROM listings WHERE is_active=1 AND source_site=? AND source_id=?", [plan.entity_source_site, plan.entity_source_id]).fetchone()
        output = [row_to_listing(entity)] if entity else []
        if not plan.cross_source or len(output) >= limit:
            return output
        clauses = ["is_active=1", "source_site=?"]
        params: list[Any] = ["wasalt" if plan.entity_source_site == "darglobal" else "darglobal"]
        if plan.city: clauses.append("location_city=?"); params.append(plan.city)
        if plan.country: clauses.append("location_country=?"); params.append(plan.country)
        if plan.category: clauses.append("property_category=?"); params.append(plan.category)
        if plan.listing_type: clauses.append("listing_type=?"); params.append(plan.listing_type)
        if plan.bedrooms_min is not None: clauses.append("bedrooms_max>=?"); params.append(plan.bedrooms_min)
        if plan.bedrooms_max is not None: clauses.append("bedrooms_min<=?"); params.append(plan.bedrooms_max)
        if plan.min_price is not None: clauses.append("price_amount>=?"); params.append(plan.min_price)
        if plan.max_price is not None: clauses.append("price_amount<=?"); params.append(plan.max_price)
        order = "price_amount ASC" if plan.order == "asc" else "price_amount DESC" if plan.order == "desc" else "updated_at DESC"
        with db.connect() as conn:
            rows = conn.execute(f"SELECT * FROM listings WHERE {' AND '.join(clauses)} ORDER BY {order} LIMIT ?", [*params, limit - len(output)]).fetchall()
        return output + [row_to_listing(row) for row in rows]
    clauses = ["is_active=1"]
    params: list[Any] = []
    if plan.source_site: clauses.append("source_site=?"); params.append(plan.source_site)
    if plan.city: clauses.append("location_city=?"); params.append(plan.city)
    if plan.country: clauses.append("location_country=?"); params.append(plan.country)
    if plan.category: clauses.append("property_category=?"); params.append(plan.category)
    if plan.listing_type: clauses.append("listing_type=?"); params.append(plan.listing_type)
    if plan.bedrooms_min is not None: clauses.append("bedrooms_max>=?"); params.append(plan.bedrooms_min)
    if plan.bedrooms_max is not None: clauses.append("bedrooms_min<=?"); params.append(plan.bedrooms_max)
    if plan.min_price is not None: clauses.append("price_amount>=?"); params.append(plan.min_price)
    if plan.max_price is not None: clauses.append("price_amount<=?"); params.append(plan.max_price)
    if plan.currency: clauses.append("(price_currency=? OR price_currency IS NULL)"); params.append(plan.currency)
    if plan.order in {"asc", "desc"}:
        clauses.append("price_amount IS NOT NULL")
    order = "price_amount ASC" if plan.order == "asc" else "price_amount DESC" if plan.order == "desc" else "updated_at DESC"
    with db.connect() as conn:
        rows = conn.execute(f"SELECT * FROM listings WHERE {' AND '.join(clauses)} ORDER BY {order} LIMIT ?", [*params, limit]).fetchall()
    return [row_to_listing(row) for row in rows]
