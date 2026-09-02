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


def test_deterministic_price_answer_is_explicit_when_unpublished():
    context = [RetrievedChunk("c1", "darglobal", "dg1", "https://darglobal.co.uk/dg1", "DG1", "structured", "DG1 is an apartment. Bedrooms: 1 to 3.", -1)]
    answer, citations = deterministic_answer("How much does DG1 cost?", context)
    assert "does not publish a price" in answer
    assert citations[0].source_id == "dg1"
