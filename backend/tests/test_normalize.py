from scraper.common.normalize import canonical_url, clean_text, normalize_city, parse_area_sqm, parse_bedrooms, parse_date, parse_price


def test_price_is_conservative():
    assert parse_price("1,250,000 SAR")[:2] == (1250000.0, "SAR")
    assert parse_price("Price on request") == (None, None, "Price on request")


def test_area_converts_square_feet():
    low, high = parse_area_sqm("1,000 - 1,200 sqft")
    assert round(low, 1) == 92.9
    assert round(high, 1) == 111.5


def test_bedroom_ranges_and_studio():
    assert parse_bedrooms("Studios, 1-3 bedrooms")[1:3] == (0, 3)
    assert parse_bedrooms("2-3 bedrooms")[1:3] == (2, 3)


def test_quarter_completion_date_uses_period_start():
    assert parse_date("Q4 2027").isoformat() == "2027-10-01"
    assert parse_date("Expected completion Q4 2027").isoformat() == "2027-10-01"


def test_completion_year_in_phrase_uses_year_start():
    assert parse_date("Completion in 2027").isoformat() == "2027-01-01"
    assert parse_date("The project launched in 2027") is None


def test_text_and_url_canonicalization():
    assert clean_text("Luxury&nbsp;  homes &amp; villas") == "Luxury homes & villas"
    assert canonical_url("https://example.com/projects", "/dg1/?utm_source=x&ref=y") == "https://example.com/dg1"


def test_city_alias_normalization():
    assert normalize_city("Al-Khobar") == "Khobar"
    assert normalize_city("Makkah") == "Mecca"
