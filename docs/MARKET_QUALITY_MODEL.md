# Market quality model (v0.9)

Last updated: 2026-09-11

v0.9 treats Pokémon singles as a fragmented, relatively illiquid financial market rather than assuming that a quoted price is executable. Every covered route can now receive three separate 0–100 scores:

- **LQS — Liquidity Quality Score:** how easily the exact printing can realistically trade near fair value.
- **PCS — Price Confidence Score:** how confident the scanner is in the estimated fair market value.
- **ECS — Exit Confidence Score:** how confident the scanner is that the currently selected sell venue can achieve its modeled exit price.

These scores are additional gates. They do not replace exact-printing, English/NM, landed-cost, fee, seller-depth or profit/ROI requirements.

## TCGplayer role

TCGplayer is a **valuation and liquidity confirmation market only** in v0.9. It is deliberately not used as an automatic acquisition source and is not selected as an exit venue.

The normalized input is `data/reference/tcgplayer_market_reference.csv`, keyed to the canonical Cardmarket `id_product`. This avoids fragile name-only or collector-number-only joins. The file can be populated manually or by a permitted provider and supports:

- TCGplayer product ID;
- market and low prices in USD or EUR;
- explicit USD->EUR rate when known;
- visible listing count;
- observed/derived 30-day sales count when available;
- reference strength and checked date;
- source/notes.

If only USD price is supplied and no row-level FX is present, the configured USD->EUR fallback is used. Because TCGplayer and US eBay demand are correlated, TCGplayer receives a discounted market-breadth weight instead of being treated as a fully independent second US vote.

## Fair value

Fair value is a **weighted median**, not an arithmetic average. This reduces the impact of one optimistic CardTrader seller or another single-market outlier.

Default evidence weights are approximately:

- Cardmarket trend: 1.00;
- strong eBay resale evidence: 1.20 (lower for weaker evidence);
- strong TCGplayer reference: 0.95 (lower for weaker evidence);
- CardTrader active exit ask: 0.10–0.50 depending on competing-seller depth.

CardTrader active asks therefore cannot dominate fair value merely because they are high.

Cross-market dispersion is the weighted median absolute percentage deviation from the weighted-median fair value. Lower dispersion increases both liquidity and price confidence.

## LQS — Liquidity Quality Score

LQS uses a market-microstructure-style 100-point model:

- **Velocity — 30 points:** confirmed eBay sales + TCGplayer 30-day sales, with inferred eBay quick sales discounted.
- **Depth — 25 points:** CardTrader competing sellers/units plus TCGplayer listing depth.
- **Spread/convergence — 20 points:** tighter cross-market pricing receives more points; wide disagreement is treated like a wide effective spread.
- **Market breadth — 15 points:** Cardmarket, CardTrader, eBay and TCGplayer coverage, with TCGplayer discounted for correlation with US eBay.
- **Immediacy — 10 points:** evidence that comparable copies actually transact rather than merely being listed.

Labels:

- 85–100: `EXTREMELY_LIQUID`
- 70–84: `HIGH`
- 55–69: `MODERATE`
- 40–54: `THIN`
- below 40: `ILLIQUID`

## PCS — Price Confidence Score

PCS uses:

- **Cross-market convergence — 35 points**
- **Transaction evidence — 25 points**
- **Freshness — 15 points**
- **Liquidity — 15 points**
- **Identity/mapping quality — 10 points**

Exact or human-verified CardTrader->Cardmarket mappings receive full identity credit. Ambiguous mappings are already blocked by the mapping guard and therefore cannot create a CardTrader arbitrage route.

TCGplayer can increase PCS when it agrees with Cardmarket/eBay/CT, but it can also reduce practical arbitrage confidence by demonstrating that a high CardTrader ask is an outlier.

## ECS — Exit Confidence Score

ECS is specific to the currently modeled sell channel.

For CardTrader exits, it combines:

- seller/unit depth (40 points);
- alignment of the selected CT gross exit with robust fair value (35 points);
- overall LQS (15 points);
- confirmation from eBay/TCGplayer (10 points).

For eBay exits, the depth component is based on evidence strength and confirmed sales rather than CardTrader order-book depth.

A card can therefore have **high PCS but low ECS**. This is intentional. Example: CM/eBay/TCGplayer all imply EUR 60 while one thin CardTrader listing asks EUR 95. The scanner may be highly confident that fair value is near EUR 60 while having very low confidence that EUR 95 is an executable exit.

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

`output/market_quality.csv` contains the scorecard per route. `output/market_routes.csv` and `output/core_watch_universe.csv` are enriched with the same core fields:

- fair value;
- dispersion;
- TCGplayer reference/depth/velocity fields;
- LQS/PCS/ECS and labels;
- gate profile/pass/failure reason.

This makes the final route decision approximately:

`economic edge × price confidence × liquidity × exit confidence`

rather than simply `sell price - buy price`.
