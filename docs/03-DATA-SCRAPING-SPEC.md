# 03 — Data Scraping Specification

## 1. Legal & ethical scope (read this before writing a single line of scraper code)

- Scrape **only** pages that are publicly accessible without login, payment, or bypassing any access control (CAPTCHA, WAF challenge, OTP-gated flows). If a page requires authentication to view (e.g. Wasalt's "list your property" dashboard, saved searches, user account areas), it is **out of scope** — this is a deliberate boundary, not a gap.
- Before crawling either domain, the scraper **must** programmatically fetch and parse `https://<domain>/robots.txt` at runtime (do not hardcode assumed rules — sites change them) and:
  - Skip any path disallowed for `User-agent: *` (or for the scraper's own declared user-agent if it chooses to identify itself specifically).
  - Respect a `Crawl-delay` directive if present; otherwise apply the default politeness delay in §4.
  - Log the parsed robots rules that were applied, so a reviewer can audit compliance.
- Identify the scraper honestly via a descriptive `User-Agent` header, e.g. `EstateBot-Assignment-Scraper/1.0 (+contact-or-repo-url; educational/assignment use)`. Do not spoof a browser UA to evade detection — spoofing to bypass an explicit block is out of scope; spoofing a *reasonable, non-deceptive* UA only to avoid trivial bot-blocklists that block on UA string alone is acceptable, but any WAF/CAPTCHA challenge must be treated as a signal to stop and back off, not defeated.
- **Do not attempt to bypass Imperva/Incapsula, Cloudflare, or any other WAF/anti-bot challenge.** DarGlobal has been observed to run behind Imperva Incapsula. If a request returns a challenge page (look for signature strings like `Incapsula incident ID`, `Request unsuccessful. Incapsula incident ID`, `cf-chl`, or a non-200 status paired with a challenge HTML shell instead of real content), the scraper must: back off, retry with a longer delay a small bounded number of times, and if still blocked, log it as a skipped page and move on — never solve the challenge programmatically.
- Store only content that was already intended for public consumption (marketing/listing pages). Do not scrape personal data of private individuals (site staff bios are fine if publicly published; do not scrape user-submitted content like private messages, or any leaked contact form data).
- Respect `noindex`/`nofollow` meta hints as a courtesy signal (they don't legally bind a non-search-engine bot the way robots.txt does, but a `noindex` page is a signal the operator doesn't want it broadly redistributed — treat pages so marked as lower priority / excludable if scope needs trimming).
- Attribute the data source in the product: every answer citation links back to the original DarGlobal/Wasalt URL (§8 in `docs/05-CHATBOT-RAG-SPEC.md`), and the UI states plainly that data is sourced from and belongs to those sites, is not affiliated with or endorsed by them, and may be out of date.
- Rate-limit aggressively (§4) — the goal is a complete, correct corpus, not the fastest possible crawl. A slow, polite, 100%-successful scrape beats a fast one that gets IP-blocked halfway through.
- Keep a documented "not scraped and why" list (this file, §7) so nobody can claim data is missing due to oversight.

## 2. Source A — DarGlobal (`https://darglobal.co.uk`)

### 2.1 Observed site characteristics (verified by direct inspection)
- Built on what appears to be a Next.js-style SSR stack (`meta-next-head-count` present in page `<head>`), meaning the primary content is present in the initial server-rendered HTML — a plain `GET` + HTML parse is sufficient for the vast majority of fields; a headless-browser fallback should rarely be needed for this source.
- Bilingual: English (default) and Arabic (`/ar` or a language toggle) — scrape English by default; Arabic scraping is optional/stretch (see §7).
- CDN-hosted images/media on `cdn.darglobal.co.uk` — image URLs should be captured as metadata (for potential UI thumbnails) but images themselves need not be downloaded/stored.
- Known to sit behind Imperva Incapsula (per third-party technology-profile lookups) — see §1 WAF handling.

### 2.2 Page inventory to scrape

| Page type | Discovery method | Approx. count (floor, re-check at run time) | Key fields to extract |
|---|---|---|---|
| **Project/listing detail pages** (e.g. `/dg1`, `/the-astera`, `/trump-tower-jeddah`, `/rayana/trump-mansions`, `/one-of-one/...`, `/amaya/...`, `/aida-...`) | Crawl `https://darglobal.co.uk/projects` — parse the project grid; each project links to its own detail-page slug. Some slugs are nested (e.g. `/one-of-one/top-of-the-astera`, `/trump-plaza/park-residences`, `/rayana/trump-mansions`, `/amaya/amaya-plots`) — the spider must follow relative hrefs as found, not assume a flat `/slug` pattern. | ~40–70 | `name`, `slug`/URL, `location_area` and `location_country` (shown as "City, Country" under the project name on the grid and again on the detail page), `property_type` (Apartments/Villas/Hotel Rooms — from the filter taxonomy and/or page content), `status` (e.g. "Under Development"), `expected_completion_date`, `unit_types` (e.g. "Studios, 1, 2, & 3-bedrooms"), `area_range_sqm` (e.g. "126 to 177"), `description` (main marketing paragraph), `amenities` (bullet list, e.g. "State-of-the-art Gym", "Infinity Swimming Pool"), `brand_partner` (if co-branded — Aston Martin, Pagani, FENDI Casa, Missoni, Elie Saab, Mouawad, Lamborghini, Trump Organization, W Hotels, Marriott — detect from title/content), `gallery_image_urls`, `brochure_url` (if a "Download Brochure" link is present), `related_project_slugs` (from the "Other projects" section). |
| **Project listing/index page** | `https://darglobal.co.uk/projects` | 1 | Used for discovery (§ above) and also as a source of the type/location taxonomy filter values themselves, useful for building UI filter facets and for validating that scraped `property_type`/`location_country` values match the site's own controlled vocabulary. |
| **Press/newsroom articles** | `https://darglobal.co.uk/press` (paginate/"view all") | Up to 20–30 most recent (configurable `MAX_DARGLOBAL_PRESS`), bounded by the links the public index actually exposes | `title`, `publish_date`, `summary`/teaser, `full_article_text` (if reachable on an article detail page), `article_url`. Useful for "what's new" / "recent news about X" questions and for corroborating project status (e.g. construction contract awards). |
| **Corporate/about pages** | `/about`, `/why-invest`, homepage | handful | Company facts used for general questions ("who is DarGlobal", "how long has DarGlobal existed", "what markets do they operate in") — `founded_year`/track record, headline stats (e.g. "$23B Gross Development Value", "7 International Markets", "12+ Global Brand Partners" — capture as of scrape date, label clearly as a point-in-time company metric, not a per-listing fact). |
| **Brand partner pages** | `/partners/<brand>` (linked from homepage "Collaborations" section) | ~10 | `brand_name`, `description`, `related_project_slugs` — enriches co-branding answers. |

### 2.3 DarGlobal — field-level extraction notes & edge cases
- Location is often only available as free text near the project name (e.g. "Dubai, UAE", "Al Marjan Island, RAK, UAE", "Benahavís, Spain", "Muscat, Oman", "AIDA, Muscat, Oman", "Wadi Safar, Riyadh", "Amaya, Jeddah, KSA", "149 Old Park Lane, London, United Kingdom", "Noonu Atoll, Maldives") — the parser must split this into best-effort `location_area` (neighbourhood/community/masterplan) and `location_country` fields using a small controlled mapping (UAE/Spain/Qatar/Oman/UK/KSA/Saudi Arabia/Maldives) rather than naive comma-splitting alone, because some entries have 3 comma-separated segments and some entries embed the masterplan name (e.g. "AIDA", "Amaya", "Rayana", "Wadi Safar") as a sub-location that should be preserved (store as `masterplan_name` when detectable).
- Price is **frequently not published** on DarGlobal project pages (register-interest / enquire model, not always with a listed price) — `price_amount` will legitimately be `null` for many DarGlobal records. Do not infer a price. Store `price_display_text` verbatim if any indicative price text exists on the page (rare), else leave both null. This is expected and must be handled gracefully downstream (§5.2 in `01-SPEC.md`, and see `docs/10-EDGE-CASES.md`).
- Some project slugs redirect or are duplicated under multiple nested paths for cross-linking purposes (the `?slug=dg1` query-string suffix seen on "Other projects" links is a referrer tag, not a distinct page — the canonical URL is the path without the query string; dedupe on the canonical path).
- Unit type / bedroom counts are given as ranges in prose ("Studios, 1, 2, & 3-bedrooms") — parse into a normalized array `["studio","1br","2br","3br"]` in addition to keeping the raw string, so structured filtering ("does X have 2-bedroom units") is possible.
- Video hero content (`.mp4` links) exists on some pages — not required to capture, optional metadata only.
- "Trump" branding appears across several distinct, differently-located projects (Dubai, Jeddah ×2, Riyadh/Wadi Safar, Maldives) — do not merge these into one record; each is a separate project with its own slug/location and must remain separately addressable, since "Trump properties" questions require enumerating all of them correctly.

## 3. Source B — Wasalt (`https://wasalt.sa`, mirrored at `https://wasalt.com`)

### 3.1 Observed site characteristics
- A large-scale KSA property marketplace: for-sale and for-rent listings, developer "Projects," investment "Plans" (land plots), and "Auctions," across major Saudi cities (Riyadh, Jeddah, Dammam, Al-Khobar, Mecca/Makkah, Medina/Madinah, Al Qassim and others).
- Two apparent domains serve the same product (`wasalt.sa` and `wasalt.com`) — treat them as one logical source in the data model (`source_site: "wasalt"`), but record whichever canonical URL the content actually resolves to, and de-duplicate if both domains are found to serve identical listing content.
- City/category landing pages exist with URL patterns such as `/en/properties-for-sale-in-saudi-arabia`, `/en/properties-for-sale-in-riyadh`, `/en/properties-for-rent-in-riyadh`, `/en/properties-for-rent-in-saudi-arabia`, etc. — pattern: `/en/properties-for-{sale|rent}-in-{scope}`, where `{scope}` is either the country or a specific city slug. These pages are the discovery entry points; actual individual listing cards/detail pages are linked from within them (verify the exact listing-detail URL pattern by inspecting the live listing grid markup at build time — do not assume it sight-unseen, since it wasn't directly inspected during spec-writing; the spider's first run should log 3–5 sample discovered listing URLs for a human/AI sanity check before scaling up).
- AI-backed / dynamic search and filter UI is emphasized in Wasalt's own marketing ("AI-backed real estate platform," map search, filters) — treat the listing grid as potentially JS-rendered/paginated via API calls under the hood. **Build order for the Wasalt spider:**
  1. First attempt plain HTTP GET + HTML parse of a city/category page — if listing cards and their detail links are present in the raw HTML (SSR), proceed with the lightweight httpx+BeautifulSoup path, same as DarGlobal.
  2. If the raw HTML is a near-empty shell and content only appears after JS execution, switch that page type to the Playwright-rendered path (render, wait for the listing grid selector, then extract).
  3. While rendering with Playwright, open browser DevTools network inspection (or Playwright's request interception) to check whether the frontend calls a discoverable JSON API (common on modern listing sites) — if a stable, unauthenticated JSON endpoint is found (e.g. `/api/...` returning listing arrays), prefer calling that endpoint directly over HTML scraping, since it is faster, more reliable, and less brittle to markup changes. Document whatever is actually found in `scraper/wasalt/README.md` (created during implementation) since this cannot be fully predetermined without live browser inspection at build time.
- Licensed by Saudi Arabia's Real Estate General Authority (REGA) — this is a legitimate, large, publicly marketed portal; no indication of blanket anti-scraping technology was found during research, but the scraper must still perform the robots.txt check and WAF-signature detection in §1 defensively regardless.

### 3.2 Page inventory to scrape

| Page type | Discovery method | Target count | Key fields to extract |
|---|---|---|---|
| **Sale listings** | City/category landing pages `/en/properties-for-sale-in-{riyadh,jeddah,dammam,...}` → listing detail pages | ≥ 80 across ≥3 cities | `title`, `listing_type: "sale"`, `property_category` (apartment/villa/land/commercial — from page taxonomy), `city`, `neighbourhood` (if shown), `price_amount`, `price_currency` (SAR), `area_sqm`, `bedrooms`, `bathrooms`, `description`, `amenities`, `image_urls`, `listing_url`, `posted_or_updated_date` (if shown), `agent_or_broker_name` (if shown, non-personal/business identity only). |
| **Rental listings** | `/en/properties-for-rent-in-{city}` → detail pages | ≥ 60 across ≥3 cities | Same as above plus `rent_period` (monthly/yearly) and `listing_type: "rent"`. |
| **Projects** (developer-led new-build projects listed on Wasalt, distinct from DarGlobal's own project pages) | Wasalt "Projects" section (linked from nav/corporate pages; confirm exact path at build time) | best-effort, ≥ 10 if the section is reachable without login | `project_name`, `developer_name`, `city`, `unit_types`, `price_from`, `status`, `description`. |
| **Plans (land plots)** | Wasalt "Plans" section if publicly reachable without login | best-effort, optional | `plan_name`, `city`, `plot_sizes`, `price_from`. |
| **City/market guide content** | The landing pages themselves also contain long-form editorial text (e.g. Riyadh/Jeddah/Dammam city guides, rental-market FAQ content) | all landing pages scraped anyway | Store as a distinct `content_type: "city_guide"` corpus document (not a listing) — valuable for general "tell me about renting in Riyadh" style questions, and for demonstrating retrieval works across content types, not just listing records. |
| **Auctions** | Wasalt Auctions, if publicly listed without login | out of scope for v1 (explicitly deferred — see §7) unless found to be trivially public; do not spend build time here unless everything else is complete. |

### 3.3 Wasalt — field-level extraction notes & edge cases
- Prices are in **SAR** — never convert currency at scrape time; store raw `price_amount` + `price_currency: "SAR"`; any cross-currency comparison in chat responses happens at generation/formatting time with an explicit, clearly-labeled approximate conversion (and only if the model is asked to compare — see `docs/05-CHATBOT-RAG-SPEC.md`).
- City/neighbourhood taxonomy should be normalized against a small controlled list built from the observed landing pages (Riyadh, Jeddah, Dammam, Khobar, Mecca, Medina, Qassim, etc.) so that "properties in Riyadh" reliably matches regardless of minor text variation ("Al-Khobar" vs "Khobar", "Makkah" vs "Mecca" — keep both a `city_raw` and a `city_normalized` field).
- Listing pages are expected to churn (listings get sold/rented and removed) far more than DarGlobal's marketing pages — the ingestion pipeline must tolerate a listing disappearing on re-scrape: mark as `is_active: false` rather than hard-deleting immediately (soft-delete), so historical citations don't 404 without explanation, and so re-runs are safe.
- Arabic-only fields: some descriptive text may only be available in Arabic even when browsing the `/en/` path (partial localization is common on regional portals) — store whatever language is actually present verbatim in `description`, and record a `description_lang` field (`en`/`ar`/`mixed`) rather than silently dropping non-English text; this is both more honest and gives the LLM raw material it can still work with (many free OpenRouter models handle Arabic reasonably).
- Pagination: listing/category pages are near-certainly paginated (e.g. `?page=2`) or infinite-scroll (JS-driven "load more") — the spider must implement explicit pagination handling with a documented page cap (`MAX_PAGES_PER_CATEGORY`, default 5) rather than looping indefinitely, and must detect "no more results" (empty grid / repeated content / disabled "next" control) to stop early and cleanly.
- Duplicate listings across `wasalt.sa` and `wasalt.com`: dedupe by a normalized key (e.g. listing reference number if the site exposes one, else normalized title+price+city+area) before writing to storage.

## 4. Politeness, rate limiting & resilience — applies to both sources

- Default request pacing: **max 1 request per 2 seconds per domain**, single concurrent connection per domain (do not parallelize aggressively against either target — this is a small assignment corpus, not a production crawl; being slow and correct is strictly preferred over being fast and blocked).
- Respect any `Crawl-delay` in `robots.txt` if it specifies a longer delay than the default above.
- Exponential backoff on 429/503: wait 5s, then 15s, then 60s; after 3 consecutive failures on the same URL, log and skip (do not infinite-loop).
- Global circuit breaker: if more than 10 consecutive requests to a domain fail (non-2xx or WAF-challenge-detected), pause that domain's crawl entirely for 5 minutes before a single retry probe; if it fails again, abort that source's run for this session, log clearly, and preserve whatever was already collected (partial success is a valid, logged outcome — not a crash).
- Set reasonable timeouts (connect 10s, read 20s) on every request; never block indefinitely.
- Cache responses to disk during development (`data/raw/`) so repeated local test runs don't re-hit the live sites unnecessarily.
- All of the above must be implemented in the shared `scraper/common/http.py` client so both source-specific spiders inherit identical politeness behaviour rather than reimplementing it.

## 5. Output contract

Every scraper module must, regardless of source, ultimately emit records conforming exactly to `docs/04-DATA-SCHEMA.md`. The scraper is responsible for **normalization into the canonical schema**; nothing downstream should need source-specific knowledge. Concretely:
- `source_site`: `"darglobal"` or `"wasalt"` (enum).
- `source_id`: stable, source-specific unique identifier (slug or listing reference).
- `source_url`: the canonical page URL the data was extracted from (used for citation links).
- `scraped_at`: ISO-8601 UTC timestamp of extraction.
- All other fields per the schema doc, `null` where genuinely unknown — never fabricated or interpolated.

## 6. Failure modes the scraper must handle without crashing

| Failure | Required behaviour |
|---|---|
| Target page 404s or has been removed since discovery | Log, skip, mark previously-stored record (if any) `is_active: false`, continue. |
| Target page structure changed (expected CSS selector not found) | Log a structured warning including the URL and the missing selector, skip that field (leave `null`) or skip the whole record if a required field (name/URL) is missing, continue — never let a single parse exception abort the whole run (wrap per-page parsing in try/except at the spider loop level). |
| WAF/CAPTCHA challenge encountered | Detect via response-content signature check, back off per §4, skip if still blocked after retries, continue with next URL. |
| Network timeout/DNS failure | Retry per §4 backoff policy, then skip and continue. |
| Duplicate content across pages | Deduplicate by `source_id` (or normalized-content hash where no stable ID exists) before persisting. |
| Partial run interrupted (process killed, host restarts) | Because writes are incremental (per-record upsert, not one big batch commit at the end), a re-run picks up safely; no in-memory-only accumulation that could lose an entire run's progress. |
| robots.txt itself unreachable | Treat conservatively: if `robots.txt` cannot be fetched at all (network error), proceed only with the most restrictive reasonable default (public marketing pages only, no deep/parameterized URLs) and log this clearly as a fallback condition for audit. |

## 7. Explicitly out of scope for this scrape (documented, not accidental)

- Anything behind login/OTP/account creation on either site (Wasalt's listing-management dashboard, saved searches, messaging).
- Wasalt Auctions (deferred — public reachability not confirmed without live inspection; low priority relative to core sale/rent/project coverage).
- Full Arabic-language mirror scraping (`/ar` paths) — optional stretch goal only if time remains after the English corpus meets the §7 minimums in `01-SPEC.md`; if attempted, tag records with `language: "ar"` and keep them separate from the primary English corpus rather than blending mid-record.
- Historical/archived listings no longer live on the site (no scraping of web-archive/cache copies).
- Any third-party aggregator or review site (e.g. the `middle-east.realestate` or `propertynetworkuae.com` mirrors of DarGlobal content found during research) — the assignment specifies the two named sources; scrape only the sites' own domains.
- Downloading and re-hosting media assets (images/video/brochure PDFs) — URLs are captured as metadata/links only, not mirrored, to respect bandwidth/copyright and keep the corpus lightweight.

## 8. Verification checklist for the scraper before moving to ingestion

- [ ] `robots.txt` fetched and honoured for both domains at run time (not hardcoded).
- [ ] Sample of 5 records per source manually spot-checked against the live page for accuracy.
- [ ] Every record has non-null `source_site`, `source_id`, `source_url`, `scraped_at`, `name`/`title`.
- [ ] Corpus size meets or exceeds the minimums in `docs/01-SPEC.md` §7.
- [ ] At least 3 distinct Wasalt cities represented.
- [ ] Both `sale` and `rent` listing types represented for Wasalt.
- [ ] At least one full re-run performed to confirm idempotency (record count doesn't duplicate, `updated_at` refreshes, removed listings soft-deleted).
- [ ] Run log reviewed for silent/blanket failures (e.g. every request from one source failing would indicate a structural break needing a parser fix, not a "ship it anyway" situation).
