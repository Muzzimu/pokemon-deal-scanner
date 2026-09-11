# Market quality model (v0.10)

Last updated: 2026-09-11

v0.10 treats Pokémon singles as a **segmented international market**, not one frictionless global exchange. For an Ireland-based buyer, Cardmarket is the main European price-discovery venue, TCGplayer is primarily a US-market reference, and CardTrader can act as a bridge between those markets.

## Core market structure

The scanner now maintains three separate concepts:

1. **EU Fair Value (EFV)** — what the exact printing is worth in the European/Ireland-facing market.
2. **US Fair Value (UFV)** — what the exact printing is worth in the US/global reference market.
3. **Bridge Opportunity Score (BOS)** — whether buying from the EU side and selling through CardTrader is supported by real US/global demand rather than a thin CardTrader ask.

TCGplayer no longer moves EU fair value directly.

## EU Fair Value

EU Fair Value is built only from European evidence:

- Cardmarket trend/history;
- live English/NM Cardmarket article pricing when enough seller depth is available;
- eBay Ireland / continental-EU evidence, with confirmed sold evidence weighted above active asks.

`fair_value_eur` remains in output for backward compatibility, but from v0.10 it means **EU Fair Value** and `fair_value_scope` is `EU_TRANSACTIONAL`.

Live Cardmarket English/NM article prices remain current replacement context rather than automatically becoming an Ireland-landed BUY. Shipping and landed cost still require separate validation.

## US Fair Value

US Fair Value is built separately from:

- TCGplayer Market Price;
- TCGplayer most recent sale when available;
- US/global eBay evidence from the project's `GLOBAL`/EBAY_US leg.

TCGplayer current sellers, current quantity and item+shipping floor remain live US order-book context. They do not become an Ireland acquisition route.

The `GLOBAL` eBay leg is treated as US/global context, not pure US-local evidence, because this project does not force physical item location for that leg.

## TCGplayer role

TCGplayer's importance is deliberately reduced for normal Irish/EU deal evaluation.

It now primarily answers:

> **Does the US/global market support the CardTrader price we hope to sell at?**

A low TCGplayer value can no longer drag an otherwise well-supported Cardmarket/EU eBay fair value down. Instead, it can reduce CardTrader exit confidence and the Bridge Opportunity Score.

TCGplayer transaction and live-order-book fields remain separated:

- Market Price / recent sale → US fair value and US price confidence;
- 30d/90d sales / avg daily sold → US liquidity velocity;
- current quantity / current sellers → exact live US depth;
- lowest item + shipping → current US executable ask context;
- legacy `listing_count` → audit only, never exact-product depth.

## Regional confidence and liquidity

The legacy output fields remain for compatibility, but their meaning changes:

- `liquidity_score` = **EU liquidity score** for an Ireland-based buyer;
- `price_confidence_score` = **EU price-confidence score**;
- `fair_value_eur` = **EU fair value**.

New explicit fields include:

- `eu_fair_value_eur`;
- `eu_price_confidence_score`;
- `eu_dispersion_pct`;
- `us_fair_value_eur`;
- `us_price_confidence_score`;
- `us_liquidity_score`;
- `us_dispersion_pct`.

This prevents a liquid US card from being automatically labelled equally liquid in Europe, or vice versa.

## CardTrader as bridge market

CardTrader remains a modeled exit venue, but its higher price is now treated as a **bridge hypothesis**.

For a CardTrader exit, the scanner asks:

- Is the EU acquisition price attractive after landed cost?
- Does CardTrader have enough competing sellers and units?
- Is the CardTrader gross exit reasonably close to US Fair Value?
- Are US price confidence and US liquidity strong enough to support that comparison?
- Does the route still clear the configured net-profit and ROI thresholds?

A high CardTrader ask that is unsupported by TCGplayer / US-global eBay receives a large discount in the bridge score even when the nominal CM→CT spread looks large.

## BOS — Bridge Opportunity Score (0–100)

BOS combines five components:

- **Economic edge — 35 points:** expected net spread and ROI versus the route's price-band hurdle;
- **US/global confirmation — 25 points:** alignment of CardTrader gross exit with US Fair Value, confidence-adjusted;
- **CardTrader depth — 20 points:** competing sellers and units on the selected Direct/Zero channel;
- **EU acquisition confidence — 10 points:** EU price-confidence contribution;
- **Market liquidity — 10 points:** EU + US liquidity contribution.

The total is then multiplied by a **US-support factor**. This is deliberate: a large nominal EU→CT price gap cannot compensate for an exit price that the US/global market does not support.

Labels:

- 85–100: `STRONG_BRIDGE`
- 70–84: `GOOD_BRIDGE`
- 55–69: `WATCH`
- below 55: `WEAK_OR_UNSUPPORTED`

## ECS — Exit Confidence Score

ECS remains venue-specific.

For CardTrader exits, it now emphasizes:

- CT seller/unit depth;
- alignment with **US Fair Value** when available;
- US and EU liquidity;
- BOS confirmation.

If no US reference is available, EU value can provide only a weak sanity check. This deliberately prevents an unsupported CardTrader premium from looking highly executable.

For eBay exits, the existing evidence-strength and confirmed-sale logic remains, with EU fair value used as the price-alignment anchor for an Ireland-based buyer.

## Quality gates

Standard route gate:

- EU-LQS >= 65
- EU-PCS >= 75
- ECS >= 65
- CardTrader routes additionally require BOS >= 65

For acquisition cost >= EUR 50:

- EU-LQS >= 70
- EU-PCS >= 80
- ECS >= 70
- CardTrader routes additionally require BOS >= 70

Existing price-band requirements still apply independently. A quality failure can only downgrade `RESELL_TEST` to `WATCH_ONLY`; it cannot promote a weak route.

## Example

If:

- Cardmarket/EU value = EUR 100
- CardTrader Zero gross exit = EUR 135
- TCGplayer + US-global eBay = EUR 130

then the CardTrader premium is plausibly supported and BOS can be high.

If instead:

- Cardmarket/EU value = EUR 100
- CardTrader Zero gross exit = EUR 135
- TCGplayer + US-global eBay = EUR 102

then EU fair value stays near EUR 100, but BOS and CT ECS are sharply reduced. The scanner should report the CardTrader price as an unsupported bridge premium rather than a EUR 35 arbitrage opportunity.

## Outputs

`output/market_quality.csv`, `output/market_routes.csv` and `output/core_watch_universe.csv` now expose:

- EU fair value / EU confidence / EU liquidity;
- US fair value / US confidence / US liquidity;
- CardTrader premium versus EU and US values;
- BOS and BOS label;
- venue-specific ECS;
- existing TCGplayer transaction/order-book diagnostics;
- final quality-gate decision.

The resulting decision model is now approximately:

`EU entry edge × EU price confidence × EU liquidity × selected-exit confidence × bridge support (when CT is the exit)`

rather than one blended global price.
