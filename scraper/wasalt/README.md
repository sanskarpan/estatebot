# Wasalt source notes

Live-source inspection on 2026-09-02 found readable public `robots.txt` and CDN sitemap XML, while direct landing/detail HTTP probes could return a Cloudflare challenge. No stable, documented public JSON listing API was identified or assumed. The implementation therefore uses permitted sitemap discovery, bounded sale/rent detail fetching, challenge detection, and conservative HTML/JSON-LD parsing when a public detail response is available.

The checked-in snapshot contains 180 genuine English detail records across Dammam, Jeddah, and Riyadh (88 sale, 92 rent), plus one city-guide document per city. Search pages, login-gated content, auctions, plans, and unverified dynamic sections are deliberately excluded. See [`../live-findings.md`](../live-findings.md) for the cross-source evidence log.
