from scraper.common.normalize import parse_area_sqm, parse_bedrooms, parse_price


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
