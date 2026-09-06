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

This is currently the most promising route.

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

### 4. Arquivo.pt

Arquivo.pt is an independent European web archive with Memento/TimeMap endpoints. It is useful as an additional exact-URL archive source independent of Wayback/Common Crawl.

### 5. archive.today / archive.ph

Useful as a manual corroboration source where a snapshot already exists. Do not assume an official bulk API exists or build automation that violates archive-site access rules.

## Controlled test results — 2026-09-06

Known sold batch91 listings initially tested:
- `40758551`
- `40926024`
- `40926025`

### Archive probe #1

Wayback CDX + Common Crawl exact-URL lookup:
- 3 listings tested
- 0 archive hits
- multiple Wayback timeouts/503s and Common Crawl 502/503/504s, so the first zero-result run was not sufficient by itself.

### Archive probe #2

Hardened test with retries plus:
- Wayback Availability API
- Wayback CDX
- recent Common Crawl indexes
- Arquivo.pt Memento lookup

Result:
- 3 listings tested
- 0 Wayback Availability hits
- 0 Wayback CDX hits
- 0 Common Crawl hits
- 0 Arquivo.pt hits

This materially lowers confidence that public web archives will recover recent Adverts sold listings at useful hit rates.

### Search-index test — expanded sample

A third-party web-search index was tested against known historical listings already present in `data/reference/local_seller_history.csv`.

The normalized sample is stored in `data/reference/adverts_search_index_probe.csv`.

Current sample:
- 13 known listings tested
- 10 recovered as an exact listing page
- 2 recovered through an exact listing/title entry on an Adverts results page
- 1 not recovered (`40758551`, whose generic title is simply `Pokemon Cards`)

Observed useful-hit rate: **12/13 = 92%**.
Observed exact-page hit rate: **10/13 = 77%**.

This is still a small and non-random sample, so it must not be treated as a production reliability estimate. However, it is materially more promising than the public-archive route.

Important search behavior discovered:
- searching only the numeric listing ID can miss pages;
- **exact or distinctive listing titles perform much better**;
- seller + title is a useful fallback;
- numeric ID + seller + title is useful for generic titles;
- generic titles such as `Pokemon Cards` are the hardest case;
- both `www.adverts.ie` and `touch.adverts.ie` pages appear in search indexes.

Examples recovered from the search index include:
- `40926024`: exact batch91 page, €20 ask and description;
- `40926025`: exact batch91 page, €20 ask plus offer/comment evidence;
- `36964449`: exact PokeDub page with €600/€750 offers and later `Still Available` evidence;
- `37253325`: exact PokeDub page with rejected €125/€140 offers and DM-placeholder acceptance;
- `38889838`: exact competitor bundle page including the 2 bundles for €13 delivered comment;
- `40758540`: exact batch91 €25 binder page.

A `touch.adverts.ie` search result was also observed for a sold Pokémon card page showing the explicit message `This item has been sold. Here are some similar ads...`. This confirms that third-party search indexes can retain sold-state pages even where the original item body has been replaced by a sold fallback page.

## Current technical direction

Prioritize **third-party search-index enrichment** over traditional web archives.

Proposed query order for a known listing:
1. exact distinctive listing title;
2. exact title + seller;
3. listing ID + seller + title;
4. known canonical URL / ID query;
5. touch-host variant query;
6. Wayback Availability/CDX exact URL;
7. Common Crawl exact URL;
8. Arquivo.pt exact URL;
9. archive.today manual corroboration when useful.

The repository now contains:
- `scripts/probe_adverts_archives.py`
- `scripts/probe_adverts_touch_archives.py`
- `scripts/probe_adverts_search_index.py`
- `data/reference/adverts_search_index_probe.csv`

The search-index script is prepared for Firecrawl API search if `FIRECRAWL_API_KEY` is configured as a GitHub Actions secret. Firecrawl's documented v2 Search endpoint supports web search, domain restriction and result snippets/metadata, which fits this use case.

A ChatGPT Firecrawl plugin connection is separate from a GitHub Actions API secret and should not be assumed to populate that secret automatically.

## URL-variant probe

Because historical Adverts pages may have been indexed under older hosts, the probe also tests known ID paths on variants such as:
- `www.adverts.ie`
- bare `adverts.ie`
- `touch.adverts.ie`
- HTTP and HTTPS

This remains third-party archive lookup only; the probe does not request those Adverts URLs directly.

## Better production design: observe before and after sale

Trying to reconstruct a listing only after it is sold is inherently fragile. A better design is to query third-party search indexes periodically for **known tracked listings while they are active**, storing only normalized evidence such as ask, seller, visible offers/comments and the indexed timestamp.

Later, when a third-party index shows a sold-state page or other independent sold evidence appears, the scanner can reconcile the earlier active snapshot with the later sold state.

This can turn:
- active ask snapshot + accepted concrete offer + later sold state

into much stronger local realized-price evidence than attempting to recover everything from a sold fallback page after the fact.

## Proposed evidence pipeline

Input:
- known `listing_id`
- known or reconstructed canonical listing URL
- optional seller/title keywords

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

Strongest archived/indexed Adverts evidence would show:
- exact listing identity
- sold state
- a concrete accepted offer or explicit transaction price

Search snippets that show a concrete accepted offer plus later independent sold-state evidence can be treated as strong corroboration, but the exact completed transaction price remains technically unverified unless explicitly shown.

## Next technical test

1. Finish the touch/hostname archive variant run.
2. Run the Firecrawl search-index probe on the known sample once a GitHub Actions `FIRECRAWL_API_KEY` secret is available.
3. Expand to at least 20 known historical Adverts listings and compare exact-title, seller+title, ID+seller+title and touch-host query hit rates.
4. If Firecrawl reproduces the strong manual search-index hit rate, build a separate `search_index_enrichment` component with strict source labelling and confidence rules.

## References

- Adverts.ie Terms & Conditions of Use: direct automated retrieval/indexing and database construction are prohibited.
- Internet Archive Wayback CDX / Availability APIs.
- Common Crawl public CDXJ/URL indexes.
- Arquivo.pt Memento/TimeMap API.
- Firecrawl v2 Search API documentation.
