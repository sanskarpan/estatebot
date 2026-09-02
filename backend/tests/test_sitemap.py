from scraper.wasalt.parsers import discover_listing_urls
from scraper.wasalt.sitemap import filter_listing_urls, urls_from_sitemap


def test_sitemap_discovery_is_bounded_and_typed():
    xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://wasalt.sa/en/property/sale/villa-123</loc></url><url><loc>https://wasalt.sa/en/dailyrental/apartment-2</loc></url></urlset>'
    urls = urls_from_sitemap(xml)
    assert len(filter_listing_urls(urls, "sale")) == 1
    assert len(filter_listing_urls(urls, "rent")) == 1


def test_json_ld_discovery_ignores_landing_pages():
    html = '''<script type="application/ld+json">
    {"itemListElement":[
      {"url":"https://wasalt.sa/en/property/sale/villa-123"},
      {"url":"https://wasalt.sa/en/properties-for-sale-in-saudi-arabia"}
    ]}
    </script>'''
    assert discover_listing_urls("https://wasalt.sa/en/properties-for-sale-in-riyadh", html) == ["https://wasalt.sa/en/property/sale/villa-123"]
