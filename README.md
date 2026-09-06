# Pokémon Deal Scanner v0.4

Python + SQLite scanner for the Pokémon TCG sourcing / resale workflow, tuned for buying and testing resale from Ireland.

## What v0.4 adds

v0.4 keeps the v0.3 Ireland sourcing rules and adds a separate **resale-intelligence layer**. The scanner no longer treats one marketplace number as "the market": acquisition cost and resale evidence stay source-labelled and region-specific.

- Adds an optional **eBay regional market-observatory implementation**, currently treated as **dormant/experimental pending permitted-use and production-access clarification**. See `docs/EBAY_API_COMPLIANCE.md`.
- Keeps **Ireland, continental EU, UK and Global** eBay evidence separate. EUR/GBP/USD are never silently mixed.
- For Ireland/EU/UK, requires the **actual item location country** to match the regional marketplace; an item listed on eBay Germany but physically located in the US is not counted as EU evidence.
- Adds exact-card eBay watch rows keyed to Cardmarket `id_product`; the first live watch is Dragonite V PGO 076.
- Rejects obvious slabs, graded cards, proxies, custom cards, code cards and lots before using a listing as raw-single evidence.
- Requires a listing to be absent on **two successful scans** before it can be marked gone; one missing result is not called a sale.
- A short-lived confirmed disappearance becomes **inferred quick-sale evidence**, but remains labelled as inferred rather than a confirmed sold price.
- Adds `data/reference/ebay_sold_evidence.csv` as a template for manually verified completed-sale evidence when use/storage is permitted.
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
7. **Verified sold evidence** — strongest resale reference when exact card/region/currency are known.
8. **Inferred sale evidence** — useful only when explicitly labelled and confidence-controlled.
9. **Active asking prices** — context only; never silently converted into sold evidence.

The detailed manual resale-evidence hierarchy (eBay Product Research -> live sold page -> archived exact listing -> snippet/tracker) and DoneDeal interpretation policy are in [`docs/MARKET_EVIDENCE.md`](docs/MARKET_EVIDENCE.md). A machine-readable policy mirror lives in `data/reference/resale_evidence_hierarchy.csv`.

Cardmarket's public download files do not expose offer-level language, condition, destination shipping or seller reputation. Those fields therefore remain in `data/reference/cardmarket_sourcing_offers.csv` and must come from observed Cardmarket offers/checkouts rather than being inferred from the generic low.

## eBay regions

The dormant v0.4 implementation defines the following marketplaces and physical-location filters:

- `IRELAND`: `EBAY_IE` + item location `IE`
- `EU`: `EBAY_DE/FR/IT/ES/NL/BE/AT`, each restricted to its corresponding physical item country
- `UK`: `EBAY_GB` + item location `GB`
- `GLOBAL`: `EBAY_US` as context only, with no local-EU sourcing implication

Ireland/EU references are normally EUR, UK is GBP and Global is USD. Only EUR Ireland/EU references are eligible for automatic comparison against EUR landed sourcing costs in the current implementation.

**Do not add production eBay API credentials merely to activate this module.** The project identified material API-license / seller-arbitrage and Buy API production-access constraints. Review `docs/EBAY_API_COMPLIANCE.md` and obtain appropriate clarification/approval before production use.

## DoneDeal

DoneDeal can be used **manually** as an additional Irish sourcing and asking-price context source. Current DoneDeal Terms prohibit automated retrieval/indexing/database construction, and its published API policy is not a general marketplace-aggregation API. Therefore DoneDeal is intentionally not an automated scanner source. See `docs/MARKET_EVIDENCE.md`.

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

## Durable project context

Business strategy, standing interpretation rules, local Irish benchmark policy, bundle concepts, deal-evaluation conventions, and conversation-continuity instructions are preserved in [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md).

Before changing scanner behavior or interpreting a run in a new chat/session, review that file together with `docs/MARKET_EVIDENCE.md`, `docs/EBAY_API_COMPLIANCE.md`, `config.yaml`, the relevant `data/reference/` files, and recent commits. Material new decisions should be written back to GitHub rather than left only in conversation history.

## Design inspiration

v0.4 reviewed several open-source Pokémon / TCG projects for architecture ideas, especially European price histories, source confidence, listing-state tracking and bounded historical storage. The implementation in this repository is original; code was not copied from repositories that do not publish a reuse licence. See `docs/INSPIRATION.md`.

The GitHub Actions workflow runs once per day during the 07:00 Europe/Dublin hour, using redundant scheduled attempts plus a daily success marker, and can also be run manually.
