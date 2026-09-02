from datetime import datetime, timezone
from pathlib import Path

from scraper.darglobal.parsers import parse_project
from scraper.darglobal.browser_capture import company_document_from_capture, document_from_capture, listing_from_capture
from scraper.wasalt.parsers import parse_listing
from scraper.wasalt.browser_capture import project_from_capture


def test_darglobal_project_fixture():
    html = Path("backend/tests/fixtures/darglobal_project.html").read_text()
    item = parse_project("https://darglobal.co.uk/dg1", html, datetime.now(timezone.utc))
    assert item.name == "DG1"
    assert item.location_city == "Dubai"
    assert item.location_country == "United Arab Emirates"
    assert item.bedrooms_min == 0
    assert "3br" in item.unit_types_normalized
    assert item.price_amount is None
    assert item.expected_completion_date.isoformat() == "2027-10-01"
    assert item.expected_completion_raw == "completion Q4 2027"


def test_wasalt_listing_fixture():
    html = Path("backend/tests/fixtures/wasalt_listing.html").read_text()
    item = parse_listing("https://wasalt.sa/en/property/jeddah-1", html, "sale", "jeddah", datetime.now(timezone.utc))
    assert item.location_city == "Jeddah"
    assert item.price_amount == 1250000
    assert item.price_currency == "SAR"
    assert item.bedrooms_min == 4


def test_darglobal_browser_capture_normalizes_sections():
    record = {
        "href": "https://darglobal.co.uk/aida-test-villas",
        "name": "TEST VILLAS",
        "h1": "TEST VILLAS",
        "location": "MUSCAT, OMAN",
        "meta": "Public project page",
        "images": ["https://cdn.darglobal.co.uk/test.jpg"],
        "brochure": "https://cdn.darglobal.co.uk/Modern_Slavery_Act_Statement.pdf",
        "text": """TEST VILLAS
MUSCAT | OMAN
Waterfront villas at AIDA.
PROPERTY TYPE
Luxury Villas
STATUS
Under Development
UNIT TYPE
3 and 4-Bedroom Villas
AREA FROM (SQFT)
2,000 to 3,000
EXPECTED COMPLETION DATE
December 2029
AMENITIES
Infinity Pool
Fitness Center
WHY INVEST
General market information
REGISTER YOUR INTEREST
Contact form""",
    }
    item = listing_from_capture(record, "2026-09-02T13:00:00Z")
    assert item.location_country == "Oman"
    assert item.location_city == "Muscat"
    assert item.property_category == "villa"
    assert (item.bedrooms_min, item.bedrooms_max) == (3, 4)
    assert round(item.area_sqm_min, 1) == 185.8
    assert item.amenities == ["Infinity Pool", "Fitness Center"]
    assert item.brochure_url is None


def test_darglobal_browser_press_capture_normalizes_body_and_date():
    record = {
        "source_url": "https://darglobal.co.uk/press/example-release",
        "title": "Example release",
        "published_at": "06/08/2026",
        "body_text": "GET IN TOUCH\nEnglish\nExample release\n06/08/2026\nDubai, UAE\nThe public announcement body.",
    }
    item = document_from_capture(record, "2026-09-02T13:00:00Z")
    assert item.source_id == "press/example-release"
    assert item.publish_date.isoformat() == "2026-08-06"
    assert item.body_text.startswith("06/08/2026 Dubai, UAE")
    assert "GET IN TOUCH" not in item.body_text


def test_darglobal_company_capture_normalizes_body():
    item = company_document_from_capture({
        "source_url": "https://darglobal.co.uk/about",
        "title": "DISCOVER DARGLOBAL",
        "body_text": "GET IN TOUCH\nDISCOVER DARGLOBAL\nA global luxury real estate developer.",
    }, "2026-09-02T13:00:00Z")
    assert item.source_id == "about"
    assert item.content_type == "company_info"
    assert item.body_text == "A global luxury real estate developer."


def test_wasalt_project_browser_capture_normalizes_project():
    record = {
        "href": "https://wasalt.sa/en/project/Riyadh/sadeem-town-villa-100319",
        "card_text": "2.29M - 2.50M Sadeem Town Villa",
        "images": [
            "https://cdn.wasalt.sa/images/wasalt-logo.svg",
            "https://imagedelivery.net/example/production/compound/100319/images/project.jpg",
            "https://imagedelivery.net/example/production/compound/999999/images/related.jpg",
        ],
        "text": """Home
Properties for Sale in Riyadh
Sadeem Town Villa
Project
For Sale
Completion in 2027
Sadeem Town Villa
As-Safa, Center, RiyadhMap view
4,5,6
Bedrooms
5,6,7
Bathrooms
325 - 440 sqm
Built-Up Area
Available Property Types
Villa (3)
Amenities
Security System
Smart Home System
About Project
A family villa development.
Units Available (3 of 3)
For Sale
Starts From
2.29M
3
Example Developer
Ref no.
100319""",
    }
    item = project_from_capture(record, "2026-09-02T14:00:00Z")
    assert item.record_type == "project"
    assert item.location_city == "Riyadh"
    assert item.location_area == "As-Safa"
    assert item.property_category == "villa"
    assert item.developer_name == "Example Developer"
    assert item.image_urls == ["https://imagedelivery.net/example/production/compound/100319/images/project.jpg"]
    assert item.price_amount == 2290000
    assert (item.bedrooms_min, item.bedrooms_max) == (4, 6)
    assert item.expected_completion_date.isoformat() == "2027-01-01"
