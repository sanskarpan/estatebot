from fastapi.testclient import TestClient

import backend.app.main as main
from backend.app.retrieval.service import RetrievalService


def test_stats_and_citation_endpoint(db, monkeypatch):
    monkeypatch.setattr(main, "db", db)
    monkeypatch.setattr(main, "retrieval", RetrievalService(db, "bm25_only", 8))
    client = TestClient(main.app)
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert response.json()["listings_total"] == 3
    assert client.get("/api/listings/darglobal/dg1").status_code == 200
    assert client.get("/api/listings/darglobal/unknown").status_code == 404


def test_listing_search_returns_filtered_page(db, monkeypatch):
    monkeypatch.setattr(main, "db", db)
    client = TestClient(main.app)
    response = client.get("/api/listings/search", params={"city": "Riyadh", "listing_type": "rent", "bedrooms_min": 2, "limit": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["results"][0]["source_id"] == "riyadh-rent"


def test_inactive_listing_is_410(db, monkeypatch):
    from backend.app.models.schema import Listing
    db.upsert_listing(Listing(source_site="darglobal", source_id="gone", source_url="https://darglobal.co.uk/gone", record_type="project", name="Gone Project", is_active=False))
    monkeypatch.setattr(main, "db", db)
    client = TestClient(main.app)
    assert client.get("/api/listings/darglobal/gone").status_code == 410


def test_chat_deterministic_mode(db, monkeypatch):
    monkeypatch.setattr(main, "db", db)
    monkeypatch.setattr(main, "retrieval", RetrievalService(db, "bm25_only", 8))
    monkeypatch.setattr(main.settings, "openrouter_api_key", None)
    client = TestClient(main.app)
    response = client.post("/api/chat", json={"message": "What is in Jeddah?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["citations"]


def test_empty_chat_is_400(db, monkeypatch):
    monkeypatch.setattr(main, "db", db)
    client = TestClient(main.app)
    assert client.post("/api/chat", json={"message": "  "}).status_code == 400


def test_chat_rate_limit_returns_retry_after(db, monkeypatch):
    monkeypatch.setattr(main, "db", db)
    monkeypatch.setattr(main.settings, "chat_rate_limit_requests", 1)
    main.rate_buckets.clear()
    client = TestClient(main.app)
    assert client.post("/api/chat", json={"message": "What is in Jeddah?"}).status_code == 200
    response = client.post("/api/chat", json={"message": "What is in Riyadh?"})
    assert response.status_code == 429
    assert response.headers["Retry-After"]
    main.rate_buckets.clear()


def test_static_frontend_is_served(db, monkeypatch):
    monkeypatch.setattr(main, "db", db)
    client = TestClient(main.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "EstateBot" in response.text


def test_chat_sse_emits_verified_answer(db, monkeypatch):
    monkeypatch.setattr(main, "db", db)
    monkeypatch.setattr(main, "retrieval", RetrievalService(db, "bm25_only", 8))
    monkeypatch.setattr(main.settings, "openrouter_api_key", None)
    client = TestClient(main.app)
    response = client.post("/api/chat", headers={"Accept": "text/event-stream"}, json={"message": "What is in Jeddah?"})
    assert response.status_code == 200
    assert "event: token" in response.text
    assert "event: done" in response.text


def test_unhandled_errors_return_safe_json():
    path = "/api/test-unhandled-error"
    if not any(getattr(route, "path", None) == path for route in main.app.routes):
        @main.app.get(path)
        def _raise_for_test():
            raise RuntimeError("sensitive implementation detail")

    response = TestClient(main.app, raise_server_exceptions=False).get(path)
    assert response.status_code == 500
    assert response.json() == {"error": "internal_error", "message": "The service could not complete this request."}
    assert "sensitive" not in response.text.lower()
