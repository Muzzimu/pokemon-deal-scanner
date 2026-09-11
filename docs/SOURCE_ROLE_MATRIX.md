# Source × role matrix

Last updated: 2026-09-11

This document defines what each external source is allowed to mean inside the Pokémon deal scanner. The machine-readable mirror is `data/reference/source_role_matrix.csv`.

The purpose is to keep three questions separate for every card the scanner can evaluate:

1. **Where can I buy it cheapest?** — acquisition evidence must be landed or explicitly marked as not yet landed.
2. **What is it actually worth?** — valuation prefers Cardmarket market history and stronger eBay sold evidence; active asks remain weaker context.
3. **Where should I sell it?** — compare expected net proceeds after platform fees and operating reserves rather than comparing headline prices.

## Source roles

| Source | Buy | Value | Sell | Bundle/local context | Data path |
| --- | --- | --- | --- | --- | --- |
| Cardmarket | Primary | Primary | Secondary | — | Official catalogue + price-guide downloads; manually/externally validated EN/NM Ireland-eligible landed offers |
| CardTrader | Secondary | Secondary | **Primary test from v0.8** | — | Official CardTrader API v2 marketplace offers, mapped to Cardmarket product IDs |
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

These values are planning assumptions and are configurable in `config.yaml`. Official fee source: `https://static.cardtrader.com/it/pages/payments-fees-and-refunds`.

## v0.8.1 risk and lag intelligence

v0.8.1 adds two controls on top of the base CardTrader exit model.

First, the scanner uses **price-band profit gates** rather than one universal hurdle. The configured defaults are:

- €0–10 acquisition: at least €2.50 net spread and 35% ROI;
- €10–30: at least €5 and 30%;
- €30–50: at least €8 and 25%;
- €50–100: at least €15 and 25%;
- €100+: at least €25 and 20%, plus mandatory human verification before action.

Second, Cardmarket -> CardTrader gaps receive a **0–100 CT lag score**. The score combines the net price gap, number of competing CT sellers, visible CT units and eBay confirmation. This is intentionally designed to distinguish a broad price dislocation from one isolated optimistic CardTrader seller.

The scanner also writes `output/core_watch_universe.csv`: an evidence-driven watch universe for covered cards in the configured value range with sufficient CT depth and cross-market confirmation. It is not a fixed list of famous Pokémon and it is not claimed to be a complete market-liquidity ranking.

## Market-route output

`output/market_routes.csv` represents cards for which the project has validated Cardmarket landed sourcing evidence and then shows:

- validated buy source and landed/risk-adjusted cost;
- CardTrader observed English/NM article floor (not landed acquisition cost);
- Cardmarket trend value;
- eBay expected resale reference when available;
- CardTrader Direct and Zero gross/net exit estimates;
- eBay gross/net exit estimate when available;
- the best modeled sell channel after fees/reserves;
- price-band requirements and manual-verification flag;
- CT/CM lag metrics;
- net spread, ROI, route signal and confidence.

The route file deliberately distinguishes **validated landed cost** from **observed marketplace article price**. CardTrader can therefore be visibly cheaper than Cardmarket without automatically becoming the chosen acquisition route until its buyer-side landed cost is known.

## Evidence discipline

- Cardmarket generic low remains discovery-only.
- Exact printing, language and condition must match before an actionable route is emitted.
- CardTrader and eBay active asks are not sold evidence.
- eBay Product Research / confirmed sold evidence outranks active-market asks for valuation.
- Local-platform accepted offers and sold markers retain their existing evidence hierarchy.
- A high CardTrader price relative to Cardmarket is a **cross-market resale hypothesis**, not proof that the card will sell quickly.
- Higher capital at risk requires larger absolute expected profit; percentage ROI alone is insufficient.
