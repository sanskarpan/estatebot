from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.db.database import Database
from backend.app.retrieval.planner import QueryPlan, plan_query, structured_search


@dataclass
class RetrievedChunk:
    chunk_id: str
    source_site: str
    source_id: str
    source_url: str
    name: str
    chunk_type: str
    text: str
    rank: float


@dataclass
class RetrievalResult:
    plan: QueryPlan
    structured: list[dict[str, Any]]
    chunks: list[RetrievedChunk]
    no_match_reason: str | None = None
    direct_answer: str | None = None


class RetrievalService:
    def __init__(self, db: Database, mode: str = "bm25_only", max_chunks: int = 8):
        self.db = db
        self.mode = mode
        self.max_chunks = max_chunks

    def retrieve(self, query: str, history: list[str] | None = None) -> RetrievalResult:
        plan = plan_query(self.db, query, history)
        overview_is_unfiltered = not any((
            plan.source_site, plan.record_type, plan.city, plan.country, plan.category,
            plan.listing_type, plan.bedrooms_min is not None, plan.bedrooms_max is not None,
            plan.min_price is not None, plan.max_price is not None,
        ))
        if plan.overview_intent and not plan.entity_source_id and overview_is_unfiltered:
            stats = self.db.stats()
            with self.db.connect() as conn:
                city_rows = conn.execute("SELECT location_city,COUNT(*) count FROM listings WHERE is_active=1 AND location_city IS NOT NULL GROUP BY location_city ORDER BY count DESC,location_city LIMIT 8").fetchall()
                type_rows = conn.execute("SELECT property_category,COUNT(*) count FROM listings WHERE is_active=1 AND property_category IS NOT NULL GROUP BY property_category ORDER BY count DESC,property_category").fetchall()
            cities = ", ".join(f"{row['location_city']} ({row['count']})" for row in city_rows)
            categories = ", ".join(f"{row['property_category']} ({row['count']})" for row in type_rows)
            answer = (
                f"The active scraped corpus contains **{stats['listings_total']} listings/projects**: "
                f"{stats['listings_darglobal']} from DarGlobal and {stats['listings_wasalt']} from Wasalt, plus "
                f"{stats['content_documents_total']} supporting documents. Leading cities are {cities or 'not published'}. "
                f"Property categories are {categories or 'not published'}. Ask me to narrow this by city, source, property type, bedrooms, or budget."
            )
            return RetrievalResult(plan, [], [], direct_answer=answer)
        if plan.unsupported_entity_mentioned:
            return RetrievalResult(plan, [], [], "; ".join(plan.notes))
        if plan.content_intent:
            rows = self.db.latest_content(plan.source_site, plan.content_type, self.max_chunks)
            chunks = [RetrievedChunk(
                f"content-{row['source_site']}-{row['source_id']}", row["source_site"], row["source_id"],
                row["source_url"], row["title"], row["content_type"],
                f"Published: {row['publish_date'] or 'date not published'}. {row['body_text'][:2200]}",
                -100.0 - index,
            ) for index, row in enumerate(rows)]
            if not chunks:
                return RetrievalResult(plan, [], [], "No active supporting documents matched the requested source and topic.")
            return RetrievalResult(plan, [], chunks, None)
        structured = structured_search(self.db, plan, self.max_chunks)
        if plan.structured_intent and not plan.location_recognized:
            return RetrievalResult(plan, [], [], "; ".join(plan.notes))
        if plan.structured_intent and not structured:
            return RetrievalResult(plan, [], [], "; ".join(plan.notes) or "No active records matched the requested criteria.")
        exact_keys = {(str(x["source_site"]), str(x["source_id"])) for x in structured}
        # Explicit filters must not be diluted by lexical matches from records
        # outside the structured candidate set. SQL is authoritative for source,
        # geography, category, numeric, named-entity, and comparison constraints.
        exact_only = bool(structured) and plan.structured_intent
        source_site = plan.source_site
        rows = self.db.search_chunks(query, self.max_chunks, source_site=source_site, source_keys=exact_keys if exact_only else None)
        chunks = [RetrievedChunk(r["chunk_id"], r["parent_source_site"], r["parent_source_id"], r["parent_source_url"], r["name"], r["chunk_type"], r["text"], float(r["rank"])) for r in rows]
        # For explicit structured filters, preserve all exact matches in SQL order
        # even when lexical wording differs or the FTS rank is misleading.
        structured_chunks = [RetrievedChunk(f"structured-{item['source_site']}-{item['source_id']}", item["source_site"], item["source_id"], item["source_url"], item["name"], "structured", self._structured_text(item), -100.0 - index) for index, item in enumerate(structured)]
        if structured_chunks:
            structured_keys = {(item.source_site, item.source_id) for item in structured_chunks}
            chunks = structured_chunks + [chunk for chunk in chunks if (chunk.source_site, chunk.source_id) not in structured_keys]
        else:
            unique_chunks: list[RetrievedChunk] = []
            unique_keys: set[tuple[str, str]] = set()
            for chunk in chunks:
                key = (chunk.source_site, chunk.source_id)
                if key not in unique_keys:
                    unique_chunks.append(chunk)
                    unique_keys.add(key)
            chunks = unique_chunks
        if not chunks:
            return RetrievalResult(
                plan,
                [],
                [],
                "I couldn't find a relevant match in the active DarGlobal and Wasalt data. Try a project, covered location, property type, or budget.",
            )
        return RetrievalResult(plan, structured, chunks[: self.max_chunks], None)

    @staticmethod
    def _structured_text(item: dict[str, Any]) -> str:
        facts = [f"{item['name']} ({item['source_site']})", f"URL: {item['source_url']}"]
        location = ", ".join(x for x in [item.get("location_area"), item.get("location_city"), item.get("location_country")] if x)
        if location: facts.append(f"Location: {location}.")
        if item.get("property_category"): facts.append(f"Category: {item['property_category']}.")
        if item.get("price_display_text") or item.get("price_amount"):
            price = item.get("price_display_text") or f"{item['price_amount']} {item.get('price_currency') or ''}"
            currency = item.get("price_currency")
            if currency and currency.lower() not in str(price).lower():
                price = f"{price} {currency}"
            facts.append(f"Price: {price}.")
        if item.get("bedrooms") is not None: facts.append(f"Bedrooms: {item['bedrooms']}.")
        if item.get("description"): facts.append(f"Description: {item['description']}")
        if not item.get("is_active", True): facts.append("Listing status: inactive at the last scrape; treat these details as historical.")
        return " ".join(facts)
