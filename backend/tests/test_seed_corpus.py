import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from backend.app.models.schema import ContentDocument, Listing


def test_checked_in_seed_is_valid_and_covers_both_sources():
    payload = json.loads(Path("data/seed_corpus.json").read_text(encoding="utf-8"))
    listings = [Listing.model_validate(item) for item in payload["listings"]]
    documents = [ContentDocument.model_validate(item) for item in payload["content_documents"]]
    counts = Counter(item.source_site for item in listings)
    keys = {(item.source_site, item.source_id) for item in listings}
    assert len(keys) == len(listings)
    assert counts["darglobal"] >= 30
    assert counts["wasalt"] >= 150
    assert len(documents) >= 3
    press = [item for item in documents if item.source_site == "darglobal" and item.content_type == "press_release"]
    assert len(press) >= 15
    assert all(item.publish_date and item.source_url.startswith("https://darglobal.co.uk/press/") for item in press)
    assert payload["last_scrape_completed_at"]
    for item in listings:
        path = urlparse(item.source_url).path.lower().rstrip("/")
        if item.source_site == "wasalt":
            assert any(token in path for token in ("/property/", "/listing/", "/real-estate/"))


def test_overlong_chat_is_rejected(db, monkeypatch):
    from fastapi.testclient import TestClient
    import backend.app.main as main

    monkeypatch.setattr(main, "db", db)
    response = TestClient(main.app).post("/api/chat", json={"message": "x" * 2001})
    assert response.status_code == 400
