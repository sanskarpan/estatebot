from scraper.common.http import PoliteHTTPClient


def test_waf_signature_detection():
    assert PoliteHTTPClient._is_waf("<html>Request unsuccessful. Incapsula incident ID: 123</html>", 200)
    assert PoliteHTTPClient._is_waf("<html><title>Just a moment...</title>cf-chl-abc</html>", 200)
    assert not PoliteHTTPClient._is_waf("<html><body>Normal property page</body></html>", 200)
