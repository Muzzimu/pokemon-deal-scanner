# Pokémon Deal Scanner v0.5

Python + SQLite scanner for the Pokémon TCG sourcing / resale workflow, tuned for buying and testing resale from Ireland.

## What v0.5 changes

v0.5 closes a pricing-guardrail bug exposed when Cardmarket's generic low came from a cheaper Italian copy.

- Cardmarket's public/generic `low` remains **discovery only**. It may reflect another language or condition and can no longer drive `gap_pct`, flip-gap scoring, or `top_flips.csv` qualification.
- `gap_pct` now means the gap from the **best validated English/NM acquisition reference** (Cardmarket EN/NM or separately labelled CardTrader EN/NM) to Cardmarket `avg30`.
- The raw generic-low gap is retained separately as `generic_gap_pct` for discovery/context only.
- A `top_flips.csv` candidate must now have validated **English/NM acquisition evidence**. A generic low by itself can only produce a validation/watch lead.
- Cardmarket BUY decisions still require the stronger sourcing layer: **English + NM + ships to Ireland + confirmed landed/basket-adjusted cost + seller-risk consideration**.
- Automatic resale decisions remain stricter: a `RESELL_TEST` requires confirmed Ireland-landed sourcing cost plus qualifying Ireland/EU resale evidence.
- The daily GitHub workflow is now resilient to GitHub Actions delays. Scheduled jobs that start after 07:00 Dublin time can still run; redundant attempts are serialized and the daily-success marker prevents duplicate full scans.

Two regression tests explicitly verify that a very cheap generic Cardmarket low cannot create a flip signal when no English/NM acquisition price exists.

## Retained v0.4 resale-intelligence layer

v0.5 keeps the v0.4 regional/evidence architecture:

- optional **eBay regional market-observatory implementation**, currently dormant/experimental pending permitted-use and production-access clarification; see `docs/EBAY_API_COMPLIANCE.md`;
- Ireland, continental EU, UK and Global eBay evidence kept separate;
- physical item location required for regional evidence;
- exact-card eBay watch rows keyed to Cardmarket `id_product`;
- graded/slab/proxy/custom/code-card/lot filtering before raw-single evidence is used;
- repeated-miss requirement before a listing can be marked gone;
- inferred quick-sale evidence kept below confirmed sold evidence;
- resale confidence levels `STRONG`, `MEDIUM`, `WEAK`, `VERY_WEAK`, `NONE`;
- active eBay asks treated as context only, never as sold prices;
- new-product flip guard for the first 14 days;
- bounded Cardmarket/CardTrader/eBay history retention.

## Pricing / evidence hierarchy

1. **Cardmarket generic low** — discovery only; language, condition and Ireland deliverability are unknown. It cannot qualify a flip.
2. **Cardmarket EN/NM benchmark** — verified English/NM article-price evidence.
3. **Cardmarket EN/NM + ships to Ireland** — eligible sourcing evidence.
4. **Landed / basket-adjusted cost** — the number used for Cardmarket buy decisions.
5. **Seller confidence** — rating quality + sales history as a risk overlay.
6. **CardTrader EN/NM** — independent live European supply evidence, kept source-labelled.
7. **Verified sold evidence** — strongest resale reference when exact card/region/currency are known.
8. **Inferred sale evidence** — useful only when explicitly labelled and confidence-controlled.
9. **Active asking prices** — context only; never silently converted into sold evidence.

The detailed manual resale-evidence hierarchy (eBay Product Research -> live sold page -> archived exact listing -> snippet/tracker) and DoneDeal interpretation policy are in [`docs/MARKET_EVIDENCE.md`](docs/MARKET_EVIDENCE.md). A machine-readable policy mirror lives in `data/reference/resale_evidence_hierarchy.csv`.

Cardmarket's public download files do not expose offer-level language, condition, destination shipping or seller reputation. Those fields therefore remain in `data/reference/cardmarket_sourcing_offers.csv` and must come from observed Cardmarket offers/checkouts rather than being inferred from the generic low.

## eBay regions

The dormant implementation defines:

- `IRELAND`: `EBAY_IE` + item location `IE`
- `EU`: `EBAY_DE/FR/IT/ES/NL/BE/AT`, each restricted to its corresponding physical item country
- `UK`: `EBAY_GB` + item location `GB`
- `GLOBAL`: `EBAY_US` as context only

Ireland/EU references are normally EUR, UK is GBP and Global is USD. Only EUR Ireland/EU references are eligible for automatic comparison against EUR landed sourcing costs in the current implementation.

**Do not add production eBay API credentials merely to activate this module.** Review `docs/EBAY_API_COMPLIANCE.md` and obtain appropriate clarification/approval before production use.

## DoneDeal

DoneDeal can be used **manually** as additional Irish sourcing and asking-price context. It is intentionally not an automated scanner source; see `docs/MARKET_EVIDENCE.md`.

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

## Workflow scheduling

The production GitHub Actions workflow targets one full scan per Dublin calendar day once local time has reached **07:00**. Redundant UTC schedule attempts cover Irish DST and GitHub scheduling delays; a serialized concurrency group plus daily success marker prevent duplicate full scans. Manual workflow dispatch remains supported.
