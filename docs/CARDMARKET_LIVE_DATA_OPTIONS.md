# Cardmarket live-offer data options

Last reviewed: 2026-09-11

## Why this matters

The scanner's largest Cardmarket data gap is not product identity or daily market pricing; Cardmarket already publishes those through its official downloadable product catalogue and price guide. The missing layer is **live offer-level data filtered to the exact printing, language, condition, seller and Ireland-eligible shipping context**.

That live layer would materially improve Cardmarket -> CardTrader arbitrage because the scanner could verify a real English/NM acquisition price rather than rely on the generic Cardmarket low or manually maintained sourcing rows.

## Current baseline: official Cardmarket downloads

Keep the official product catalogue + daily price guide as the production baseline. They are free, stable and explicitly published by Cardmarket. They provide product IDs, catalogue metadata, low/trend and 1/7/30-day market averages, but the generic low is not English/NM-specific and therefore cannot create an automatic BUY signal.

## Official Cardmarket API

Cardmarket still documents API v2, but its help page currently says it is **not accepting new applications for API access**. Existing API credentials must not be shared with third-party apps. Cardmarket's current GTC also restrict API data use and says presentation of cards/prices requires prior written agreement.

For this project, the official API would be the preferred live-offer source if Cardmarket grants access/permission in future.

## Apify options

There are two materially different kinds of Cardmarket actors on Apify:

1. **Daily market-price actors** that mainly package Cardmarket's published catalogue/price-guide data. These add little value to this project because we already download the same official source directly for free.
2. **Browser/residential-proxy actors** that load Cardmarket product pages and extract live offers. These can technically return useful live information, but they rely on browser automation, residential proxies and anti-bot handling. That is a much less stable and higher-risk production dependency.

Do not add a residential-proxy / Cloudflare-evasion actor to the scheduled scanner merely because it works technically. Third-party infrastructure does not remove Cardmarket contractual/account risk, and a provider can break or disappear without warning.

## Parse.bot Cardmarket wrapper

Parse.bot currently advertises an unofficial Cardmarket wrapper with endpoints for card details and live listings, including listing condition, price, quantity and pagination; it also advertises language/min-condition filters. Technically, this is much closer to the data the scanner actually needs than the daily Apify market-price actor.

However, Parse.bot explicitly describes this as an **independent wrapper over Cardmarket public data**, not Cardmarket's official API. Before using it in production, confirm that the intended use is acceptable under both the provider's terms and Cardmarket's current terms/permissions.

## Recommended integration policy

If a permitted live-offer source becomes available, integrate it behind a provider-neutral interface rather than coupling the scanner to one scraper vendor. Minimum fields:

- Cardmarket `id_product` / exact product identity;
- exact printing / version;
- language;
- condition;
- article price;
- seller country;
- seller rating / sales count when permitted;
- quantity;
- Ireland shipping eligibility and shipping cost when available;
- checked timestamp and source/provider label.

The existing `cardmarket_sourcing_offers.csv` schema and robust-floor logic should remain the normalization layer. A live provider should feed that layer rather than bypassing it.

## Safe pilot if permission/terms are confirmed

Start with an **on-demand, low-volume exact-card validator**, not a whole-site crawler:

- only cards already flagged by the CM/CT gap engine;
- exact product pages only;
- English + NM filters;
- no logged-in Cardmarket cookies or account credentials supplied to the scraping provider;
- cache results and avoid repeated requests within the same day;
- do not store unnecessary seller personal data;
- stop/degrade gracefully on blocks or provider errors;
- compare a sample against manual Cardmarket pages before allowing the data to create BUY signals.

A successful pilot should first produce `VERIFY_LIVE_CM` / `VALIDATED_LIVE_CM` evidence. It should not immediately trigger unattended purchases.

## Current decision

**Do not integrate Apify/Parse/proxy scraping into the scheduled production scanner yet.** The daily price-guide actors are redundant, while the live-offer wrappers are technically useful but need a clearer permission/terms basis before becoming a dependency. The architecture should remain ready to accept a permitted live-offer provider later.

Official references reviewed on 2026-09-11:

- Cardmarket API help: https://help.cardmarket.com/en/cardmarket-api
- Cardmarket GTC / API use: https://www.cardmarket.com/en/Policies/GeneralTermsAndConditions/IT
- Cardmarket public price-guide/catalogue announcement: https://news.cardmarket.com/en/Magic/were-making-the-price-guide-and-product-catalogue-available-for-download
- Cardmarket partner apps/services: https://help.cardmarket.com/en/api-partnerships
