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


def test_unsupported_developer_does_not_receive_unrelated_citations(db):
    result = RetrievalService(db).retrieve("What Emaar Beachfront properties are available?")
    assert result.no_match_reason
    assert "Emaar" in result.no_match_reason
    assert result.chunks == []


def test_competitor_comparison_stays_inside_the_corpus_boundary(db):
    result = RetrievalService(db).retrieve("Is DarGlobal better than Damac?")
    assert result.no_match_reason
    assert "Damac" in result.no_match_reason
    assert result.chunks == []


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


def test_company_question_routes_to_company_documents(db):
    db.upsert_content(ContentDocument(
        source_site="darglobal", source_id="about", source_url="https://darglobal.co.uk/about",
        content_type="company_info", title="Discover DarGlobal", body_text="DarGlobal is a luxury real estate developer.",
    ))
    build_index(db)
    result = RetrievalService(db).retrieve("Who is DarGlobal as a company?")
    assert result.plan.content_type == "company_info"
    assert result.chunks[0].source_id == "about"
    assert result.chunks[0].chunk_type == "company_info"


def test_directly_named_inactive_record_is_returned_with_stale_caveat(db):
    db.upsert_listing(Listing(
        source_site="darglobal", source_id="retired-tower", source_url="https://darglobal.co.uk/retired-tower",
        record_type="project", name="Retired Tower", property_category="apartment", is_active=False,
    ))
    result = RetrievalService(db).retrieve("Tell me about Retired Tower")
    assert result.plan.entity_is_active is False
    assert result.chunks[0].source_id == "retired-tower"
    assert "inactive at the last scrape" in result.chunks[0].text


def test_extremely_broad_query_returns_bounded_corpus_overview(db):
    result = RetrievalService(db).retrieve("Tell me about everything you have")
    assert result.direct_answer
    assert "3 listings/projects" in result.direct_answer
    assert "narrow this" in result.direct_answer


def test_overview_wording_does_not_discard_explicit_filters(db):
    result = RetrievalService(db).retrieve("What do you have in Riyadh?")
    assert result.direct_answer is None
    assert result.structured
    assert all(item["location_city"] == "Riyadh" for item in result.structured)


def test_unspecified_source_results_include_darglobal_and_wasalt(db):
    result = RetrievalService(db).retrieve("What apartments are available?")
    assert {item.source_site for item in result.chunks} == {"darglobal", "wasalt"}


def test_explicit_cross_source_query_balances_both_corpora(db):
    result = RetrievalService(db).retrieve("Compare DarGlobal and Wasalt properties")
    assert result.plan.cross_source is True
    assert {item.source_site for item in result.chunks} == {"darglobal", "wasalt"}


def test_equal_cheapest_prices_are_both_returned(db):
    db.upsert_listing(Listing(
        source_site="wasalt", source_id="jeddah-tie", source_url="https://wasalt.sa/en/property/jeddah-tie",
        record_type="sale_listing", name="Jeddah Tie Villa", property_category="villa", listing_type="sale",
        location_city="Jeddah", price_amount=1250000, price_currency="SAR",
    ))
    result = structured_search(db, plan_query(db, "cheapest villa in Jeddah"), 5)
    assert {item["source_id"] for item in result[:2]} == {"jeddah-1", "jeddah-tie"}


def test_explicit_wasalt_projects_excludes_individual_listings(db):
    db.upsert_listing(Listing(
        source_site="wasalt", source_id="project-1", source_url="https://wasalt.sa/en/project/Riyadh/project-1",
        record_type="project", name="Project One", location_country="Saudi Arabia", location_city="Riyadh",
        listing_type="sale", property_category="villa",
    ))
    result = RetrievalService(db).retrieve("What projects does Wasalt have in Riyadh?")
    assert result.plan.record_type == "project"
    assert [item["source_id"] for item in result.structured] == ["project-1"]


def test_self_contained_turn_does_not_inherit_unrelated_history(db):
    plan = plan_query(db, "What properties are available in Jeddah?", ["Show me villas in Riyadh"])
    assert plan.city == "Jeddah"
    plan = plan_query(db, "Show me apartments", ["Show me villas in Riyadh"])
    assert plan.city is None
    assert plan.category == "apartment"


def test_referential_follow_up_can_inherit_history(db):
    plan = plan_query(db, "What about 2-bedroom homes there?", ["Show me properties in Riyadh"])
    assert plan.city == "Riyadh"
    assert plan.bedrooms_min == 2

    latest = plan_query(
        db,
        "What about 2-bedroom homes there?",
        ["Show me properties in Riyadh", "Show me apartments in Jeddah"],
    )
    assert latest.city == "Jeddah"


def test_source_typo_is_resolved_and_unknown_source_is_not_silently_ignored(db):
    assert plan_query(db, "List projects from Dargloabl").source_site == "darglobal"
    unknown = RetrievalService(db).retrieve("List projects from dware")
    assert unknown.chunks == []
    assert "couldn't identify 'dware'" in (unknown.no_match_reason or "")

    property_type_unknown = RetrievalService(db).retrieve("Show me villas from madeuphomes")
    assert property_type_unknown.chunks == []
    assert "couldn't identify 'madeuphomes'" in (property_type_unknown.no_match_reason or "")


def test_generic_cross_source_language_is_not_treated_as_an_unknown_provider(db):
    villas = RetrievalService(db).retrieve("Show villas from both sources")
    assert villas.plan.cross_source is True
    assert villas.no_match_reason is None
    assert villas.chunks

    apartments = RetrievalService(db).retrieve("Compare apartments from all providers")
    assert apartments.plan.cross_source is True
    assert apartments.no_match_reason is None


def test_number_without_price_language_does_not_activate_unfiltered_structured_results(db):
    result = RetrievalService(db).retrieve("asdf qwer 987")
    assert result.structured == []
    assert result.chunks == []


def test_currency_suffix_is_parsed_as_a_filter(db):
    plan = plan_query(db, "Show properties under 2 million AED")
    assert plan.max_price == 2_000_000
    assert plan.currency == "AED"
    result = RetrievalService(db).retrieve("Show properties under 2 million AED")
    assert all(item.get("price_currency") in {"AED", None} for item in result.structured)
    assert not any(chunk.source_site == "wasalt" for chunk in result.chunks)


def test_structured_chunk_never_drops_known_currency(db):
    result = RetrievalService(db).retrieve("What is the cheapest villa in Jeddah?")
    assert result.chunks
    assert "SAR" in result.chunks[0].text
