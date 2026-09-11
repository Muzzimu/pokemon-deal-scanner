# Source × role matrix

Last updated: 2026-09-11

This document defines what each external source is allowed to mean inside the Pokémon deal scanner. The machine-readable mirror is `data/reference/source_role_matrix.csv`.

The core v0.10 principle is that Pokémon is a **segmented international market**. For an Ireland-based buyer, EU and US price discovery must not be blended mechanically.

## The three market layers

1. **EU market** — Cardmarket plus Ireland/continental-EU eBay evidence. This drives the main fair value and deal assessment for an Ireland-based buyer.
2. **US/global reference market** — TCGplayer plus the scanner's `GLOBAL`/EBAY_US evidence. This is kept separate from EU fair value.
3. **Bridge market** — CardTrader. Its price is evaluated as a possible route between EU acquisition and global/US demand rather than as another independent fair-value vote.

## Source roles

| Source | Buy | Value | Sell | Main v0.10 role |
| --- | --- | --- | --- | --- |
| Cardmarket | Primary | **Primary EU** | Secondary | EU price discovery and sourcing baseline |
| Cardmarket live validator | Verification only | Supporting EU context | — | English/NM current article depth/replacement context |
| CardTrader | Secondary | Bridge context | **Primary test** | Cross-border bridge; premium must be supported by US/global evidence |
| TCGplayer | — | **Primary US confirmation** | — | US fair value, US liquidity, CT bridge validation |
| eBay Ireland/EU | — | Regional EU secondary/primary sold evidence | Primary | EU transaction/supply context |
| eBay GLOBAL / EBAY_US | — | US/global confirmation | Primary | US/global transaction/supply context for bridge validation |
| Adverts.ie | Primary local | Local context | Secondary local | Irish sourcing / local benchmark |
| Gumtree UK/NI | Primary | Secondary | — | Local/UK sourcing with friction controls |
| Vinted | Secondary | Bundle/local context | Secondary | Consumer bundle demand and selected singles |
| DoneDeal | Secondary | Irish context | — | Manual Irish sourcing context |
| Facebook Marketplace | Primary local | Local context | Secondary local | User-supplied local deal evidence |
| Public search indexes | Discovery only | Context only | — | Discovery/corroboration only |
| Frankfurter/ECB FX | — | Support | — | Currency conversion |

## EU deal assessment

For an Ireland-based single-card purchase, **TCGplayer must not drag EU fair value up or down**.

EU fair value uses:

- Cardmarket trend/history;
- live Cardmarket English/NM article evidence when sufficiently deep;
- eBay Ireland / continental-EU evidence, with confirmed sales above inferred sales and asks.

`fair_value_eur`, `price_confidence_score`, and `liquidity_score` remain as backward-compatible output fields, but from v0.10 they mean:

- **EU fair value**;
- **EU price confidence**;
- **EU liquidity**.

## US/global reference

TCGplayer and the `GLOBAL`/EBAY_US leg form a separate US/global reference.

TCGplayer fields are deliberately split:

- Market Price / most recent sale → US fair value / US price confidence;
- 30d/90d sales / avg daily sold → US sales velocity;
- current quantity / current sellers → exact live US depth;
- lowest item price + shipping → current US ask context;
- legacy `listing_count` → audit only.

This reference is mainly used to answer whether a CardTrader exit price has real international support.

## CardTrader bridge policy

CardTrader active prices are not fair-value votes and are not sold-price evidence.

A CardTrader route must satisfy:

- validated EU acquisition economics;
- configured profit/ROI hurdle;
- sufficient CT seller/unit depth;
- selected-exit confidence;
- **Bridge Opportunity Score (BOS)**.

BOS combines the economic edge, US/global support for the CT price, CT depth, EU acquisition confidence and liquidity. A large nominal CM→CT spread that is not supported by TCGplayer / US-global eBay is heavily discounted.

Default BOS gates:

- standard CardTrader route: **BOS ≥65**;
- acquisition cost ≥€50: **BOS ≥70**.

## Evidence discipline

- Cardmarket generic low remains discovery-only.
- Exact printing, language and condition must match before an actionable route is emitted.
- Third-party Cardmarket live article prices are not Ireland-landed buys without shipping evidence.
- Active CardTrader/eBay/TCGplayer asks are not confirmed sales.
- TCGplayer is US-market confirmation, not an EU acquisition valuation input.
- UK is not silently merged into EU evidence.
- `GLOBAL` eBay is explicitly US/global context, not guaranteed US-local physical-location evidence.
- CardTrader multi-ID mappings remain blocked from arbitrage until exact Cardmarket mapping is resolved.

See `docs/MARKET_QUALITY_MODEL.md` for the v0.10 scoring model.
