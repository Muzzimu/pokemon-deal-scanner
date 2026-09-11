# Cardmarket live-offer data options

Last reviewed: 2026-09-11

## Why this matters

The scanner's largest Cardmarket data gap is not product identity or daily market pricing; Cardmarket already publishes those through its official downloadable product catalogue and price guide. The missing layer is **live offer-level data filtered to the exact printing, language, condition, seller and Ireland-eligible shipping context**.

That live layer materially improves Cardmarket -> CardTrader arbitrage because it can tell us whether a previously validated acquisition price still resembles the current English/NM article market. It still cannot prove landed cost unless Ireland shipping is known.

## Current baseline: official Cardmarket downloads

Keep the official product catalogue + daily price guide as the production baseline. They are free, stable and explicitly published by Cardmarket. They provide product IDs, catalogue metadata, low/trend and 1/7/30-day market averages, but the generic low is not English/NM-specific and therefore cannot create an automatic BUY signal.

## Official Cardmarket API

Cardmarket still documents API v2, but its help page currently says it is **not accepting new applications for API access**. Existing API credentials must not be shared with third-party apps. For this project, the official API would be the preferred live-offer source if Cardmarket grants access/permission in future.

## Apify options

There are two materially different kinds of Cardmarket actors on Apify:

1. **Daily market-price actors** that mainly package Cardmarket's published catalogue/price-guide data. These add little value because the scanner already downloads the same official source directly for free.
2. **Browser/residential-proxy actors** that load Cardmarket product pages and extract live offers. These can technically expose useful live offer data, but they are a more fragile and higher-risk dependency because they operate against a site that actively deploys anti-automation controls.

The project does not implement Cloudflare bypass, fingerprint spoofing, challenge solving, residential-proxy rotation or logged-in session harvesting. If an external provider exposes public-data access behind a normal REST contract, the scanner can consume that provider without coupling our code to its internal scraping implementation.

## Parse.bot Cardmarket wrapper

Parse.bot currently advertises an unofficial Cardmarket wrapper with `get_card_listings` and related endpoints. Its current documentation says the exact Cardmarket numeric `idProduct` can be used, and listing responses can be filtered by language and minimum condition. The wrapper is explicitly described as independent of Cardmarket rather than Cardmarket's official API.

### v0.8.2 implementation

The repository contains `src/deal_scanner/cardmarket_live.py`, a **feature-flagged, low-volume validation layer**. The current provider implementation calls Parse.bot's public REST wrapper when `PARSE_API_KEY` is present.

The validator deliberately does not:

- send Cardmarket login credentials or cookies;
- scrape Cardmarket directly;
- rotate proxies or evade Cloudflare itself;
- interpret a live article price as Ireland-landed cost;
- create a new automatic BUY signal from a cheaper live article alone.

It only checks high-priority rows already present in `output/core_watch_universe.csv`, currently priorities A/B with a minimum CT-lag score. The default cap is **3 cards per daily run**. Parse currently prices `get_card_listings` at 2 credits per successful call, so three daily calls use about 180 credits in a 30-day month and fit the current 200-credit free tier with a small buffer. The 12.5-second request delay is also below the current free-tier 5-requests/minute rate limit. Raise the cap only when using a paid plan.

Output: `output/cardmarket_live_validation.csv`.

For each checked exact Cardmarket product, the file records the live article floor, a robust median of the cheapest configured sample, visible seller/unit depth, comparison with the previously validated landed source, and a validation state:

- `LIVE_ALIGNED` — current live article evidence is broadly consistent with the previous validated landed source;
- `LIVE_CHEAPER_VERIFY_SHIPPING` — a cheaper article may exist, but shipping/landed cost still needs verification;
- `REVALIDATE_STALE_SOURCE` — current live article evidence has moved materially above the prior source, so actionable CM->CT routes are downgraded pending revalidation;
- `INSUFFICIENT_LIVE_DEPTH` / `NO_LIVE_OFFERS` — not enough evidence.

When the live evidence indicates a stale acquisition source, `market_routes.csv` is changed from `RESELL_TEST`/`WATCH_ONLY` to `REVALIDATE_SOURCE`, and a CardTrader resale candidate is downgraded from `RESELL_TEST` to `WATCH_ONLY`. A lower live article price never upgrades a route automatically.

## Provider-neutral policy

The validation logic is deliberately separate from the provider client. A different live-offer service can replace Parse later while preserving the normalized output and guardrails. Minimum useful fields remain:

- Cardmarket `id_product` / exact product identity;
- language and condition;
- article price;
- seller identity/country where permitted;
- quantity;
- Ireland shipping eligibility and cost when available;
- checked timestamp and provider label.

A future provider that supplies reliable Ireland shipping can feed the existing sourcing/robust-floor layer; until then, live provider data stays verification evidence rather than landed acquisition evidence.

## Operational rule

Use the official Cardmarket feed to screen the whole catalogue, CardTrader/eBay to identify plausible cross-market gaps, and only then spend live-provider requests on the highest-priority exact products. This keeps cost, traffic and false positives bounded.

Official/provider references reviewed on 2026-09-11:

- Cardmarket API help: https://help.cardmarket.com/en/cardmarket-api
- Cardmarket GTC: https://www.cardmarket.com/en/FoW/Policies/GeneralTermsAndConditions
- Cardmarket public price-guide/catalogue announcement: https://news.cardmarket.com/en/Magic/were-making-the-price-guide-and-product-catalogue-available-for-download
- Parse.bot Cardmarket wrapper: https://parse.bot/marketplace/d6eff58a-dd95-45bc-886b-f1cd346d961c/cardmarket-com-api
