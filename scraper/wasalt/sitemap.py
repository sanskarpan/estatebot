from __future__ import annotations

import re
import xml.etree.ElementTree as ET


def urls_from_sitemap(xml_text: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
        return [x.text.strip() for x in root.iter() if x.tag.endswith("loc") and x.text and x.text.strip()]
    except ET.ParseError:
        # A malformed response should be logged/skipped by the caller, never crash a run.
        return re.findall(r"<loc>\s*(https?://[^<]+)", xml_text, flags=re.I)


def filter_listing_urls(urls: list[str], listing_type: str | None = None) -> list[str]:
    result = []
    for url in urls:
        lower = url.lower()
        if "wasalt.sa/" not in lower and "wasalt.com/" not in lower:
            continue
        if listing_type == "sale" and "/property/sale/" not in lower:
            continue
        if listing_type == "rent" and not ("/property/rent/" in lower or "/dailyrental/" in lower):
            continue
        if any(x in lower for x in ("/property/", "/dailyrental/")):
            result.append(url)
    return list(dict.fromkeys(result))
