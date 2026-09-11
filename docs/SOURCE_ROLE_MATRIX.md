# Source × role matrix

Last updated: 2026-09-11

This document defines what each external source is allowed to mean inside the Pokémon deal scanner. The machine-readable mirror is `data/reference/source_role_matrix.csv`.

The purpose is to keep three questions separate for every card the scanner can evaluate:

1. **Where can I buy it cheapest?** — acquisition evidence must be landed or explicitly marked as not yet landed.
2. **What is it actually worth?** — valuation prefers robust cross-market evidence rather than a single active ask.
3. **Where should I sell it?** — compare expected net proceeds, liquidity and exit confidence rather than headline prices.

## Source roles

| Source | Buy | Value | Sell | Bundle/local context | Data path |
| --- | --- | --- | --- | --- | --- |
| Cardmarket | Primary | Primary | Secondary | — | Official catalogue + price-guide downloads; manually/externally validated EN/NM Ireland-eligible landed offers |
| Cardmarket live validator | Verification only | Supporting context | — | — | Low-volume exact-product third-party REST lookup; article price is never treated as Ireland-landed cost without shipping evidence |
| CardTrader | Secondary | Secondary | **Primary test from v0.8** | — | Official CardTrader API v2 marketplace offers, mapped to Cardmarket product IDs |
| **TCGplayer** | — | **Valuation/liquidity confirmation** | — in v0.9 | — | Normalized exact-product reference CSV containing market/low price, listing depth and sales velocity when available |
| eBay Browse API | — | Secondary | Primary | — | Official active-listing API with item-location checks and regional separation |
| eBay Product Research | — | Primary sold evidence | Primary sold evidence | — | Manual Seller Hub research, normalized into reference CSVs |
| Adverts.ie | Primary local | Local context | Secondary local | Primary | User-supplied pages/screenshots + public-index discovery; no direct automated scraper |
| Gumtree UK/NI | Primary | Secondary | — | — | Automated defensive public-result retrieval with exact-printing gate |
| Vinted | Secondary | Bundle-demand context | Secondary | Primary | Manual/public-index sold-state research |
| DoneDeal | Secondary | Irish asking context | — | Secondary | Manual only |
| Facebook Marketplace | Primary local | Local context | Secondary local | Primary | Manual/user-supplied evidence |
| Public web/search indexes | Discovery only | Context only | — | Discovery | Search/index/archives; never promoted to confirmed sold evidence by themselves |
| Frankfurter / ECB-derived FX | — | Support | — | — | Live currency conversion only |

## CardTrader resale / exit policy (v0.8)

CardTrader is no longer treated only as a source of cheap inventory. The same official marketplace data is also used to estimate whether an English/NM card could be sold competitively on **CardTrader Direct** or **CardTrader Zero**.

The scanner does **not** call active CardTrader listings confirmed sale prices. For each mapped card it records the current English/NM competitive floor and models an exit price just below that floor by the configured undercut amount. A resale test becomes actionable only when there is enough competing-seller depth and the net spread/ROI survives CardTrader seller fees plus configured operating reserves.

Current default EU seller-fee assumptions are intentionally conservative for a new seller account:

- Direct: **5.3%** seller commission;
- CardTrader Zero: **7.3%** seller commission;
- VAT is added to those commissions; the Ireland-tuned default is **23%**;
- minimum commission is 1 cent before VAT;
- Direct and Zero also have configurable small operational reserves so postage/materials/hub shipment are not silently treated as free.

These values are planning assumptions and are configurable in `config.yaml`.

## v0.8.1 risk and lag intelligence

v0.8.1 adds two controls on top of the base CardTrader exit model.

First, the scanner uses **price-band profit gates** rather than one universal hurdle. The configured defaults are:

- €0–10 acquisition: at least €2.50 net spread and 35% ROI;
- €10–30: at least €5 and 30%;
- €30–50: at least €8 and 25%;
- €50–100: at least €15 and 25%;
- €100+: at least €25 and 20%, plus mandatory human verification before action.

