# eBay alternative-data evaluation — ScrapeBadger

Date: 2026-09-12

Status: **research challenger only; do not replace the current eBay collector yet**

Scanner version: v0.12 (no model, BUY-gate, fair-value, or score changes)

## Executive conclusion

ScrapeBadger is useful for one specific gap in the current scanner: **programmatic completed/sold eBay search**. The current production eBay collector uses eBay's official Buy Browse API for active listings and derives conservative disappearance/quick-sale observations from repeated snapshots. Confirmed sold evidence is still a separate/manual evidence path.

The recommended architecture is therefore:

1. keep the official eBay Browse API as the primary active-listing collector;
2. add ScrapeBadger's completed endpoint as an **optional research challenger** for candidate sold observations;
3. never give the same eBay market two independent votes merely because it arrived through two providers;
4. do not treat every completed-row price as a realised transaction price until Best Offer and exact-identity behaviour has been validated;
5. promote only after manual cross-checking and prospective reliability tests.

This is potentially high-value because it can improve the weak point in our current eBay evidence — realised/completed observations — without discarding the official active-listing pipeline that already has hard marketplace/country guards.

## Current scanner eBay architecture

`src/deal_scanner/market_observatory.py` currently uses eBay's official Browse API for live listings.

Current strengths:

- official API and OAuth credentials (`EBAY_APP_ID`, `EBAY_CERT_ID`);
- explicit marketplace coverage for Ireland, EU, UK and US;
- watchlist queries plus required/excluded tokens;
- hard country/location matching so currency-converted foreign listings do not masquerade as domestic supply;
- exact listing IDs and repeated SQLite observations;
- active supply and ask-price history;
- conservative quick-sale inference only after a previously observed listing disappears under the configured checks;
- confirmed sold rows are kept distinct from inferred disappearance evidence.

Current limitation:

- the Buy Browse API is an **active-listing API**, not a completed/sold research feed;
- therefore confirmed sold evidence has to come from the separate `ebay_sold_evidence.csv`/manual research path;
- disappearance is useful liquidity evidence but is not proof of a completed transaction or realised price.

That limitation is the main reason ScrapeBadger is worth testing.

## ScrapeBadger eBay product

Sources reviewed:

- https://scrapebadger.com/blog/how-to-build-an-ebay-price-tracker-with-scrapebadger
- https://docs.scrapebadger.com/ebay/overview
- https://docs.scrapebadger.com/api-reference/endpoint/ebay/completed
- https://scrapebadger.com/pricing

### Relevant endpoints

ScrapeBadger documents an eBay scraper with endpoints for:

- active search;
- completed/sold search;
- item detail;
- image search;
- seller profile/items/feedback;
- categories/autocomplete/markets.

For this project, the important endpoint is the completed search. It is documented as supporting:

- free-text query;
- eBay domain/market;
- category;
- page and result size;
- sorting;
- min/max price;
- condition, including graded/ungraded;
- domestic vs worldwide location scope;
- result fields including item ID, title, price, condition, format, bids, shipping, seller and sold date.

ScrapeBadger currently documents 18 supported eBay markets including Ireland, UK, Germany, France, Italy, Spain, Netherlands, Belgium and Austria, so it can broadly mirror the scanner's existing European routing geography.

### Why `location=domestic` matters

ScrapeBadger's documentation explicitly distinguishes domestic listings from worldwide/currency-converted results. This is compatible with our existing hard-country principle: a listing shown in EUR/GBP/USD must not be assumed local solely because of currency presentation.

If integrated, market/domain + domestic-location verification should remain mandatory rather than trusting the query label alone.

## Critical price caveat: completed does not automatically mean confirmed paid price

The completed endpoint is described by the vendor as returning completed/sold rows and a `price` field. That is useful but **not sufficient to call every row a confirmed realised sale price**.

A known eBay research problem is Best Offer: public completed pages can retain/display the original/listed fixed price rather than the confidential accepted offer. Therefore our model should distinguish at least:

- **auction sold** — generally strongest candidate for realised final price;
- **fixed-price sold without Best Offer evidence** — stronger candidate, still subject to identity/condition checks;
- **Best Offer accepted / ambiguous negotiated sale** — sold-state evidence, but price should be marked uncertain until independently confirmed (for example through eBay Product Research/Terapeak or another trustworthy source).

This means ScrapeBadger can immediately be useful for **sale-state/velocity research**, while price evidence needs confidence typing.

## Cost

ScrapeBadger currently advertises:

