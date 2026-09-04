# Pokémon Deal Scanner v0.2

Python + SQLite scanner for the Pokémon TCG sourcing / bundle-resale workflow.

The scanner combines official Cardmarket daily price-guide history, Cardmarket product catalogue mapping, live CardTrader English/Near-Mint offer data, seller-level consolidation for cheap ex/V/Mega-style inventory, and Dragonite / character-bundle watchlists.

## Pricing rule

Three price types stay separate:

1. **Cardmarket generic low** — discovery only; not English+NM-specific.
2. **Cardmarket English+NM** — verified benchmark supplied through `data/reference/en_nm_overrides.csv`.
3. **CardTrader English+NM** — automated live sourcing data from CardTrader; never mislabeled as Cardmarket EN/NM.

See the rest of the repository for setup, configuration, reports, tests, and the daily GitHub Actions workflow.
