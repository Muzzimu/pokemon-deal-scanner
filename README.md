# Pokémon Deal Scanner v0.4

Python + SQLite scanner for the Pokémon TCG sourcing / resale workflow, tuned for buying and testing resale from Ireland.

## What v0.4 adds

v0.4 keeps the v0.3 Ireland sourcing rules and adds a separate **resale-intelligence layer**. The scanner no longer treats one marketplace number as "the market": acquisition cost and resale evidence stay source-labelled and region-specific.

- Adds an optional **eBay regional market observatory** using the official Browse API.
- Keeps **Ireland, continental EU, UK and Global** eBay evidence separate. EUR/GBP/USD are never silently mixed.
- For Ireland/EU/UK, requires the **actual item location country** to match the regional marketplace; an item listed on eBay Germany but physically located in the US is not counted as EU evidence.
- Adds exact-card eBay watch rows keyed to Cardmarket `id_product`; the first live watch is Dragonite V PGO 076.
- Rejects obvious slabs, graded cards, proxies, custom cards, code cards and lots before using a listing as raw-single evidence.
- Requires a listing to be absent on **two successful scans** before it can be marked gone; one missing result is not called a sale.
- A short-lived confirmed disappearance becomes **inferred quick-sale evidence**, but remains labelled as inferred rather than a confirmed sold price.
- Adds `data/reference/ebay_sold_evidence.csv` for manually verified completed-sale evidence when we have a trustworthy source.
- Uses resale-reference confidence: `STRONG`, `MEDIUM`, `WEAK`, `VERY_WEAK`, `NONE`.
- Active eBay asking prices are a weak fallback and are **never relabelled as sold prices**.
- Adds `output/resale_candidates.csv`, comparing confirmed Ireland-landed sourcing cost against Ireland/EU resale evidence when both exist.
- Suppresses generic top-flip signals for products less than 14 days old to avoid launch-week price noise.
- Bounds database growth: Cardmarket history remains daily for 90 days, weekly to one year, then monthly; raw CardTrader offers are kept for 30 days.

## Pricing / evidence hierarchy

1. **Cardmarket generic low** — discovery only; language, condition and Ireland deliverability are unknown.
2. **Cardmarket EN/NM benchmark** — verified article-price evidence.
3. **Cardmarket EN/NM + ships to Ireland** — eligible sourcing evidence.
4. **Landed / basket-adjusted cost** — the number used for Cardmarket buy decisions.
5. **Seller confidence** — rating quality + sales history as a risk overlay.
6. **CardTrader EN/NM** — independent live European supply evidence.
7. **eBay confirmed sold evidence** — strongest resale reference when region/currency are known.
8. **eBay inferred quick-sales** — useful but explicitly medium-confidence evidence.
9. **eBay active asks** — context only; weak/very-weak resale evidence.

Cardmarket's public download files do not expose offer-level language, condition, destination shipping or seller reputation. Those fields therefore remain in `data/reference/cardmarket_sourcing_offers.csv` and must come from observed Cardmarket offers/checkouts rather than being inferred from the generic low.

## eBay regions

The default v0.4 watch uses the following marketplaces and physical-location filters:

- `IRELAND`: `EBAY_IE` + item location `IE`
- `EU`: `EBAY_DE/FR/IT/ES/NL/BE/AT`, each restricted to its corresponding physical item country
- `UK`: `EBAY_GB` + item location `GB`
- `GLOBAL`: `EBAY_US` as context only, with no local-EU sourcing implication

Ireland/EU references are normally EUR, UK is GBP and Global is USD. Only EUR Ireland/EU references are currently eligible for automatic comparison against our EUR landed sourcing costs.

The eBay Browse API is optional. Configure `EBAY_APP_ID` and `EBAY_CERT_ID` as repository secrets to enable live collection. Without them the daily scanner still succeeds, emits the eBay output contract, and can use rows manually added to `data/reference/ebay_sold_evidence.csv`.

## Main outputs

- `output/cheap_ex.csv`
- `output/top_flips.csv`
- `output/dragonite.csv`
- `output/bundle_candidates.csv`
- `output/seller_baskets.csv`
- `output/cardmarket_sourcing.csv`
- `output/ebay_market_reference.csv`
- `output/resale_candidates.csv`
- `output/pgo076_test.json`
- `output/scanner_status.json`

## Design inspiration

v0.4 reviewed several open-source Pokémon / TCG projects for architecture ideas, especially European price histories, source confidence, listing-state tracking and bounded historical storage. The implementation in this repository is original; code was not copied from repositories that do not publish a reuse licence. See `docs/INSPIRATION.md`.

The GitHub Actions workflow runs daily at about 07:05 Europe/Dublin and can also be run manually.
