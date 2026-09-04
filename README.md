# Pokémon Deal Scanner v0.3

Python + SQLite scanner for the Pokémon TCG sourcing / bundle-resale workflow, tuned for buying from Ireland.

## What v0.3 changes

- Fixes CardTrader Pokémon mapping (`game_id=5`) and the current live marketplace shapes (`price.cents`, `properties_hash`, `pokemon_language`, CardTrader Zero).
- Keeps Cardmarket's official generic low strictly as discovery data; it is never treated as an English/NM buying price.
- Adds a Cardmarket sourcing-evidence layer for **English + Near Mint + ships to Ireland** offers, including landed/shared-shipping cost and seller confidence.
- Adds seller-risk scoring that combines rating quality with sales history rather than simply preferring the largest seller.
- Separates actionable Dragonite sourcing into `STANDALONE_BUY`, `BUNDLE_BUY`, `VERIFY_LANDED`, `WAIT`, and `INELIGIBLE`.
- Keeps the exact Dragonite V PGO 076 CardTrader diagnostic as a regression check while v0.3 stabilises.

## Pricing hierarchy

1. **Cardmarket generic low** — discovery only; language/condition/shipping are unknown.
2. **Cardmarket EN/NM benchmark** — verified article-price evidence.
3. **Cardmarket EN/NM + ships to Ireland** — eligible sourcing evidence.
4. **Landed / basket-adjusted cost** — the number used for Cardmarket buy decisions.
5. **Seller confidence** — a risk overlay, not a replacement for the real euro cost.
6. **CardTrader EN/NM** — an independent live European source, never relabelled as Cardmarket.

Cardmarket's downloadable price guide does not expose offer-level language, condition, destination shipping, or seller reputation. Those fields therefore live in `data/reference/cardmarket_sourcing_offers.csv` and must be based on observed Cardmarket offers/checkouts rather than inferred from the generic low.

## Main outputs

- `output/cheap_ex.csv`
- `output/top_flips.csv`
- `output/dragonite.csv`
- `output/bundle_candidates.csv`
- `output/seller_baskets.csv`
- `output/cardmarket_sourcing.csv`
- `output/pgo076_test.json`
- `output/scanner_status.json`

The GitHub Actions workflow runs daily at about 07:05 Europe/Dublin and can also be run manually.
