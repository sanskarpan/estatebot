import json

from backend.app.bootstrap import seed_if_empty
from backend.app.db.database import Database


def test_seed_bootstrap_loads_once(tmp_path):
    db = Database(tmp_path / "bootstrap.db")
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"generated_at": "2026-09-02T00:00:00Z", "listings": [{"source_site": "wasalt", "source_id": "seed-1", "source_url": "https://wasalt.sa/en/property/seed-1", "record_type": "sale_listing", "name": "Seed listing", "listing_type": "sale"}], "content_documents": []}))
    assert seed_if_empty(db, str(seed)) == 1
    assert seed_if_empty(db, str(seed)) == 0
    assert db.stats()["listings_total"] == 1
    assert db.meta("last_scrape_completed_at") == "2026-09-02T00:00:00Z"
