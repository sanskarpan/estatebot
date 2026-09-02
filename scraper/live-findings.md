# Live source findings

Observed during the implementation pass on 2026-09-02 (UTC):

| Source | Observation | Implementation decision |
|---|---|---|
| `darglobal.co.uk` | Plain HTTP probes for `robots.txt`, `/projects`, and sitemap content returned an Incapsula HTML shell. The public `/projects` index, all 36 linked project pages, 15 articles exposed by the current `/press` index, and the About/Investor Relations pages loaded normally in a standard, unauthenticated browser session. Its visible “Load More” control did not reveal more article links during the capture. | Keep the HTTP spider's WAF stop behavior. Capture only the visible public DOM through the normal browser path, store the auditable capture, and normalize it with `ingestion.import_darglobal_capture`; no cookies, CAPTCHA solving, fingerprint spoofing, or hidden API access was used. |
| `wasalt.sa` | `robots.txt` was publicly readable and allows `/` for the default user-agent while disallowing `/search` and `/cdn-cgi/rum`. Listing landing/detail probes returned Cloudflare challenge responses (`403`, `cf-mitigated: challenge`). | Use the permitted public sitemap as a discovery fallback, but do not solve the Cloudflare challenge. Detail records are only persisted when their public detail response is actually available. |
| `cdn.wasalt.sa` | English product and rental sitemap XML was publicly readable and contains canonical `wasalt.sa` listing URLs. | Added sitemap parsing for bounded discovery; it is not treated as a substitute for listing-detail facts. |

These observations can change. Re-run the scraper when the access state changes and record the resulting run counts in the submission notes.

Current normalized snapshot: 36 DarGlobal projects, 15 dated DarGlobal press releases, 2 DarGlobal company documents, 180 Wasalt sale/rent listings, and 3 Wasalt city-guide documents.
