from pathlib import Path

import pytest

from backend.app.db.database import Database
from backend.app.models.schema import Listing
from ingestion.build_index import build_index


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    database.upsert_listing(Listing(source_site="darglobal", source_id="dg1", source_url="https://darglobal.co.uk/dg1", record_type="project", name="DG1", property_category="apartment", location_city="Dubai", location_country="United Arab Emirates", bedrooms="Studios, 1, 2 and 3 bedrooms", bedrooms_min=0, bedrooms_max=3, unit_types_normalized=["studio", "1br", "2br", "3br"], price_currency="AED", image_urls=["https://cdn.darglobal.co.uk/dg1.jpg"], description="Luxury apartments in Business Bay with a sky garden and infinity pool."))
    database.upsert_listing(Listing(source_site="wasalt", source_id="jeddah-1", source_url="https://wasalt.sa/en/property/jeddah-1", record_type="sale_listing", name="Jeddah Family Villa", property_category="villa", listing_type="sale", location_city="Jeddah", location_country="Saudi Arabia", bedrooms="4", bedrooms_min=4, bedrooms_max=4, price_amount=1250000, price_currency="SAR", description="A spacious family villa near parks."))
    database.upsert_listing(Listing(source_site="wasalt", source_id="riyadh-rent", source_url="https://wasalt.sa/en/property/riyadh-rent", record_type="rent_listing", name="Riyadh Apartment", property_category="apartment", listing_type="rent", rent_period="yearly", location_city="Riyadh", location_country="Saudi Arabia", bedrooms="2", bedrooms_min=2, bedrooms_max=2, price_amount=60000, price_currency="SAR", description="Modern apartment close to business districts."))
    build_index(database)
    return database
