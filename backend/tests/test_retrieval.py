from backend.app.retrieval.planner import plan_query, structured_search
from backend.app.retrieval.service import RetrievalService
from backend.app.models.schema import ContentDocument, Listing
from ingestion.build_index import build_index


def test_structured_cheapest_query(db):
    plan = plan_query(db, "What is the cheapest property in Jeddah?")
    assert plan.city == "Jeddah"
    assert plan.order == "asc"
    results = structured_search(db, plan)
    assert results[0]["name"] == "Jeddah Family Villa"


def test_structured_results_keep_sql_order(db):
    db.upsert_listing(Listing(
        source_site="wasalt", source_id="jeddah-cheaper", source_url="https://wasalt.sa/en/property/jeddah-cheaper",
        record_type="sale_listing", name="Jeddah Smaller Villa", property_category="villa", listing_type="sale",
        location_city="Jeddah", location_country="Saudi Arabia", bedrooms="2", bedrooms_min=2, bedrooms_max=2,
        price_amount=900000, price_currency="SAR", description="A smaller villa in Jeddah."
    ))
    result = RetrievalService(db).retrieve("What is the cheapest property in Jeddah?")
    assert [chunk.source_id for chunk in result.chunks[:2]] == ["jeddah-cheaper", "jeddah-1"]


def test_unknown_city_is_not_dropped(db):
    result = RetrievalService(db).retrieve("Are there villas in Paris?")
    assert result.no_match_reason
    assert "Paris" in result.no_match_reason or "paris" in result.no_match_reason


def test_vectorish_fts_query(db):
    result = RetrievalService(db).retrieve("sky garden amenity")
    assert result.chunks
    assert result.chunks[0].source_id == "dg1"


def test_named_entity_query_is_not_diluted_by_generic_filters(db):
    result = RetrievalService(db).retrieve("How much does a 2-bedroom apartment in DG1 cost?")
    assert result.plan.entity_source_id == "dg1"
    assert result.chunks[0].source_id == "dg1"


def test_cross_source_comparison_keeps_both_sides(db):
    result = RetrievalService(db).retrieve("Compare DarGlobal's DG1 project with Wasalt apartments in Riyadh.")
    assert result.plan.cross_source is True
    assert [chunk.source_id for chunk in result.chunks[:2]] == ["dg1", "riyadh-rent"]


def test_latest_news_routes_to_press_documents_in_date_order(db):
    for source_id, published in (("press/older", "2026-01-01"), ("press/newer", "2026-08-06")):
        db.upsert_content(ContentDocument(
            source_site="darglobal", source_id=source_id,
            source_url=f"https://darglobal.co.uk/{source_id}", content_type="press_release",
            title=source_id.rsplit("/", 1)[-1].title(), publish_date=published,
            body_text=f"DarGlobal public announcement dated {published}.",
        ))
    build_index(db)
    result = RetrievalService(db).retrieve("What is the latest DarGlobal news?")
    assert result.plan.content_intent is True
    assert [chunk.source_id for chunk in result.chunks[:2]] == ["press/newer", "press/older"]
    assert all(chunk.chunk_type == "press_release" for chunk in result.chunks)
