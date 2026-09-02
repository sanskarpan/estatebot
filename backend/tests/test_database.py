from backend.app.models.schema import Listing


def test_composite_source_identity(db):
    db.upsert_listing(Listing(source_site="darglobal", source_id="same", source_url="https://darglobal.co.uk/same", record_type="project", name="DG Same"))
    db.upsert_listing(Listing(source_site="wasalt", source_id="same", source_url="https://wasalt.sa/en/property/same", record_type="sale_listing", name="Wasalt Same", listing_type="sale"))
    assert db.get_listing("darglobal", "same")["name"] == "DG Same"
    assert db.get_listing("wasalt", "same")["name"] == "Wasalt Same"
