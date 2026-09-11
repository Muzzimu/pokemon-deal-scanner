# Market quality model (v0.9.1)

Last updated: 2026-09-11

v0.9.1 treats Pokémon singles as a fragmented, relatively illiquid financial market rather than assuming that a quoted price is executable. Every covered route can receive three separate 0–100 scores:

- **LQS — Liquidity Quality Score:** how easily the exact printing can realistically trade near fair value.
- **PCS — Price Confidence Score:** how confident the scanner is in the estimated fair market value.
- **ECS — Exit Confidence Score:** how confident the scanner is that the currently selected sell venue can achieve its modeled exit price.

These scores are additional gates. They do not replace exact-printing, English/NM, landed-cost, fee, seller-depth or profit/ROI requirements.

## TCGplayer role and v0.9.1 source semantics

TCGplayer is a **valuation and liquidity confirmation market only**. It is deliberately not used as an automatic Ireland acquisition source and is not selected as an exit venue.

v0.9.1 explicitly separates **transaction evidence** from the **current live order book**:

### Transaction / velocity fields

- `market_price_*` — transaction-derived market reference; can enter global fair value / PCS.
- `most_recent_sale_*` — latest observed realized transaction; freshness/context only, not a second independent fair-value vote.
- `sales_30d`, `sales_90d`, `avg_daily_sold` — realized velocity inputs. The scanner normalizes these to a monthly-equivalent rate.

### Current live supply fields

- `lowest_listing_price_*` — current item price of the cheapest exact-product listing.
- `lowest_listing_shipping_*` — shipping attached to that same listing when known.
- `executable_floor_*` — item + displayed shipping when both are known.
- `current_quantity` — exact product's current available quantity.
- `current_sellers` — exact product's current seller count.

A legacy/provider field named `listing_count` is retained for audit/backwards compatibility but is **never used as exact live depth**, because search/provider result counts can differ from the exact product page's current quantity.

This means a card can correctly be classified as **high velocity + thin current supply**. Example: 107 sales in three months with only 4 copies from 2 sellers is a liquid card experiencing a tight live order book, not an illiquid card.

The scanner additionally reports `tcgplayer_supply_coverage_days` and classifies live supply as `TIGHT`, `BALANCED`, `DEEP`, `NO_LIVE_SUPPLY`, `DEPTH_ONLY` or `UNKNOWN`.

The normalized input remains `data/reference/tcgplayer_market_reference.csv`, keyed to canonical Cardmarket `id_product`. Exact-ID mapping remains mandatory; name/collector-number-only provider rows are rejected by the importer.

If only USD values are supplied and no row-level FX is present, the configured USD->EUR fallback is used. Because TCGplayer and US eBay demand are correlated, TCGplayer receives a discounted market-breadth weight rather than being treated as a fully independent second US market.

## Global fair value versus executable value

`fair_value_eur` is explicitly scoped as **`GLOBAL_TRANSACTIONAL`**. It is a weighted median of transaction/market evidence and is not intended to answer "what would it cost me to replace this card in Europe right now?"

Current live asks are kept separate:

- TCGplayer `executable_floor` is live US supply context and may include displayed domestic shipping; it is not an Ireland-landed acquisition price.
- When the targeted live Cardmarket validator has at least two English/NM sellers, `eu_executable_value_eur` exposes the robust live Cardmarket article floor as **European replacement context**. It remains an article-price reference rather than confirmed Ireland-landed cost until shipping is independently known.

This separation prevents a temporary supply squeeze from being confused with realized fair value and prevents a historical market price from being mistaken for the price a buyer can actually execute today.

## Fair value

Global transactional fair value is a **weighted median**, not an arithmetic average. This reduces the impact of one optimistic CardTrader seller or another single-market outlier.

Default evidence weights are approximately:

- Cardmarket trend: 1.00;
- strong eBay resale evidence: 1.20 (lower for weaker evidence);
- strong TCGplayer transaction market reference: 0.95 (lower for weaker evidence);
- CardTrader active exit ask: 0.10–0.50 depending on competing-seller depth.