Second, Cardmarket -> CardTrader gaps receive a **0–100 CT lag score**. The score combines the net price gap, number of competing CT sellers, visible CT units and eBay confirmation. This is intentionally designed to distinguish a broad price dislocation from one isolated optimistic CardTrader seller.

The scanner also writes `output/core_watch_universe.csv`: an evidence-driven watch universe for covered cards in the configured value range with sufficient CT depth and cross-market confirmation.

## v0.8.2 targeted live Cardmarket validation

The Core watch universe is also the budget/rate-limit gate for optional live Cardmarket offer validation. The current provider implementation is Parse.bot's public Cardmarket wrapper, but the normalized validation logic is provider-neutral.

Only high-priority exact Cardmarket product IDs are queried. English/NM article prices can confirm that the previous sourcing evidence is still plausible or show that it needs revalidation. They cannot establish a new Ireland-landed BUY by themselves because shipping is not part of the current live-provider evidence.

## v0.9 TCGplayer and market-quality model

TCGplayer is intentionally added as a **fourth valuation/liquidity leg**, not as another automatic sourcing or exit market. The canonical join remains Cardmarket `id_product`; collector number and card name are supporting validation, not the primary key.

The scanner computes three 0–100 quality scores:

- **LQS — Liquidity Quality Score:** velocity, visible depth, cross-market spread/convergence, market breadth and immediacy.
- **PCS — Price Confidence Score:** cross-market convergence, transaction evidence, freshness, liquidity and mapping/identity quality.
- **ECS — Exit Confidence Score:** confidence that the selected sell channel can actually achieve its modeled gross exit price.

TCGplayer is correlation-discounted against US eBay so the two are not counted as fully independent markets. A high CT price that disagrees with Cardmarket/eBay/TCGplayer may therefore leave PCS high around the lower fair value while driving CT exit confidence sharply lower.

The standard quality gate is LQS ≥65 / PCS ≥75 / ECS ≥65. For acquisition cost ≥€50 it becomes LQS ≥70 / PCS ≥80 / ECS ≥70. A failing gate can downgrade `RESELL_TEST` to `WATCH_ONLY`; this layer never upgrades a weak route.

See `docs/MARKET_QUALITY_MODEL.md` for the scoring detail.

## Market-route output

`output/market_routes.csv` represents cards for which the project has validated Cardmarket landed sourcing evidence and then shows:

- validated buy source and landed/risk-adjusted cost;
- CardTrader observed English/NM article floor;
- Cardmarket trend value;
- eBay expected resale reference when available;
- TCGplayer supporting reference when available;
- robust weighted-median fair value and cross-market dispersion;
- CardTrader Direct and Zero gross/net exit estimates;
- eBay gross/net exit estimate when available;
- the best modeled sell channel after fees/reserves;
- price-band requirements and manual-verification flag;
- CT/CM lag metrics;
- optional live Cardmarket validation fields;
- LQS/PCS/ECS market-quality scores and quality-gate result;
- net spread, ROI, route signal and confidence.

The route file deliberately distinguishes **validated landed cost** from **observed marketplace article price**. CardTrader, TCGplayer or a third-party Cardmarket live feed can therefore be visibly cheaper/more expensive without automatically becoming an acquisition route.

## Evidence discipline

- Cardmarket generic low remains discovery-only.
- Exact printing, language and condition must match before an actionable route is emitted.
- Third-party Cardmarket live article prices are verification evidence, not Ireland-landed acquisition evidence.
- CardTrader and eBay active asks are not sold evidence.
- eBay Product Research / confirmed sold evidence outranks active-market asks for valuation.
- TCGplayer is confirmation evidence only in v0.9 and is correlation-discounted against eBay.
- Local-platform accepted offers and sold markers retain their existing evidence hierarchy.
- A high CardTrader price relative to Cardmarket is a **cross-market resale hypothesis**, not proof that the card will sell quickly.
- Higher capital at risk requires larger absolute expected profit; percentage ROI alone is insufficient.
