# Adverts.ie historical evidence — manual/public workflow

Last reviewed: 2026-09-06

## What is available

Adverts.ie can retain historical/inactive listing information that is useful for Irish Pokémon market calibration. Publicly accessible old/sold listing pages may preserve:

- listing title and asking price;
- explicit sold/inactive state where shown;
- listing description and images where still available;
- the visible Comments & Offers thread;
- concrete offer amounts and seller responses;
- timestamps/relative timing; and
- seller/profile context.

Adverts' own help documentation states that profiles can contain active and inactive ads. The mobile app may expose historical seller ads more conveniently than the desktop public site.

## Evidence interpretation

Historical Adverts data must keep the existing confidence hierarchy:

1. explicit sold state + visible accepted concrete price/offer;
2. explicit sold state, realized price unknown;
3. seller explicitly marks item/subset sold;
4. concrete accepted offer without sold state;
5. PM/DM/contact placeholder acceptance;
6. disappearance/withdrawal;
7. active ask only.

A visible offer is not automatically the realized sale price. A seller's acceptance of a PM/DM placeholder is weaker than a concrete accepted amount. A withdrawn/inactive ad is not automatically a sale.

## Permitted retrieval approach for this project

Use manual/public access only. Useful methods include:

- opening a known old Adverts listing URL directly;
- following publicly accessible seller/profile links and inactive/sold ads when available;
- using normal public web/search-engine indexing to locate exact old listing URLs;
- manually reviewing publicly visible Comments & Offers on those pages;
- user-provided screenshots from the official Adverts mobile app when a historical page is visible in-app but cannot be reached through the public web interface.

When the user provides a seller link, seller ID, or old ad URL, manually inspect the relevant historical Pokémon ads and normalize only the useful market evidence into the project's reference files.

## Access restrictions

Do **not** build an automated Adverts scraper, crawler, reverse-engineer the mobile app/backend, intercept private API traffic, or construct a systematic database from automated retrieval.

The Adverts.ie Terms of Use reviewed on 2026-09-06 prohibit, among other things:

- robots/spiders/search-retrieval applications or other automated means to access/retrieve/index the service;
- accessing/retrieving/indexing the service to construct or populate a database;
- reverse engineering portions of the service; and
- scraping/mirroring content without permission.

Therefore the scanner should not automate Adverts retrieval. Historical evidence may be entered manually after public review, with source/status/confidence clearly labelled.

## Practical project workflow

For a tracked seller:

1. identify historical Pokémon listings manually;
2. open each relevant old listing where publicly accessible;
3. record status (active/sold/withdrawn/unknown);
4. inspect concrete offers/comments and seller responses;
5. distinguish ask, accepted offer, and confirmed sold state;
6. compare the resulting Irish evidence with Cardmarket EN/NM and eBay/Product Research evidence;
7. preserve only normalized evidence needed for project decisions, not a bulk copy of Adverts content or personal data.

This historical review is particularly valuable for standing seller benchmarks such as Rocco_jr, PokeDub, batch91, and other sellers whose realized local prices can calibrate Irish resale better than active asks alone.

Official references reviewed:

- https://help.adverts.ie/hc/en-us/articles/360001288725-Terms-Conditions-of-Use-of-Adverts
- https://help.adverts.ie/hc/en-us/articles/360001336889-I-cant-find-my-advert-on-the-site
