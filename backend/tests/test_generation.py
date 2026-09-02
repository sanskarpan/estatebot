import pytest

from backend.app.config import Settings
from backend.app.generation import openrouter
from backend.app.generation.openrouter import OpenRouterGenerator, deterministic_answer, verify_and_extract
from backend.app.retrieval.service import RetrievedChunk


def test_citations_are_limited_to_retrieved_context():
    context = [RetrievedChunk("c1", "darglobal", "dg1", "https://darglobal.co.uk/dg1", "DG1", "overview", "facts", -1)]
    answer, citations, valid = verify_and_extract("DG1 is an apartment [[id:dg1]]. Fake [[id:secret]].", context)
    assert "secret" not in answer
    assert [x.source_id for x in citations] == ["dg1"]
    assert valid is False


@pytest.mark.asyncio
async def test_openrouter_falls_back_after_primary_failure(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self.payload = payload or {}

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, headers, json, timeout):
            calls.append(json["model"])
            if len(calls) == 1:
                return FakeResponse(429)
            return FakeResponse(200, {"model": json["model"], "choices": [{"message": {"content": "Grounded [[id:dg1]]"}}]})

    monkeypatch.setattr(openrouter.httpx, "AsyncClient", FakeClient)
    settings = Settings(openrouter_api_key="test", openrouter_model_primary="primary:free", openrouter_model_fallback_1="fallback:free", openrouter_model_fallback_2=None)
    result = await OpenRouterGenerator(settings).generate("Where is DG1?", [RetrievedChunk("c1", "darglobal", "dg1", "https://darglobal.co.uk/dg1", "DG1", "overview", "Dubai", -1)], [])
    assert result.answer == "Grounded [[id:dg1]]"
    assert result.model_used == "fallback:free"
    assert calls == ["primary:free", "fallback:free"]


@pytest.mark.asyncio
async def test_preferred_model_is_tried_first_then_configured_fallback(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self.payload = payload or {}

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, headers, json, timeout):
            calls.append(json["model"])
            if json["model"] == "selected:free":
                return FakeResponse(429)
            return FakeResponse(200, {"model": json["model"], "choices": [{"message": {"content": "Grounded [[id:dg1]]"}}]})

    monkeypatch.setattr(openrouter.httpx, "AsyncClient", FakeClient)
    settings = Settings(
        openrouter_api_key="test",
        openrouter_model_primary="primary:free",
        openrouter_model_fallback_1="fallback:free",
        openrouter_model_fallback_2=None,
    )
    result = await OpenRouterGenerator(settings).generate(
        "Where is DG1?",
        [RetrievedChunk("c1", "darglobal", "dg1", "https://darglobal.co.uk/dg1", "DG1", "overview", "Dubai", -1)],
        [],
        preferred_model="selected:free",
    )
    assert result.model_used == "primary:free"
    assert calls == ["selected:free", "primary:free"]


def test_preferred_model_is_not_duplicated_in_fallback_order():
    settings = Settings(
        openrouter_api_key="test",
        openrouter_model_primary="primary:free",
        openrouter_model_fallback_1="fallback:free",
        openrouter_model_fallback_2=None,
    )
    assert OpenRouterGenerator(settings).ordered_models("fallback:free") == ["fallback:free", "primary:free"]


def test_deterministic_price_answer_is_explicit_when_unpublished():
    context = [RetrievedChunk("c1", "darglobal", "dg1", "https://darglobal.co.uk/dg1", "DG1", "structured", "DG1 is an apartment. Bedrooms: 1 to 3.", -1)]
    answer, citations = deterministic_answer("How much does DG1 cost?", context)
    assert "does not publish a price" in answer
    assert citations[0].source_id == "dg1"


def test_deterministic_document_answer_uses_content_disclaimer():
    context = [RetrievedChunk(
        "content-darglobal-about", "darglobal", "about", "https://darglobal.co.uk/about",
        "Discover DarGlobal", "company_info", "DarGlobal is a global real estate developer.", -1,
    )]
    answer, citations = deterministic_answer("Who is DarGlobal?", context)
    assert "last capture" in answer
    assert "Prices and availability" not in answer
    assert citations[0].source_id == "about"


def test_deterministic_listing_answer_summarizes_fields_without_raw_urls():
    context = [RetrievedChunk(
        "listing-1", "wasalt", "listing-1", "https://wasalt.sa/listing-1",
        "A compact Jeddah apartment", "structured",
        "A compact Jeddah apartment URL: https://wasalt.sa/listing-1 Location: Jeddah, Saudi Arabia. Category: apartment. Price: 1,700 /Year. Bedrooms: 1 Bedroom. Description: A very long scraped page.",
        -1,
    )]
    answer, citations = deterministic_answer("Show me homes in Jeddah", context)
    assert "Jeddah, Saudi Arabia · apartment · 1,700 /Year · 1 Bedroom" in answer
    assert "https://" not in answer
    assert citations[0].source_url == "https://wasalt.sa/listing-1"
