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
    wasalt_projects = [item for item in listings if item.source_site == "wasalt" and item.record_type == "project"]
    assert len(press) >= 15
    assert all(item.publish_date and item.source_url.startswith("https://darglobal.co.uk/press/") for item in press)
    assert len(wasalt_projects) == 32
    assert all(item.developer_name and item.price_amount and item.image_urls for item in wasalt_projects)
    assert payload["last_scrape_completed_at"]
    for item in listings:
        assert isinstance(item.image_urls, list)
        path = urlparse(item.source_url).path.lower().rstrip("/")
        if item.source_site == "wasalt":
            if item.record_type == "project":
                assert "/project/" in path
                project_ref = item.source_id.rsplit("-", 1)[-1]
                assert all(f"/compound/{project_ref}/" in url for url in item.image_urls)
            else:
                assert any(token in path for token in ("/property/", "/listing/", "/real-estate/"))


def test_overlong_chat_is_rejected(db, monkeypatch):
    from fastapi.testclient import TestClient
    import backend.app.main as main

    monkeypatch.setattr(main, "db", db)
    response = TestClient(main.app).post("/api/chat", json={"message": "x" * 2001})
    assert response.status_code == 400
