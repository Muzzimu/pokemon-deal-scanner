# Adverts sold-listing archive research

Last updated: 2026-09-06

## Goal

Find a compliant way to recover historical Adverts.ie listing evidence after an advert is sold/removed, without directly automating retrieval or indexing of Adverts.ie itself.

## Important constraint

Adverts.ie Terms prohibit robots/spiders/search-retrieval applications or other automated means used to access, retrieve or index portions of the Adverts service, and prohibit retrieving/indexing the service to construct or populate a database.

Therefore the scanner must **not** automate direct Adverts.ie crawling, app/API reverse engineering, or direct sold-listing harvesting.

A sold advert remaining visible in the mobile app does **not** imply that a public web archive exists. The app may simply retrieve retained data from Adverts' own backend.

## Compliant archive-enrichment path

The promising approach is to query **third-party public archives and search indexes**, not Adverts directly.

### 1. Search-engine index/snippets

Use public web-search results to recover title, asking price, description fragments, offer snippets, seller name and sold-state hints when indexed. Treat snippets as weak-to-medium evidence depending on detail and recency.

### 2. Internet Archive / Wayback Machine

For a known listing URL, query the public CDX index for exact captures and historical snapshots. The CDX API supports exact, prefix and domain matching plus date/status filters.

Potential fields to extract from a captured page:
- listing ID and URL
- capture timestamp
- title
- asking price at capture
- description
- seller name/member ID when visible
- offer/comment evidence when visible
- sold badge/state if present in that snapshot

A Wayback capture showing the page as sold is useful corroboration, but a sold badge still does not prove the realized transaction price unless a matching accepted offer or explicit sold price is visible.

### 3. Common Crawl

Common Crawl exposes a public CDXJ/URL index and WARC content. For known Adverts URLs, query recent and historical crawl indexes for captured versions. This is especially useful where Wayback has no snapshot or where search engines have dropped the page.

Recommended use is exact known-URL lookup rather than broad crawling. Store only normalized market-evidence fields needed for the project, not entire archived pages.

### 4. archive.today / archive.ph

Useful as a manual corroboration source where a snapshot already exists. Do not assume an official bulk API exists or build automation that violates archive-site access rules.

## Proposed evidence pipeline

Input:
- known `listing_id`
- known or reconstructed canonical listing URL
- optional seller/title keywords

Lookup order:
1. current public search-engine result/snippet
2. Wayback CDX exact URL
3. Common Crawl exact URL across recent indexes
4. archive.today manual lookup when needed

Normalize to:
- `listing_id`
- `source`
- `capture_timestamp`
- `title`
- `ask_price_eur`
- `observed_offer_eur`
- `sold_state`
- `realized_price_known`
- `seller_name`
- `evidence_type`
- `sale_confidence`
- `source_url`
- `notes`

## Evidence interpretation

Do not equate any of the following with a realized sale price:
- sold badge by itself
- listing disappearance
- archive snapshot disappearance
- active asking price
- PM/DM placeholder acceptance

Strongest archived Adverts evidence would be a snapshot that simultaneously shows:
- exact listing identity
- sold state
- a concrete accepted offer or explicit transaction price

## Next technical test

Use a small controlled sample of known historical listings from `data/reference/local_seller_history.csv`, including batch91 listings, and measure archive hit rate across Wayback/Common Crawl before adding code to the scanner.

If hit rate is useful, implement a separate `archive_enrichment` module that queries only third-party archive/search-index services and never directly crawls Adverts.ie.

## References

- Adverts.ie Terms & Conditions of Use: direct automated retrieval/indexing and database construction are prohibited.
- Internet Archive Wayback CDX API documentation: exact/prefix/domain URL matching, filtering and JSON output.
- Common Crawl: public CDXJ/URL index and WARC archive access.