- 1,000 signup/free credits;
- PAYG from $10, with the pricing page showing roughly $0.150 per 1,000 credits;
- Starter $49/month for 600k credits;
- Growth $129/month for 1.8m;
- Pro $299/month for 5m;
- Scale $699/month for 13m.

The active-search and completed-search endpoints are documented at 5 credits/request.

Illustrative scale for our project: 10 exact cards × 4 market groups × active + completed once daily = 80 calls/day = 400 credits/day, about 12,000 credits/month. The API-credit consumption itself is therefore small; the real question is reliability/identity quality, not compute cost.

No ScrapeBadger API key is connected to the repository today, so this review did **not** execute paid/live ScrapeBadger API calls. The comparison is based on the provider's current public documentation plus our current scanner implementation.

## Comparison with the current eBay collector

| Dimension | Current official eBay Browse collector | ScrapeBadger |
|---|---|---|
| Active listings | **Strong / production** | Available, but redundant initially |
| Completed/sold discovery | Not provided by Browse API | **Main advantage** |
| Provider | Official eBay API | Third-party scraper/API |
| Credentials | Existing eBay app credentials | Additional ScrapeBadger key required |
| IE/EU marketplace coverage | Already configured | Broad supported-domain coverage |
| Country guard | Existing explicit hard guard | Must configure and re-validate `domestic`/domain behaviour |
| Listing IDs | Yes | Yes, per docs |
| Historical active snapshots | Yes, our SQLite | Could collect, but no reason to duplicate initially |
| Disappearance inference | Yes, conservative | Could be built, but current code already does this |
| Sold date | No native completed feed | **Yes, documented** |
| Realised price certainty | Manual/verified evidence only | Mixed; Best Offer caveat requires confidence labels |
| Identity controls | Our required/excluded token logic | Must be layered with our own exact-identity rules |
| Graded/ungraded filtering | Our token exclusions | Endpoint documents graded/ungraded filter |
| Search pagination | API limit/our collector | Deep pagination documented |
| Anti-bot maintenance | eBay's responsibility | ScrapeBadger's responsibility; vendor dependency |
| Source authority | Primary platform API | Secondary provider over the same eBay market |

## Recommended pilot

Do **not** replace `run_ebay_observatory()`.

Create an optional research collector, conceptually `ebay_completed_scrapebadger`, that writes append-only candidate completed observations with fields such as:

- `observed_at`
- `marketplace`
- `query_id`
- `id_product`
- `ebay_item_id`
- `title`
- `sold_date`
- `reported_price`
- `shipping`
- `condition`
- `buying_format`
- `best_offer_possible_or_unknown`
- `identity_status`
- `language_status`
- `raw_or_graded_status`
- `price_confidence`
- `provider=SCRAPEBADGER`

Do not merge it blindly into the existing confirmed-sold table.

### Validation set before promotion

Manually check at least 50 completed rows spanning:

- auctions;
- fixed-price sales;
- Best Offer-enabled sales;
- modern raw singles;
- vintage raw singles;
- graded cards;
- multilingual European listings;
- high-duplicate product names/collector numbers.

For each row verify:

1. exact printing/set/collector number;
2. raw vs graded;
3. language where production use requires it;
4. sold/completed state;
5. sold date;
6. domestic-market interpretation;
7. whether the displayed price can credibly be treated as the paid price.

Suggested acceptance gates for using the feed as more than a diagnostic:

- >=95% exact-print precision for rows admitted into card-level price evidence;
- >=95% raw/graded classification precision;
- no systematic domestic-market leakage;
- explicit uncertainty treatment for Best Offer;
- stable IDs/deduplication across repeated calls;
- measured uptime/staleness over several weeks;
- no double counting against manual/eBay Product Research evidence.

## Source role if adopted

Recommended source role:

`EBAY_COMPLETED_CANDIDATE`

Possible later subtypes after validation:

- `EBAY_COMPLETED_AUCTION_HIGH_CONFIDENCE`
- `EBAY_COMPLETED_FIXED_PRICE_HIGH_CONFIDENCE`
- `EBAY_COMPLETED_BEST_OFFER_PRICE_UNCERTAIN`

It should contribute to sale velocity and market diagnostics immediately after basic validation. Promotion into realised-price/fair-value evidence should be stricter.

## Final decision

**Worth integrating as a research challenger: YES.**

**Replace the current eBay active collector: NO.**

**Main expected value:** better completed/sold evidence, sale dates, liquidity/velocity and potentially ECS/market-quality support.

**Main risk:** treating a scraper's completed-row `price` as a literal paid price, especially for Best Offer transactions, or treating the same eBay observation as an independent second market signal.