TCGplayer live listing floor is **not** added as another fair-value point. The most recent sale is also not double-counted as an independent market when Market Price already summarizes TCGplayer transactions.

Cross-market dispersion is the weighted median absolute percentage deviation from global transactional fair value. Lower dispersion increases both liquidity and price confidence.

## LQS — Liquidity Quality Score

LQS uses a market-microstructure-style 100-point model:

- **Velocity — 30 points:** confirmed eBay sales plus TCGplayer realized monthly-equivalent sales, with inferred eBay quick sales discounted.
- **Depth — 25 points:** CardTrader competing sellers/units plus **TCGplayer current sellers/current quantity**. Legacy `listing_count` contributes zero points.
- **Spread/convergence — 20 points:** tighter cross-market transaction pricing receives more points; wide disagreement is treated like a wide effective spread.
- **Market breadth — 15 points:** Cardmarket, CardTrader, eBay and TCGplayer coverage, with TCGplayer discounted for correlation with US eBay.
- **Immediacy — 10 points:** evidence that comparable copies actually transact rather than merely being listed.

Labels:

- 85–100: `EXTREMELY_LIQUID`
- 70–84: `HIGH`
- 55–69: `MODERATE`
- 40–54: `THIN`
- below 40: `ILLIQUID`

A tight current order book does not erase strong realized velocity. It reduces the depth component while transaction volume continues to support velocity/immediacy.

## PCS — Price Confidence Score

PCS uses:

- **Cross-market convergence — 35 points**
- **Transaction evidence — 25 points**
- **Freshness — 15 points**
- **Liquidity — 15 points**
- **Identity/mapping quality — 10 points**

Exact or human-verified CardTrader->Cardmarket mappings receive full identity credit. Ambiguous mappings are already blocked by the mapping guard and therefore cannot create a CardTrader arbitrage route.

TCGplayer can increase PCS when its transaction market agrees with Cardmarket/eBay/CT, but a high live listing floor by itself cannot increase PCS as if it were a realized sale.

## ECS — Exit Confidence Score

ECS is specific to the currently modeled sell channel.

For CardTrader exits, it combines:

- seller/unit depth (40 points);
- alignment of the selected CT gross exit with global transactional fair value (35 points);
- overall LQS (15 points);
- confirmation from **transactional** eBay/TCGplayer evidence (10 points).

The TCGplayer executable listing floor is intentionally not allowed to validate a high CardTrader exit by itself. An active ask can corroborate a supply squeeze, but it is not equivalent to a completed transaction.

For eBay exits, the depth component is based on evidence strength and confirmed sales rather than CardTrader order-book depth.

A card can therefore have **high PCS but low ECS**. Example: CM/eBay/TCGplayer transactions imply EUR 60 while a thin CardTrader market asks EUR 95. The scanner may be highly confident that fair value is near EUR 60 while having low confidence that EUR 95 is an executable exit.

## Quality gates

Default standard route gate:

- LQS >= 65
- PCS >= 75
- ECS >= 65

For acquisition cost >= EUR 50:

- LQS >= 70
- PCS >= 80
- ECS >= 70

A route that previously qualified as `RESELL_TEST` but fails the applicable quality gate is downgraded to `WATCH_ONLY`. The market-quality layer never upgrades a weaker signal to `RESELL_TEST`; it is a risk-control layer, not a signal generator.

Existing price-band rules continue to apply independently, including the EUR 50–100 requirement for at least EUR 15 expected net profit and 25% ROI.

## Outputs

`output/market_quality.csv`, `output/market_routes.csv` and `output/core_watch_universe.csv` now expose:

- global transactional fair value and scope;
- cross-market dispersion;
- optional current European EN/NM executable article context;
- TCGplayer Market Price and most recent sale separately;
- TCGplayer exact current quantity/sellers separately from legacy listing count;
- TCGplayer item price, shipping and executable floor separately;
- normalized monthly sales velocity;
- supply coverage days/state;
- LQS/PCS/ECS and labels;
- gate profile/pass/failure reason.

The final route decision remains approximately:

`economic edge × price confidence × liquidity × exit confidence`

rather than simply `sell price - buy price`.
