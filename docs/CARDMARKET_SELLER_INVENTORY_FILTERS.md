# Cardmarket Seller Inventory Filters — sourcing workflow

Last updated: 2026-09-10

Cardmarket released expanded seller-inventory filters on 2026-09-10. These are useful for manual/consolidated sourcing after a promising seller has been identified.

## What the feature adds

- Sorting applies to the seller's whole inventory rather than a limited subset.
- The old 300-item filter limit is removed.
- Expansion, rarity and language filters use autocomplete and only show values actually present in that seller's inventory.
- Multiple expansions, rarities and languages can be selected at the same time.
- Result counts react to active filters before opening the filtered set.
- Active-filter markers make it easier to see why an expected card is hidden.

## How to use it for this project

After identifying a seller with attractive postage or several Wants-list hits, inspect the seller's full Pokémon inventory before checkout.

Priority passes:

1. **ICON stock** — English, NM; recognizable Pokémon such as Pikachu, Eevee, starters, Dragonite, Gengar, Mewtwo, Gyarados, Eeveelutions, Snorlax, etc.
2. **HERO ex/V stock** — cheap recognizable ex/V/VMAX/VSTAR/Mega cards suitable for Premium bundles.
3. **SHINY Pokémon** — inexpensive Pokémon holo/reverse-holo cards that can strengthen Standard/Premium shiny quotas.
4. **EVOLUTION lines** — cheap matching evolutionary families, especially where the final stage is holo or recognizable.
5. **GREAT theme cards** — attractive Cute or Power/Dragon cards not strong enough to be ICONs.

Use the new filters to reduce seller inventory by language, expansion and rarity, then sort the whole resulting inventory by price where useful.

## Project rules still apply

- Cardmarket actionable sourcing benchmark remains **English + Near Mint** unless explicitly changed by the user.
- Optimize **landed basket cost**, not just headline card price.
- A slightly higher per-card price is acceptable when one seller materially reduces postage and supplies many useful cards.
- Do not add low-value cards merely to fill a shipping allowance; each added card should have a defined bundle/inventory role.
- For ICON restocking, species diversity is more valuable once there is already enough depth for several bundles.

## Automation limitation

This feature is a Cardmarket website/UI improvement, not a new public inventory API. It can improve our manual seller-basket workflow and any browser-assisted review, but it should not be treated as a new automated scanner data source unless Cardmarket separately exposes a compliant machine-readable endpoint.
