# Source × role matrix

Last updated: 2026-09-12

This document defines what each external source is allowed to mean inside the Pokémon deal scanner. The machine-readable mirror is `data/reference/source_role_matrix.csv`.

The core v0.10 principle is that Pokémon is a **segmented international market**. For an Ireland-based buyer, EU and US price discovery must not be blended mechanically.

## The three market layers

1. **EU market** — Cardmarket plus Ireland/continental-EU eBay evidence. This drives the main fair value and deal assessment for an Ireland-based buyer.
2. **US/global reference market** — TCGplayer plus the scanner's `GLOBAL`/EBAY_US evidence. This is kept separate from EU fair value.
3. **Bridge market** — CardTrader. Its price is evaluated as a possible route between EU acquisition and global/US demand rather than as another independent fair-value vote.

## Source roles

| Source | Buy | Value | Sell | Main v0.12 role |
| --- | --- | --- | --- | --- |
| Cardmarket | Primary | **Primary EU** | Secondary | EU price discovery and sourcing baseline |
| Cardmarket live validator | Verification only | Supporting EU context | — | English/NM current article depth/replacement context |
| CardTrader | Secondary | Bridge context | **Primary test** | Cross-border bridge; premium must be supported by US/global evidence |
| TCGplayer | — | **Primary US confirmation** | — | US fair value, US liquidity, CT bridge validation |
| TCGCSV | — | **Primary US market cache** | — | Automated cached TCGplayer-derived Market Price; proxy only, exact bridge required |
| eBay Ireland/EU | — | Regional EU secondary/primary sold evidence | Primary | EU transaction/supply context |
| eBay GLOBAL / EBAY_US | — | US/global confirmation | Primary | US/global transaction/supply context for bridge validation |
| **eBay ScrapeBadger completed pilot** | — | **Research only** | Research liquidity | Candidate completed/sold observations; same underlying eBay market, not a second price vote |
| Adverts.ie | Primary local | Local context | Secondary local | Irish sourcing / local benchmark |
| Gumtree UK/NI | Primary | Secondary | — | Local/UK sourcing with friction controls |
| Vinted | Secondary | Bundle/local context | Secondary | Consumer bundle demand and selected singles |
| **Vinted ScrapeBadger pilot** | Discovery research | **No fair-value role** | Research diagnostic | Category-filtered discovery plus prospective listing-state history |
| DoneDeal | Secondary | Irish context | — | Manual Irish sourcing context |
| Facebook Marketplace | Primary local | Local context | Secondary local | User-supplied local deal evidence |
| Public search indexes | Discovery only | Context only | — | Discovery/corroboration only |
| Frankfurter/ECB FX | — | Support | — | Currency conversion |

## ScrapeBadger research pilots

The 2026-09-12 ScrapeBadger integration is deliberately **outside production valuation and BUY logic**. It uses an isolated research database (`db/scrapebadger_research.sqlite`) and a separate scheduled/manual workflow.

### eBay completed pilot

Initial source role: `EBAY_COMPLETED_CANDIDATE`.

Rules:

- the official eBay Browse API remains the production active-listing/supply collector;
- ScrapeBadger completed rows represent the **same underlying eBay market**, so they are never an independent second price vote;
- exact-print matching remains mandatory;
- Best Offer rows keep sold-state evidence separate from price confidence because the displayed completed price may not equal the confidential accepted offer;
- physical item location is retained as context but is not assumed from marketplace domain alone;
- candidate rows begin as research/liquidity evidence with zero production valuation weight;
- manual validation and deduplication against eBay Product Research/manual sold evidence are required before any promotion.

### Vinted pilot

Initial research roles:

- `VINTED_ACTIVE_DISCOVERY`;
- `VINTED_LOT_DISCOVERY`;
- `VINTED_RESALE_DIAGNOSTIC`;
- `VINTED_CLOSED_STATE_UNPRICED`.

Rules:

- use category-filtered Vinted Ireland searches where possible;
- exact card identity, language and condition remain untrusted until detail-level validation;
- Vinted generic conditions such as `Very good` must not be silently converted to Pokémon `NM`;
- public search visibility is not executable proof: selected candidates receive detail-state checks;
- `is_closed`, disappearance or removal never becomes a confirmed realised price automatically;
- Buyer Protection and checkout-dependent shipping remain acquisition friction, not fair value;
- Vinted asks and closed-state observations have zero production valuation weight during the pilot;
- prospective state history may later support liquidity/time-to-sale research if status semantics validate.

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
- Research-provider rows remain research rows until their documented acceptance gates are met; availability alone never promotes them into fair value or BUY logic.

See `docs/MARKET_QUALITY_MODEL.md` for the v0.10 scoring model.
